from lib.data.utils import client

import logging

logger = logging.getLogger(__name__)


def call_sbp_api(start_date: str, end_date: str):

    logger.info(f"Getting SIP from {start_date} to {end_date}")

    data_df = client.get_DERSYSDATA(start_date=start_date, end_date=end_date)

    # filter on start and end date, as we sometimes get more
    if start_date.tzinfo is None:
        start_date = start_date.tz_localize(tz="Europe/London")
    if end_date.tzinfo is None:
        end_date = end_date.tz_localize(tz="Europe/London")

    data_df = data_df[data_df["local_datetime"] >= start_date]
    data_df = data_df[data_df["local_datetime"] < end_date]

    return data_df
