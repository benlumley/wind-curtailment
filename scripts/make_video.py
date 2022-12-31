import pandas as pd
from pathlib import Path
import pydeck as pdk
from lib.db_utils import DbRepository
from lib.data.main import analyze_curtailment

DATA_PATH = Path("./data/locations")
start_time = "2022-06-10 00:00:00"
end_time = "2022-06-11 00:00:00"

# load locations
df_bm = pd.read_csv(DATA_PATH / "bm_units_with_locations.csv")
df_bm["coordinates"] = df_bm.apply(lambda row: [row["lng"], row["lat"]], axis=1)
df_bm[["coordinates", "Installed Capacity (Nominal Power) (MW)"]].dropna(how="any")
df_bm["unit"] = df_bm["Unnamed: 0"]
df_bm.set_index("unit", drop=True, inplace=True)

# load curtailment
physical_data_database = f"phys_data_{start_time}_{end_time}.db"
db = DbRepository(physical_data_database)
df_curtilament = analyze_curtailment(db, start_time=start_time, end_time=end_time)


# select one time period
for time in pd.date_range(start=start_time, end=end_time, freq="30T"):
    print(time)
    df_curtilament_one_time = df_curtilament[df_curtilament["Time"] == time]
    df_curtilament_one_time.set_index("unit", drop=True, inplace=True)
    df_all = df_curtilament_one_time.merge(df_bm, on="unit")
    df_all.dropna(how="any", inplace=True)

    print(df_all["delta"].sum())

    df_all["size"] = df_all["delta"]*100 + 1

    # Define a layer to display on a map
    layer = pdk.Layer(
        "ScatterplotLayer",
        df_all,
        pickable=True,
        opacity=0.6,
        stroked=False,
        filled=True,
        radius_scale=20,
        radius_min_pixels=1,
        radius_max_pixels=200,
        line_width_min_pixels=1,
        get_position="coordinates",
        get_radius="size",
        get_fill_color=[255, 140, 0],
        get_line_color=[0, 0, 0],
    )

    # Set the viewport location
    view_state = pdk.ViewState(latitude=54, longitude=0, zoom=5, bearing=0, pitch=0)

    # Render
    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
    )

    r.to_html(f"video/scatterplot_{time}.html")

# make video
import cv2
import os
import imgkit

imgkit.from_file('test.html', 'out.jpg')

image_folder = 'video'
video_name = f'video/video_{start_time}_{end_time}.avi'

# change html to png
from html2image import Html2Image
hti = Html2Image(output_path=image_folder)

images = [img for img in os.listdir(image_folder) if img.endswith(".html")]
for img in images:
    hti.screenshot(
        html_file=f'{image_folder}/{img}',
        save_as=f'{img.replace("html","png")}'
    )

images = [img for img in os.listdir(image_folder) if img.endswith(".png")]

# TODO sort by file name
frame = cv2.imread(os.path.join(image_folder, images[0]))
height, width, layers = frame.shape

video = cv2.VideoWriter(video_name, 0, 1, (width,height))

for image in images:
    video.write(cv2.imread(os.path.join(image_folder, image)))

cv2.destroyAllWindows()
video.release()
