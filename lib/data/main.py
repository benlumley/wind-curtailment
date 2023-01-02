import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import psutil
from sqlalchemy import create_engine

from lib.constants import df_bm_units
from lib.curtailment import analyze_curtailment
from lib.data.fetch_boa_data import run_boa
from lib.data.fetch_bod_data import run_bod
from lib.data.fetch_sbp_data import call_sbp_api
from lib.db_utils import drop_and_initialize_tables, drop_and_initialize_bod_table, DbRepository
from lib.gcp_db_utils import load_data, write_curtailment_data, write_sbp_data, read_data

logger = logging.getLogger(__name__)


def fetch_and_load_data(
    start: Optional[str] = None,
    end: Optional[str] = None,
    chunk_size_minutes: int = 60,
    multiprocess: bool = True,
    pull_data_once: bool = True,
    check_data: bool = False
):
    """
    Entrypoint for the scheduled data refresh. Fetches data from Elexon and pushes
    to the postgres instance.

    check_data: option to check if the data is the database first, default to False

    Writes a CSV as intermediate step
    """

    # get a 1 hour chunk date
    if (start is None) or (end is None):
        end = datetime.now(tz=timezone.utc)
        end = end - timedelta(hours=2)
        end = end.replace(minute=0)
        end = end.replace(second=0)
        end = end.replace(microsecond=0)
        start = end - timedelta(hours=1)

    start = pd.Timestamp(start)
    end = pd.Timestamp(end)

    wind_units = df_bm_units[df_bm_units["FUEL TYPE"] == "WIND"]["SETT_BMU_ID"].unique()

    logger.info(f"Fetching data from ELEXON {start} {end}")

    start_chunk = start
    end_chunk = start_chunk + pd.Timedelta(f"{chunk_size_minutes}T")
    # loop over 30 minutes chunks of data
    while end_chunk <= end:
        logger.info(f"Memory in use: {psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2} MB")

        end_chunk = start_chunk + pd.Timedelta(f"{chunk_size_minutes}T")
        logger.info(f"Running chunk from {start_chunk=} to {end_chunk=}")

        # make new SQL database
        db_url = f"phys_data_{start_chunk}_{end_chunk}.db"
        engine = create_engine(f"sqlite:///{db_url}", echo=False)

        # initialize database
        drop_and_initialize_tables(db_url)
        drop_and_initialize_bod_table(db_url)

        data_df = read_data(start_time=start_chunk, end_time=end_chunk)

        if (len(data_df) > 0) or (not check_data):
            logger.warning(f'Found data between {start_chunk} and {end_chunk}, so wont pull any.')
        else:

            # get BOAs and BODs
            run_boa(
                start_date=start_chunk,
                end_date=end_chunk,
                units=wind_units,
                chunk_size_in_days=chunk_size_minutes / 24 / 60,
                database_engine=engine,
                cache=True,
                multiprocess=multiprocess,
                pull_data_once=pull_data_once,
            )
            run_bod(
                start_date=start_chunk,
                end_date=end_chunk,
                units=wind_units,
                chunk_size_in_days=chunk_size_minutes / 24 / 60,
                database_engine=engine,
                cache=True,
                multiprocess=multiprocess,
                pull_data_once=pull_data_once,
            )

            logger.info("Running analysis")
            db = DbRepository(db_url)
            df = analyze_curtailment(db, str(start_chunk), str(end_chunk))

            # df.to_csv(f"./data/outputs/results-{start_chunk}-{end_chunk}.csv")
            #
            # # load csv and save to database
            # df = load_data(f"./data/outputs/results-{start_chunk}-{end_chunk}.csv")

            logger.info(f"Pushing to postgres, {len(df)} rows")
            try:
                write_curtailment_data(df=df)
                logger.info("Pushing to postgres :done")
            except Exception as e:
                logger.warning("Writing the df failed, but going to carry on anyway")
                logger.error(e)

            df_sbp = call_sbp_api(
                start_date=start_chunk,
                end_date=end_chunk,
            )

            try:
                write_sbp_data(df=df_sbp)
                logger.info("Pushing SBP data to postgres :done")
            except Exception as e:
                logger.warning("Writing the df_sbp failed, but going to carry on anyway")
                logger.error(e)

            # bump up the start_chunk by 30 minutes
            start_chunk = start_chunk + pd.Timedelta(f"{chunk_size_minutes}T")

    return df
