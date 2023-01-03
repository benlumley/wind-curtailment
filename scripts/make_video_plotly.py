import pandas as pd
from pathlib import Path
import os
from lib.db_utils import DbRepository
from lib.data.main import analyze_curtailment
import plotly.graph_objects as go

DATA_PATH = Path("./data/locations")
start_time = "2021-01-11 00:00:00"
end_time = "2021-01-12 00:00:00"

# load locations
df_bm = pd.read_csv(DATA_PATH / "bm_units_with_locations.csv")
df_bm["coordinates"] = df_bm.apply(lambda row: [row["lng"], row["lat"]], axis=1)
df_bm[["coordinates", "Installed Capacity (Nominal Power) (MW)"]].dropna(how="any")
df_bm["unit"] = df_bm["Unnamed: 0"]
df_bm.set_index("unit", drop=True, inplace=True)

# load curtailment
physical_data_database = f"phys_data_{start_time}_{end_time}.db"
db = DbRepository(physical_data_database)
a = db.get_data_for_time_range(start_time=start_time, end_time=end_time)
df_curtilament = analyze_curtailment(db, start_time=start_time, end_time=end_time)


# select one time period
image_folder = f'video/{start_time}_{end_time}'
if not os.path.exists(image_folder):
    os.mkdir(image_folder)

for time in pd.date_range(start=start_time, end=end_time, freq="30T"):

    print(time)
    df_curtilament_one_time = df_curtilament[df_curtilament["Time"] == time]
    df_curtilament_one_time.set_index("unit", drop=True, inplace=True)
    df_all = df_curtilament_one_time.merge(df_bm, on="unit")
    df_all.dropna(how="any", inplace=True)

    print(df_all["delta"].sum())

    df_all["size"] = df_all["delta"] + 1

    fig = go.Figure(data=go.Scattermapbox(
        lon=df_all['lng'],
        lat=df_all['lat'],
        # text=df_all['text'],
        mode='markers',
        marker_size=df_all['size'],
    ))

    fig.update_layout(
        title=f'Wind Curtailment on {time}',
    )
    fig.update_layout(mapbox_style="carto-positron", mapbox_zoom=4.5, mapbox_center={"lat": 55, "lon": -3})
    print('Saving image')
    fig.write_image(f"video/{time}.png", width=600, height=800)

# make video
import os, cv2
video_name = f'video/video_{start_time}_{end_time}.avi'
images = sorted([img for img in os.listdir(image_folder) if img.endswith(".png")])

# TODO sort by file name
frame = cv2.imread(os.path.join(image_folder, images[0]))
height, width, layers = frame.shape

video = cv2.VideoWriter(video_name, 0, fps=6, frameSize=(width,height))

for image in images:
    video.write(cv2.imread(os.path.join(image_folder, image)))

cv2.destroyAllWindows()
video.release()
