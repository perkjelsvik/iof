import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_daq as daq
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import sqlite3
import pandas as pd
from flask_caching import Cache
import pyarrow as pa
import pyarrow.plasma as plasma
import numpy as np
import pickle
from datetime import timedelta
from datetime import datetime as dt
import dash_auth
import toml
import plotly
import os

from layoutCode import app_page_layout, header_colors
from metaData import aq_cage, aq_cage_new, ref_cage


usrpwd = toml.load("usrpwd.toml")
VALID_USERNAME_PASSWORD_PAIR = [[usrpwd["username"], usrpwd["password"]]]
app = dash.Dash(__name__)
auth = dash_auth.BasicAuth(app, VALID_USERNAME_PASSWORD_PAIR)
# cache = Cache(
#    app.server,
#    config={
#        "CACHE_TYPE": "redis",
#        "CACHE_TYPE": "filesystem",
#        "CACHE_DIR": "cache-directory",
#        "CACHE_THRESHOLD": 100,
#    },
# )


start_project_time = 1541498400
# end_project_time = 1557496200  # 10th of may
end_project_time = 1562277600
# timeout = 1 * 60 * 60  # 1 hour timeout for filesystem cache

# Init
tz = "Europe/Oslo"
dt_format = "%Y-%m-%d %H:%M:%S"
depth_tags = tuple(
    *[
        list(range(10, 90, 2))
        + list(range(97, 107))
        + list(range(107, 109))
        + list(range(110, 126, 2))
    ]
)
acc_tags = tuple(range(11, 91, 2))
aqz_tags = tuple(*[list(range(10, 50)) + list(range(97, 107))])
aqz_depth = tuple(*[list(range(10, 50, 2)) + list(range(97, 107))])
ref_depth = tuple(
    *[list(range(50, 90, 2)) + list(range(107, 109)) + list(range(110, 126, 2))]
)
ref_tags = tuple(
    *[list(range(50, 90)) + list(range(107, 109)) + list(range(110, 126, 2))]
)
all_tags = tuple(sorted([*aqz_tags, *ref_tags]))
aqz_tbrs = tuple([732, 735, 837])
ref_tbrs = tuple([730, 734, 836])
all_tbrs = tuple(sorted([*aqz_tbrs, *ref_tbrs]))
tag_frequencies = (69, 71, 73)
tag_freq_69 = tuple(range(10, 90))
tag_freq_71 = tuple(
    *[list(range(97, 102)) + list(range(107, 109)) + list(range(110, 116, 2))]
)
tag_freq_73 = tuple(*[list(range(102, 107)) + list(range(116, 126, 2))])

# PROBABLY LAST AVAILABLE 71/73 data timestamp: 1549949008 | 12.02.2019 06:23:28


# Parameters
showDiv = {"display": "inline-block"}
hideDiv = {"display": "none"}
marker_line_options = [
    {"label": "Solid", "value": "solid"},
    {"label": "dot", "value": "dot"},
    {"label": "Dash", "value": "dash"},
    {"label": "Long Dash", "value": "longdash"},
    {"label": "Dash Dot", "value": "dashdot"},
    {"label": "Long Dash Dot", "value": "longdashdot"},
]
timeseries_xaxis_dict = dict(
    rangeselector=dict(
        buttons=list(
            [
                dict(count=1, label="1h", step="hour", stepmode="backward"),
                dict(count=2, label="2h", step="hour", stepmode="backward"),
                dict(count=3, label="3h", step="hour", stepmode="backward"),
                dict(count=6, label="6h", step="hour", stepmode="backward"),
                dict(count=12, label="12h", step="hour", stepmode="backward"),
                dict(count=24, label="24h", step="hour", stepmode="backward"),
                dict(count=7, label="1w", step="day", stepmode="backward"),
                dict(count=14, label="2w", step="day", stepmode="backward"),
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(count=2, label="2m", step="month", stepmode="backward"),
                dict(count=3, label="3m", step="month", stepmode="backward"),
                dict(count=6, label="6m", step="month", stepmode="backward"),
                dict(step="all"),
            ]
        )
    ),
    rangeslider=dict(visible=True),
    type="date",
    title="Time",
)


def db_sql_query(starts_ts, table):
    # Shared filters
    ts_filt = f"timestamp > {starts_ts}"
    order = "timestamp ASC"
    freq = (69, 71, 73)  # tag and positions

    if table == "tag":
        comm = "S256"
        columns = "timestamp, tbr_serial_id, tag_id, tag_data, snr, millisecond"
        freq_filt = f"frequency IN {freq}"
        comm_filt = f"comm_protocol = '{comm}'"
        tag_filt = f"tag_id IN {all_tags}"
        tbr_filt = f"tbr_serial_id IN {all_tbrs}"
        filters = (
            f"{ts_filt} AND {freq_filt} AND {comm_filt} AND {tag_filt} AND {tbr_filt}"
        )
    elif table == "tbr":
        columns = "timestamp, tbr_serial_id, temperature, noise_avg, noise_peak"
        filters = f"{ts_filt}"
    elif table == "pos":
        table = "positions"
        columns = (
            "timestamp, tag_id, frequency, millisecond, x, y, z, latitude, longitude"
        )
        tag_filt = f"tag_id IN {all_tags}"
        freq_filt = f"frequency IN {freq}"
        filters = f"{ts_filt} AND {tag_filt} AND {freq_filt}"

    # query
    query = f"SELECT {columns} FROM {table} WHERE {filters} ORDER BY {order};"
    return query


def clean_df(df, name):
    # Optimize and transform dataframe
    df.timestamp = df.timestamp.astype("uint32")
    print("Converting timestamps to datetime...")
    df["Date"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    print("Converting timezone...")
    df.Date = df.Date.dt.tz_convert(tz)
    print("Converting datetime to str...")
    df["Date_str"] = df.Date.dt.strftime(dt_format)
    print("Extracting hour into new column...")
    df["hour"] = df.Date_str.str.slice(11, 13, 1)
    df.hour = df.hour.astype("uint8")
    print("Setting datetime as index")
    df = df.set_index("Date")
    print("optimizing memory...")
    if name == "tag":
        df.tbr_serial_id = df.tbr_serial_id.astype("uint16")
        df.tag_id = df.tag_id.astype("uint8")
        df.tag_data = -df.tag_data
        df.snr = df.snr.astype("uint8")
        df.millisecond = df.millisecond.astype("uint16")
    elif name == "tbr":
        df.tbr_serial_id = df.tbr_serial_id.astype("uint16")
        df.noise_avg = df.noise_avg.astype("uint8")
        df.noise_peak = df.noise_peak.astype("uint8")
    elif name == "pos":
        df.tag_id = df.tag_id.astype("uint8")
        df.frequency = df.frequency.astype("uint8")
        df.millisecond = df.millisecond.astype("uint16")
        df.z = -df.z
    return df


def write_to_plasma(df, type):
    with open("plasma_state.pkl", "rb") as f:
        plasma_state = pickle.load(f)
    # get the object ID for the dataframe
    object_id = plasma_state[type]
    client = plasma.connect("/tmp/plasma")
    client.delete([object_id])
    # Convert the Pandas DataFrame into a PyArrow RecordBatch
    record_batch = pa.RecordBatch.from_pandas(df)
    # Create the Plasma object from the PyArrow RecordBatch. Most of the work here
    # is done to determine the size of buffer to request from the object store.
    object_id = plasma.ObjectID(np.random.bytes(20))
    mock_sink = pa.MockOutputStream()
    stream_writer = pa.RecordBatchStreamWriter(mock_sink, record_batch.schema)
    stream_writer.write_batch(record_batch)
    stream_writer.close()
    data_size = mock_sink.size()
    buf = client.create(object_id, data_size)
    # Write the PyArrow RecordBatch to Plasma
    stream = pa.FixedSizeBufferWriter(buf)
    stream_writer = pa.RecordBatchStreamWriter(stream, record_batch.schema)
    stream_writer.write_batch(record_batch)
    stream_writer.close()
    # Seal the Plasma object
    client.seal(object_id)
    # end the client
    client.disconnect()
    # Write the new object ID
    plasma_state[type] = object_id
    with open("plasma_state.pkl", "wb") as f:
        pickle.dump(plasma_state, f)


def read_from_plasma(type):
    # get the current plasma_state
    with open("plasma_state.pkl", "rb") as f:
        plasma_state = pickle.load(f)
    # get the object ID for the dataframe
    object_id = plasma_state[type]
    # get the client and read from it
    client = plasma.connect("/tmp/plasma")
    # Fetch the Plasma object
    [data] = client.get_buffers([object_id])  # Get PlasmaBuffer from ObjectID
    buffer = pa.BufferReader(data)
    # Convert object back into an Arrow RecordBatch
    reader = pa.RecordBatchStreamReader(buffer)
    record_batch = reader.read_next_batch()
    # Convert back into Pandas
    df = record_batch.to_pandas()
    # close out and finish
    client.disconnect()
    return df


# @cache.memoize(timeout=timeout)
def clean_data(start_ts, name):
    # db = "Aquatraz.db"
    db = "../backend/src/backend/dbmanager/databases/iof.db"

    # create sql query
    query = db_sql_query(start_ts, name)

    # Read from databse
    print("Reading from database")
    con = sqlite3.connect(db)
    df = pd.read_sql(query, con)
    con.close()

    print("cleaning up dataframe")
    df = clean_df(df, name)

    return df


def get_date_picker(type):
    return html.Div(
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name", children=["Choose date period"]
            ),
            dcc.DatePickerRange(
                id=f"{type}-date-picker-range",
                start_date=dt.strftime(dt.today() - timedelta(days=30), "%Y-%m-%d"),
                end_date=dt.strftime(dt.today(), "%Y-%m-%d"),
                min_date_allowed=dt.fromtimestamp(start_project_time),
                max_date_allowed=dt.today(),
                display_format="DD/MM/YYYY",
                clearable=False,
                first_day_of_week=1,
                className="fullwidth-app-controls-name",
                initial_visible_month=dt.today(),
                number_of_months_shown=2,
                show_outside_days=True,
                with_portal=True,
            ),
            html.Div(
                children=[
                    html.Button(
                        "Start",
                        id=f"{type}-start-date-btn",
                        className="app-controls-btn",
                    ),
                    html.Div("", className="app-controls-btn"),
                    html.Button(
                        "Today", id=f"{type}-end-date-btn", className="app-controls-btn"
                    ),
                ]
            ),
        ],
    )


def get_time_picker_switch(type):
    return html.Div(
        className="app-controls-block",
        children=[
            html.Div(
                className="app-controls-name-",
                children=["Enable filtering based on time of day?"],
            ),
            daq.BooleanSwitch(id=f"{type}-time-switch", on=False),
        ],
    )


def get_time_picker(type):
    return html.Div(
        id=f"{type}-time-picker-div",
        className="app-controls-block",
        children=[
            html.Div(className="fullwidth-app-controls-name", children=["Start Time"]),
            daq.NumericInput(
                id=f"{type}-start-hour-picker",
                className="app-controls-name",
                value=0,
                min=0,
                max=23,
                label="Hour",
            ),
            daq.NumericInput(
                id=f"{type}-start-minute-picker",
                className="app-controls-name",
                value=0,
                min=0,
                max=59,
                label="Minute",
            ),
            daq.NumericInput(
                id=f"{type}-start-second-picker",
                className="app-controls-name",
                value=0,
                min=0,
                max=59,
                label="Second",
            ),
            html.Div(className="fullwidth-app-controls-name", children=["End Time"]),
            daq.NumericInput(
                id=f"{type}-end-hour-picker",
                className="app-controls-name",
                value=23,
                min=0,
                max=23,
                label="Hour",
            ),
            daq.NumericInput(
                id=f"{type}-end-minute-picker",
                className="app-controls-name",
                value=59,
                min=0,
                max=59,
                label="Minute",
            ),
            daq.NumericInput(
                id=f"{type}-end-second-picker",
                className="app-controls-name",
                value=59,
                min=0,
                max=59,
                label="Second",
            ),
        ],
    )


def get_cage_tbr_dropdown(type, cage="All"):
    return html.Div(
        id=f"{type}-cage-tbr-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name", children=["Select cage (TBR)"]
            ),
            dcc.Dropdown(
                id=f"{type}-cage-tbr-dropdown",
                value=cage,
                options=[
                    {"label": i, "value": i} for i in ("Aquatraz", "Reference", "All")
                ],
                clearable=False,
            ),
        ],
    )


def get_tbr_dropdown(type):
    return html.Div(
        id=f"{type}-tbr-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(className="fullwidth-app-controls-name", children=["Select TBRs"]),
            dcc.Dropdown(
                id=f"{type}-tbr-dropdown",
                value=all_tbrs,
                options=[{"label": f"tbr {i}", "value": i} for i in all_tbrs],
                multi=True,
            ),
        ],
    )


def get_cage_tag_dropdown(type, cage="All"):
    return html.Div(
        id=f"{type}-cage-tag-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name", children=["Select cage (TAGs)"]
            ),
            dcc.Dropdown(
                id=f"{type}-cage-tag-dropdown",
                value=cage,
                options=[
                    {"label": i, "value": i} for i in ("Aquatraz", "Reference", "All")
                ],
                clearable=False,
            ),
        ],
    )


def get_tag_frequency_dropdown(type):
    return html.Div(
        id=f"{type}-tag-frequency-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=["Select tag frequencies"],
            ),
            dcc.Dropdown(
                id=f"{type}-tag-frequency-dropdown",
                value=[69, 71, 73],
                options=[{"label": f"{i}", "value": i} for i in tag_frequencies],
                multi=True,
                clearable=False,
            ),
        ],
    )


def get_tag_dropdown(type):
    return html.Div(
        id=f"{type}-tag-id-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name", children=["Select tag IDs"]
            ),
            dcc.Dropdown(
                id=f"{type}-tag-id-dropdown",
                value=[10, 0],
                options=[{"label": f"tag {i}", "value": i} for i in depth_tags],
                multi=True,
                clearable=False,
                placeholder="Select at least one tag frequency first!",
            ),
        ],
    )


tag_filter_options = [
    # Date picker
    get_date_picker("tag"),
    # Time picker on/off switch
    get_time_picker_switch("tag"),
    # Time picker
    get_time_picker("tag"),
    html.Hr(),
    # Dropdown for cage TBR
    get_cage_tbr_dropdown("tag"),
    # Dropdown for TBR IDs
    get_tbr_dropdown("tag"),
    html.Hr(),
    # Dropdown for data type
    html.Div(
        id="tag-data-type-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=["Choose tag data type"],
            ),
            dcc.Dropdown(
                id="tag-data-type-dropdown",
                value="depth",
                options=[
                    {"label": "All", "value": "all"},
                    {"label": "Depth [m]", "value": "depth"},
                    {"label": "Acceleration [m/s^2]", "value": "acc"},
                ],
                clearable=False,
            ),
        ],
    ),
    # Dropdown for cage tags
    get_cage_tag_dropdown("tag"),
    # Dropdown for tag Frequencies
    get_tag_frequency_dropdown("tag"),
    # Dropdown for tag IDs
    get_tag_dropdown("tag"),
    html.Hr(),
    # Rangeslider for SNR
    html.Div(
        id="tag-snr-rangeslider-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=["Filter based on SNR"],
            ),
            dcc.RangeSlider(
                id="tag-snr-rangeslider",
                className="control-slider",
                min=6,
                max=60,
                value=[6, 60],
                marks={
                    6: {"label": "6", "style": {"color": "#c12f19"}},
                    12: {"label": "12", "style": {"color": "#e06f06"}},
                    25: {"label": "25", "style": {"color": "#7add1c"}},
                    60: {"label": "60", "style": {"color": "#06e03d"}},
                },
            ),
            html.Div(className="app-controls-name", id="snr-values"),
        ],
    ),
    # Bottom-line
    html.Hr(),
]

tbr_filter_options = [
    # Date picker
    get_date_picker("tbr"),
    # Time picker on/off switch
    get_time_picker_switch("tbr"),
    # Time picker
    get_time_picker("tbr"),
    # Dropdown for cage TBR
    html.Hr(),
    get_cage_tbr_dropdown("tbr"),
    # Dropdown for TBR IDs
    get_tbr_dropdown("tbr"),
    html.Hr(),
    # Rangeslider for Temperature
    html.Div(
        id="tbr-temperature-rangeslider-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=["Filter based on Temperature"],
            ),
            dcc.RangeSlider(
                id="tbr-temperature-rangeslider",
                className="control-slider",
                min=-5,
                max=35,
                value=[-5, 35],
                marks={
                    -5: {"label": "-5 °C", "style": {"color": "#08cdd1"}},
                    10: {"label": "10 °C"},
                    20: {"label": "20 °C"},
                    35: {"label": "35 °C", "style": {"color": "#c40f05"}},
                },
            ),
            html.Div(className="app-controls-name", id="temperature-values"),
        ],
    ),
    # Rangeslider for Ambient noise
    html.Div(
        id="tbr-amb-avg-noise-rangeslider-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=["Filter based on Average Ambient Noise"],
            ),
            dcc.RangeSlider(
                id="tbr-amb-avg-noise-rangeslider",
                className="control-slider",
                min=0,
                max=255,
                value=[0, 255],
                marks={0: {"label": "0"}, 128: {"label": "128"}, 255: {"label": "255"}},
            ),
            html.Div(className="app-controls-name", id="amb-avg-noise-values"),
        ],
    ),
    # Rangeslider for Ambient noise
    html.Div(
        id="tbr-amb-peak-noise-rangeslider-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=["Filter based on Ambient Noise Peak"],
            ),
            dcc.RangeSlider(
                id="tbr-amb-peak-noise-rangeslider",
                className="control-slider",
                min=0,
                max=255,
                value=[0, 255],
                marks={0: {"label": "0"}, 128: {"label": "128"}, 255: {"label": "255"}},
            ),
            html.Div(className="app-controls-name", id="amb-peak-noise-values"),
        ],
    ),
    # Bottom-line
    html.Hr(),
]

pos_filter_options = [
    # Date picker
    get_date_picker("pos"),
    # Time picker on/off switch
    get_time_picker_switch("pos"),
    # Time picker
    get_time_picker("pos"),
    html.Hr(),
    # Dropdown for cage tags
    get_cage_tag_dropdown("pos", cage="Aquatraz"),
    # Dropdown for tag Frequencies
    get_tag_frequency_dropdown("pos"),
    # Dropdown for tag IDs
    get_tag_dropdown("pos"),
    # Bottom-line
    html.Hr(),
]

tag_plot_options = [
    {"label": "Scatter", "value": "scatter"},
    {"label": "Histogram", "value": "histogram"},
    {"label": "Box Plot", "value": "boxplot"},
    {"label": "2D Histogram", "value": "histogram2d"},
    {"label": "2D Histogram Contour", "value": "histogram2dcontour"},
    {"label": "3D Scatter", "value": "scatter3d"},
    {"label": "ikke bruk", "value": "scatter_ikke"},
]

tbr_plot_options = list(tag_plot_options)
tbr_plot_options.append(
    {"label": "Histogram 2D animation test", "value": "histogram2dcontour_animation"}
)
pos_plot_options = list(tag_plot_options)
pos_plot_options.append(
    {"label": "3D position animation", "value": "scatter3d_animation"}
)

all_plot_options = {
    "tag": tag_plot_options,
    "tbr": tbr_plot_options,
    "pos": pos_plot_options,
}

tag_axis_options = [
    {"label": "Date", "value": "Date_str"},
    {"label": "Timestamp", "value": "timestamp"},
    {"label": "Hour of day", "value": "hour"},
    {"label": "Millisecond", "value": "millisecond"},
    {"label": "TBR ID", "value": "tbr_serial_id"},
    {"label": "Tag ID", "value": "tag_id"},
    {"label": "Tag Data", "value": "tag_data"},
    {"label": "SNR", "value": "snr"},
    {"label": "Frequency", "value": "frequency"},
]

tbr_axis_options = [
    {"label": "Date", "value": "Date_str"},
    {"label": "Timestamp", "value": "timestamp"},
    {"label": "Hour of day", "value": "hour"},
    {"label": "Temperature [°C]", "value": "temperature"},
    {"label": "Ambient Noise Average", "value": "noise_avg"},
    {"label": "Ambient Noise Peak", "value": "noise_peak"},
]

pos_axis_options = [
    {"label": "Date", "value": "Date_str"},
    {"label": "Timestamp", "value": "timestamp"},
    {"label": "Hour of day", "value": "hour"},
    {"label": "Millisecond", "value": "millisecond"},
    {"label": "X position (tag)", "value": "x"},
    {"label": "Y position (tag)", "value": "y"},
    {"label": "Z position (tag)", "value": "z"},
    {"label": "Latitude", "value": "latitude"},
    {"label": "Longitude", "value": "longitude"},
    {"label": "Frequency", "value": "frequency"},
]

plot_scatter_options = [
    {"label": "Markers", "value": "markers"},
    {"label": "Markers + Lines", "value": "markers+lines"},
    {"label": "Lines", "value": "lines"},
]

plot_boxplot_options = [
    {"label": "Group", "value": "group"},
    {"label": "Overlay", "value": "overlay"},
]

axisLabels = dict(
    Date_str="Date",
    timestamp="Timestamp",
    hour="Hour of day",
    millisecond="Millisecond",
    tbr_serial_id="TBR Serial ID",
    tag_id="Tag ID",
    tag_data="Tag Data",
    snr="Signal to Noise ratio (SNR)",
    frequency="Frequency",
    temperature="Temperature [°C]",
    noise_avg="Ambient Noise Average",
    noise_peak="Ambient Noise Peak",
    x="X-position [m]",
    y="Y-position [m]",
    z="Depth [m]",
    latitude="Latitude",
    longitude="Longitude",
)

plotLabels = dict(
    scatter="Scatter",
    histogram="Histogram",
    boxplot="Boxplot",
    histogram2d="2D Histogram",
    histogram2dcontour="2D Histogram Contour",
    scatter3d="3D Scatter",
    histogram2dcontour_animation="2D Histogram Contour animation (test)",
    scatter3d_animation="3D Position Animation",
    scatter_ikke="Scatter",
)


def get_plot_selection_div(type, plotType, options):
    return html.Div(
        className="app-controls-block",
        children=[
            html.Div(className="fullwidth-app-controls-name", children=["Plot type"]),
            dcc.Dropdown(
                id=f"{type}-plot-type-selection-dropdown",
                value=plotType,
                clearable=False,
                options=options,
            ),
        ],
    )


def get_axis_div(type, axis, axisValue):
    return html.Div(
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=[f"{axis.capitalize()}-axis"],
            ),
            dcc.Dropdown(
                id=f"{type}-{axis}-axis-selection-dropdown",
                value=axisValue,
                clearable=False,
            ),
        ],
    )


def get_plot_options_div(type, plotType, info, value):
    if plotType == "boxplot":
        return html.Div(
            className="app-controls-block",
            id=f"{type}-{plotType}-options-div",
            children=[
                html.Div(className="fullwidth-app-controls-name", children=[info]),
                dcc.Dropdown(
                    id=f"{type}-{plotType}-options-selection-dropdown",
                    value=value,
                    clearable=False,
                    options=plot_boxplot_options,
                ),
            ],
        )
    elif plotType == "scatter":
        return html.Div(
            className="app-controls-block",
            id=f"{type}-{plotType}-options-div",
            children=[
                html.Div(className="fullwidth-app-controls-name", children=[info]),
                dcc.Dropdown(
                    id=f"{type}-{plotType}-options-selection-dropdown",
                    value=value,
                    clearable=False,
                    options=plot_scatter_options,
                ),
                daq.NumericInput(
                    id=f"{type}-plot-marker-size",
                    className="app-controls-name",
                    value=6,
                    min=1,
                    max=20,
                    label="Mark size",
                ),
                daq.NumericInput(
                    id=f"{type}-plot-marker-opacity",
                    className="app-controls-name",
                    value=0.5,
                    min=0,
                    max=1,
                    label="Mark opacity",
                ),
                daq.NumericInput(
                    id=f"{type}-plot-line-width",
                    className="app-controls-name",
                    value=2,
                    min=1,
                    max=20,
                    label="Line width",
                ),
                html.Div(
                    className="fullwidth-app-controls-name",
                    children=["Line dash type (scatter plots)"],
                ),
                dcc.Dropdown(
                    id=f"{type}-plot-line-dash",
                    value="solid",
                    clearable=False,
                    options=marker_line_options,
                ),
            ],
        )


def get_timeseries_switch_div(type):
    return html.Div(
        id=f"{type}-enable-timeseries-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name",
                children=["Enable timeseries (forces x-axis to 'Date')"],
            ),
            daq.BooleanSwitch(id=f"{type}-enable-timeseries", on=False),
        ],
    )


tag_plot_controls = [
    # Plot Type
    get_plot_selection_div("tag", "scatter", tag_plot_options),
    # Timeseries
    get_timeseries_switch_div("tag"),
    html.Hr(),
    # X-axis
    get_axis_div("tag", axis="x", axisValue="Date_str"),
    # Y-axis
    get_axis_div("tag", axis="y", axisValue="tag_data"),
    # Z-axis
    get_axis_div("tag", axis="z", axisValue="snr"),
    html.Hr(),
    # Plot options
    get_plot_options_div(
        "tag",
        "scatter",
        info="Scatter marker mode (scatter plots)",
        value="markers+lines",
    ),
    get_plot_options_div(
        "tag", "boxplot", info="Select boxmode (boxplot)", value="group"
    ),
    html.Hr(),
]

tbr_plot_controls = [
    # Plot Type
    get_plot_selection_div("tbr", "scatter", tbr_plot_options),
    # Timeseries
    get_timeseries_switch_div("tbr"),
    html.Hr(),
    # X-axis
    get_axis_div("tbr", axis="x", axisValue="Date_str"),
    # Y-axis
    get_axis_div("tbr", axis="y", axisValue="temperature"),
    # Z-axis
    get_axis_div("tbr", axis="z", axisValue="noise_avg"),
    html.Hr(),
    # Plot options
    get_plot_options_div(
        "tbr", "scatter", info="Scatter marker mode", value="markers+lines"
    ),
    get_plot_options_div("tbr", "boxplot", info="Select boxmode", value="group"),
    html.Hr(),
]

pos_plot_controls = [
    html.P(
        "If you select '3D scatter' or '3D position anmimation', be aware that the "
        "TBRs of the 'Aquatraz' cage was moved 10th of may, and so the xyz-coordinates "
        "after this date will not match earlier xyz-positions. The reference cage "
        "remains unchanged."
    ),
    # Plot Type
    get_plot_selection_div("pos", "scatter3d", pos_plot_options),
    dcc.ConfirmDialog(
        id=f"pos-confirm-3d-animation",
        message=(
            "Selecting a large time period for this 3d animation plot will result in a "
            "long response time, and the resulting graph will be slow / not as "
            "responsive. Especially for tags with frequency 71 and 73 (rapid-updates)."
        ),
    ),
    # Timeseries
    get_timeseries_switch_div("pos"),
    html.Hr(),
    # X-axis
    get_axis_div("pos", axis="x", axisValue="x"),
    # Y-axis
    get_axis_div("pos", axis="y", axisValue="y"),
    # Z-axis
    get_axis_div("pos", axis="z", axisValue="z"),
    html.Hr(),
    # Plot options
    get_plot_options_div(
        "pos", "scatter", info="Scatter marker mode", value="markers+lines"
    ),
    get_plot_options_div("pos", "boxplot", info="Select boxmode", value="group"),
    html.Hr(),
]


def get_graph_div(type, style=hideDiv):
    return html.Div(
        id=f"{type}-graph-div",
        style=style,
        children=dcc.Graph(
            style={"bgcolor": "rgba(0,0,0,0)"},
            id=f"{type}-graph",
            className="tag-graph",
            config={"scrollZoom": True},
        ),
    )


def get_submit_btn_div(type, style=hideDiv):
    return html.Div(
        id=f"{type}-submit-button-div",
        className="submit-button",
        style=style,
        children=[
            html.Button(
                id=f"{type}-submit-button",
                n_clicks=0,
                children="Submit changes",
                style={"fontSize": 28},
            )
        ],
    )


def layout_test():
    return html.Div(
        id="iofp-page-content",
        className="app-body",
        children=[
            # Graph
            dcc.Loading(
                className="dashiof-loading",
                children=[
                    get_graph_div("tag", style=showDiv),
                    get_graph_div("tbr", style=hideDiv),
                    get_graph_div("pos", style=hideDiv),
                ],
            ),
            # Control Tabs
            html.Div(
                id="iof-control-tabs",
                className="control-tabs",
                children=[
                    dcc.Tabs(
                        id="iof-tabs",
                        value="what-is",
                        children=[
                            # Info tab
                            dcc.Tab(
                                label="About",
                                value="what-is",
                                children=html.Div(
                                    className="control-tab",
                                    children=[
                                        html.H4(
                                            className="what-is",
                                            children="Internet of Fish tool",
                                        ),
                                        html.P(
                                            "This Dash app allows you to plot data "
                                            "collected through acoustic telemetry in "
                                            "fish farms or fjords, using the SLIM "
                                            "hardware module, and IOF backend. It can "
                                            "plot both real-time and historic data."
                                            "You can adjust which type of data you "
                                            "want to plot in the 'data' tab. Possible "
                                            "data types are 'tag', 'tbr', and "
                                            "'positions'."
                                        ),
                                        html.P(
                                            "In the 'Plot' tab, you can select what "
                                            "kind of plot you want (scatter, boxplot, "
                                            "2dhistogram...), and you can customize "
                                            "how the plot looks to some degree. "
                                            "You can also choose what x-, y- and "
                                            "z-axis you want for the graph. In the"
                                            "'filters' tab, you can adjust and filter "
                                            "the data you want to view (for example "
                                            "filtering based on SNR value, or "
                                            "selecting data from specific "
                                            "tag-ids / TBRs)."
                                        ),
                                        html.Hr(),
                                        html.P(
                                            "When you have made the changes you want "
                                            "to the plot options and filtering, press "
                                            "the 'Submit Changes' Button to update the "
                                            "graph. When switching datasets, the graph "
                                            "is automatically updated"
                                        ),
                                    ],
                                ),
                            ),
                            # Data set tab
                            dcc.Tab(
                                label="Data",
                                value="data",
                                children=html.Div(
                                    className="control-tab",
                                    children=[
                                        html.H4(
                                            className="what-is", children="Select data"
                                        ),
                                        html.P("Select what data set you want to plot"),
                                        html.Div(
                                            className="app-controls-block",
                                            children=[
                                                html.Div(
                                                    className="app-controls-name",
                                                    children=["Choose data set"],
                                                ),
                                                dcc.Dropdown(
                                                    id="data-set-selection-dropdown",
                                                    value="tag",
                                                    clearable=False,
                                                    options=[
                                                        {
                                                            "label": "tag",
                                                            "value": "tag",
                                                        },
                                                        {
                                                            "label": "tbr",
                                                            "value": "tbr",
                                                        },
                                                        {
                                                            "label": "position",
                                                            "value": "pos",
                                                        },
                                                    ],
                                                ),
                                                html.Hr(),
                                                html.P(
                                                    children=[
                                                        "Valgene under er valg for å "
                                                        "lagre figurer i forskjellig "
                                                        "format på Per Arne sin PC. "
                                                        "Vennligst *ikke* bruk disse "
                                                        "valgene, da det lagres filer "
                                                        "til Per Arne sin datamaskin "
                                                        "hver gang. Skal se på "
                                                        "muligheten til å kunne lagre "
                                                        "til andre datamaskiner i "
                                                        "fremtiden. For øyeblikket kan "
                                                        "en eksportere png-format "
                                                        "i menyen til plottet."
                                                    ]
                                                ),
                                                dcc.Dropdown(
                                                    id="fig-format-options",
                                                    value="pdf",
                                                    className="app-controls-name",
                                                    clearable=False,
                                                    options=[
                                                        {
                                                            "label": "pdf",
                                                            "value": "pdf",
                                                        },
                                                        {
                                                            "label": "eps",
                                                            "value": "eps",
                                                        },
                                                        {
                                                            "label": "svg",
                                                            "value": "svg",
                                                        },
                                                        {
                                                            "label": "webp",
                                                            "value": "webp",
                                                        },
                                                        {
                                                            "label": "jpeg",
                                                            "value": "jpeg",
                                                        },
                                                    ],
                                                ),
                                                html.Button(
                                                    "Export",
                                                    id=f"fig-save-button",
                                                    className="app-controls-name",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ),
                            # Tag Plot tab
                            dcc.Tab(
                                label="Plot",
                                value="plot",
                                children=html.Div(
                                    className="control-tab",
                                    children=[
                                        html.H4(
                                            className="what-is",
                                            children="Customize the plot",
                                        ),
                                        html.P(
                                            "Select which type of plot and what x-axis "
                                            "and y-axis you want. In addition, you can "
                                            "also customize how the plot looks "
                                            "(markers, lines, markers+lines etc.)"
                                        ),
                                        html.Hr(),
                                        # Tag plot tab
                                        html.Div(
                                            id="tag-plot-tab",
                                            children=tag_plot_controls,
                                            style=showDiv,
                                        ),
                                        # Tbr plot tab
                                        html.Div(
                                            id="tbr-plot-tab",
                                            children=tbr_plot_controls,
                                            style=hideDiv,
                                        ),
                                        # pos plot tab
                                        html.Div(
                                            id="pos-plot-tab",
                                            children=pos_plot_controls,
                                            style=hideDiv,
                                        ),
                                    ],
                                ),
                            ),
                            # Data filtering tab
                            dcc.Tab(
                                label="Filter",
                                value="filter",
                                children=html.Div(
                                    className="control-tab",
                                    children=[
                                        html.H4(
                                            className="what-is",
                                            children="Filter the data",
                                        ),
                                        html.P(
                                            "Filter the data you want, i.e. select "
                                            "specific tag IDs, or TBRs, or cages etc."
                                        ),
                                        html.Hr(),
                                        # TAG filter options
                                        html.Div(
                                            id="tag-filter-tab",
                                            children=tag_filter_options,
                                            style=showDiv,
                                        ),
                                        # TBR filter options
                                        html.Div(
                                            id="tbr-filter-tab",
                                            children=tbr_filter_options,
                                            style=hideDiv,
                                        ),
                                        # POS filter options
                                        html.Div(
                                            id="pos-filter-tab",
                                            children=pos_filter_options,
                                            style=hideDiv,
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                    # Interval to update data
                    html.Div(
                        id="interval-component-div",
                        style={"display": "none"},
                        children=[
                            html.H1(id="number-out", children=""),
                            dcc.Interval(
                                id="interval-component",
                                interval=(60 * 10) * 1000,  # Every 10 minutes
                                n_intervals=0,
                            ),
                        ],
                    ),
                    # Submit button TAG
                    get_submit_btn_div("tag", style=showDiv),
                    # Submit button TBR
                    get_submit_btn_div("tbr", style=hideDiv),
                    # Submit button POS
                    get_submit_btn_div("pos", style=hideDiv),
                ],
            ),
        ],
    )


app.layout = app_page_layout(
    page_layout=layout_test(),
    app_title="Internet of Fish",
    app_name="Aquatraz",
    standalone=True,
    **header_colors(),
)


# *-----------------------------*
# | FUNCTIONS USED BY CALLBACKS |
# *-----------------------------*


def tag_dropdown_options(cage, dataType=None, frequencies=[]):
    # Get possible cage tags
    cageTags = {"All": all_tags, "Aquatraz": aqz_tags, "Reference": ref_tags}
    tags = cageTags[cage]

    # Get possible data type tags. If no datatype, keep previous list of possible tags
    typeTags = {
        "All": list(set(tags).intersection(all_tags)),
        "depth": list(set(tags).intersection(depth_tags)),
        "acc": list(set(tags).intersection(acc_tags)),
    }
    tags = typeTags.get(dataType, tags)

    # Get possible frequency tags
    freqTags = {69: list(tag_freq_69), 71: list(tag_freq_71), 73: list(tag_freq_73)}
    freq = []
    for frequency in frequencies:
        freq += freqTags[frequency]
    tags = list(set(tags).intersection(freq))

    # Pack possible tags into options list and return with tags
    options = [{"label": f"tag {i}", "value": i} for i in tags]
    return options, tags


def cage_tbr_dropdown(cage):
    cageTbrs = {"All": all_tbrs, "Aquatraz": aqz_tbrs, "Reference": ref_tbrs}
    tbrs = cageTbrs[cage]
    options = [{"label": f"tbr {i}", "value": i} for i in tbrs]
    return options, tbrs


def empty_tags_selection(cage, dataType, frequencies):
    defaultTags = {
        "acc": {"Aquatraz": {69: [11, 0]}, "Reference": {69: [51, 0]}},
        "depth": {
            "Aquatraz": {69: [10, 0], 71: [97, 0], 73: [102, 0]},
            "All": {69: [10, 0], 71: [97, 0], 73: [102, 0]},
            "Reference": {69: [50, 0], 71: [107, 0], 73: [116, 0]},
        },
    }
    return defaultTags[dataType][cage][min(frequencies)]


def update_plasma_df(type):
    df = read_from_plasma(type)
    ts = max(df["timestamp"])
    df_new = clean_data(ts, type)
    if df_new.empty:
        print(f"no new data, not updating plasma {type} data")
    else:
        dff = pd.concat([df, df_new])
        print(f"Writing to plasma update {type} data")
        write_to_plasma(dff, type)


def get_time_of_day(hour, minute, second):
    return f"{hour}:{minute}:{second}"


# *--------------------------------------*
# | SWITCHING BETWEEN DATA SETS CALLBACK |
# *--------------------------------------*


@app.callback(
    [
        Output("tag-graph-div", "style"),
        Output("tbr-graph-div", "style"),
        Output("pos-graph-div", "style"),
        Output("tag-submit-button-div", "style"),
        Output("tbr-submit-button-div", "style"),
        Output("pos-submit-button-div", "style"),
        Output("tag-filter-tab", "style"),
        Output("tbr-filter-tab", "style"),
        Output("pos-filter-tab", "style"),
        Output("tag-plot-tab", "style"),
        Output("tbr-plot-tab", "style"),
        Output("pos-plot-tab", "style"),
    ],
    [Input("data-set-selection-dropdown", "value")],
)
def change_active_data_set_and_graph_tab(datatype):
    hide, show = {"display": "none"}, {"display": "inline-block"}
    tag_style, tbr_style, pos_style = (hide, hide, hide)
    tag_btn, tbr_btn, pos_btn = (hide, hide, hide)

    if datatype == "tag":
        tag_style, tag_btn = show, show
    elif datatype == "tbr":
        tbr_style, tbr_btn = show, show
    elif datatype == "pos":
        pos_style, pos_btn = show, show
    return (
        tag_style,
        tbr_style,
        pos_style,
        tag_btn,
        tbr_btn,
        pos_btn,
        tag_style,
        tbr_style,
        pos_style,
        tag_style,
        tbr_style,
        pos_style,
    )


# *------------------------------*
# | GLOBAL DATA UPDATE CALLBACKS |
# *------------------------------*


# Update Plasma Store dataframe
@app.callback(
    Output("number-out", "children"), [Input("interval-component", "n_intervals")]
)
def update_global_data(n):
    update_plasma_df("tag")
    update_plasma_df("tbr")
    update_plasma_df("pos")
    return ""


# *------------------------------*
# | TAG DATA FILTERING CALLBACKS |
# *------------------------------*

# START DATE BTN UPDATE
@app.callback(
    Output("tag-date-picker-range", "start_date"),
    [Input("tag-start-date-btn", "n_clicks")],
)
def set_tag_start_date(n_clicks):
    if n_clicks is None:
        return dt.strftime(dt.today() - timedelta(days=30), "%Y-%m-%d")
    return dt.strftime(dt.fromtimestamp(start_project_time), "%Y-%m-%d")


# END DATE BTN UPDATE
@app.callback(
    Output("tag-date-picker-range", "end_date"), [Input("tag-end-date-btn", "n_clicks")]
)
def set_tag_end_date(_):
    return dt.today()


# ENABLE/DISABLE TIME OF DAY FILTERING
@app.callback(
    [
        Output("tag-time-picker-div", "style"),
        Output("tag-start-hour-picker", "value"),
        Output("tag-start-minute-picker", "value"),
        Output("tag-start-second-picker", "value"),
        Output("tag-end-hour-picker", "value"),
        Output("tag-end-minute-picker", "value"),
        Output("tag-end-second-picker", "value"),
    ],
    [Input("tag-time-switch", "on")],
)
def tag_update_time_picker_div(switch):
    if switch:
        style = {"display": "inline-block"}
    else:
        style = {"display": "none"}
    return style, 0, 0, 0, 23, 59, 59


# TBR CAGE DROPDOWN
@app.callback(
    [Output("tag-tbr-dropdown", "options"), Output("tag-tbr-dropdown", "value")],
    [Input("tag-cage-tbr-dropdown", "value")],
)
def update_tag_cage_tbr_dropdown(tbr_cage):
    return cage_tbr_dropdown(tbr_cage)


# TAG ID DROPDOWN
@app.callback(
    [Output("tag-tag-id-dropdown", "options"), Output("tag-tag-id-dropdown", "value")],
    [
        Input("tag-cage-tag-dropdown", "value"),
        Input("tag-data-type-dropdown", "value"),
        Input("tag-tag-frequency-dropdown", "value"),
    ],
    [State("tag-tag-id-dropdown", "value")],
)
def update_tag_tag_id_dropdown(tagsCage, tagsType, frequencies, selected):
    options, validTags = tag_dropdown_options(tagsCage, tagsType, frequencies)
    tags = list(set(selected).intersection(validTags))
    if frequencies and not tags:
        tags = empty_tags_selection(tagsCage, tagsType, frequencies)
    return options, tags


# SNR SLIDER
@app.callback(Output("snr-values", "children"), [Input("tag-snr-rangeslider", "value")])
def show_snr_filter_values(value):
    return f"[{value[0]}, {value[1]}]"


# *------------------------------*
# | TBR DATA FILTERING CALLBACKS |
# *------------------------------*

# START DATE BTN UPDATE
@app.callback(
    Output("tbr-date-picker-range", "start_date"),
    [Input("tbr-start-date-btn", "n_clicks")],
)
def set_tbr_start_date(n_clicks):
    if n_clicks is None:
        return dt.strftime(dt.today() - timedelta(days=30), "%Y-%m-%d")
    return dt.strftime(dt.fromtimestamp(start_project_time), "%Y-%m-%d")


# END DATE BTN UPDATE
@app.callback(
    Output("tbr-date-picker-range", "end_date"), [Input("tbr-end-date-btn", "n_clicks")]
)
def set_tbr_end_date(_):
    return dt.today()


# ENABLE/DISABLE TIME OF DAY FILTERING
@app.callback(
    [
        Output("tbr-time-picker-div", "style"),
        Output("tbr-start-hour-picker", "value"),
        Output("tbr-start-minute-picker", "value"),
        Output("tbr-start-second-picker", "value"),
        Output("tbr-end-hour-picker", "value"),
        Output("tbr-end-minute-picker", "value"),
        Output("tbr-end-second-picker", "value"),
    ],
    [Input("tbr-time-switch", "on")],
)
def tbr_update_time_picker_div(switch):
    if switch:
        style = {"display": "inline-block"}
    else:
        style = {"display": "none"}
    return style, 0, 0, 0, 23, 59, 59


# TBR ID DROPDOWN
@app.callback(
    [Output("tbr-tbr-dropdown", "options"), Output("tbr-tbr-dropdown", "value")],
    [Input("tbr-cage-tbr-dropdown", "value")],
)
def update_tbr_cage_tbr_dropdown(tbr_cage):
    return cage_tbr_dropdown(tbr_cage)


# TBR SLIDERS (TEMPERATURE / NOISE AVG / NOISE PEAK)
@app.callback(
    [
        Output("temperature-values", "children"),
        Output("amb-avg-noise-values", "children"),
        Output("amb-peak-noise-values", "children"),
    ],
    [
        Input("tbr-temperature-rangeslider", "value"),
        Input("tbr-amb-avg-noise-rangeslider", "value"),
        Input("tbr-amb-peak-noise-rangeslider", "value"),
    ],
)
def tbr_slider_filters_temp_noise(temp, avg, peak):
    return f"[{temp[0]}, {temp[1]}]", f"[{avg[0]}, {avg[1]}]", f"[{peak[0]}, {peak[1]}]"


# *------------------------------*
# | POS DATA FILTERING CALLBACKS |
# *------------------------------*

# START DATE BTN UPDATE
@app.callback(
    Output("pos-date-picker-range", "start_date"),
    [Input("pos-start-date-btn", "n_clicks")],
)
def set_pos_start_date(n_clicks):
    if n_clicks is None:
        return dt.strftime(dt.today() - timedelta(days=30), "%Y-%m-%d")
    return dt.strftime(dt.fromtimestamp(start_project_time), "%Y-%m-%d")


# END DATE BTN UPDATE
@app.callback(
    Output("pos-date-picker-range", "end_date"), [Input("pos-end-date-btn", "n_clicks")]
)
def set_pos_end_date(_):
    return dt.today()


# ENABLE/DISABLE TIME OF DAY FILTERING
@app.callback(
    [
        Output("pos-time-picker-div", "style"),
        Output("pos-start-hour-picker", "value"),
        Output("pos-start-minute-picker", "value"),
        Output("pos-start-second-picker", "value"),
        Output("pos-end-hour-picker", "value"),
        Output("pos-end-minute-picker", "value"),
        Output("pos-end-second-picker", "value"),
    ],
    [Input("pos-time-switch", "on")],
)
def pos_update_time_picker_div(switch):
    if switch:
        style = {"display": "inline-block"}
    else:
        style = {"display": "none"}
    return style, 0, 0, 0, 23, 59, 59


# TAG ID DROPDOWN
@app.callback(
    [Output("pos-tag-id-dropdown", "options"), Output("pos-tag-id-dropdown", "value")],
    [
        Input("pos-cage-tag-dropdown", "value"),
        Input("pos-tag-frequency-dropdown", "value"),
    ],
    [State("pos-tag-id-dropdown", "value")],
)
def update_pos_tag_id_dropdown(tagsCage, frequencies, selected):
    options, validTags = tag_dropdown_options(tagsCage, "depth", frequencies)
    tags = list(set(selected).intersection(validTags))
    if frequencies and not tags:
        tags = empty_tags_selection(tagsCage, "depth", frequencies)
    return options, tags


# *--------------------*
# | PLOT TAB CALLBACKS |
# *--------------------*


@app.callback(
    [
        Output("tag-scatter-options-selection-dropdown", "disabled"),
        Output("tag-boxplot-options-selection-dropdown", "disabled"),
        Output(f"tag-plot-marker-size", "disabled"),
        Output(f"tag-plot-marker-opacity", "disabled"),
        Output(f"tag-plot-line-width", "disabled"),
        Output(f"tag-plot-line-dash", "disabled"),
    ],
    [Input("tag-plot-type-selection-dropdown", "value")],
)
def disable_enable_tag_plot_options(plotType):
    scat, box, mSize, mOpac, lWidth, lDash = [True] * 6
    if plotType == "boxplot":
        box = False
    elif plotType in ("scatter", "scatter3d", "scatter3d_animation"):
        scat, mSize, mOpac, lWidth, lDash = [False] * 5
    return scat, box, mSize, mOpac, lWidth, lDash


@app.callback(
    [
        Output("tbr-scatter-options-selection-dropdown", "disabled"),
        Output("tbr-boxplot-options-selection-dropdown", "disabled"),
        Output(f"tbr-plot-marker-size", "disabled"),
        Output(f"tbr-plot-marker-opacity", "disabled"),
        Output(f"tbr-plot-line-width", "disabled"),
        Output(f"tbr-plot-line-dash", "disabled"),
    ],
    [Input("tbr-plot-type-selection-dropdown", "value")],
)
def disable_enable_tbr_plot_options(plotType):
    scat, box, mSize, mOpac, lWidth, lDash = [True] * 6
    if plotType == "boxplot":
        box = False
    elif plotType in ("scatter", "scatter3d", "scatter3d_animation"):
        scat, mSize, mOpac, lWidth, lDash = [False] * 5
    return scat, box, mSize, mOpac, lWidth, lDash


@app.callback(
    [
        Output("pos-scatter-options-selection-dropdown", "disabled"),
        Output("pos-boxplot-options-selection-dropdown", "disabled"),
        Output(f"pos-plot-marker-size", "disabled"),
        Output(f"pos-plot-marker-opacity", "disabled"),
        Output(f"pos-plot-line-width", "disabled"),
        Output(f"pos-plot-line-dash", "disabled"),
    ],
    [Input("pos-plot-type-selection-dropdown", "value")],
)
def disable_enable_pos_plot_options(plotType):
    scat, box, mSize, mOpac, lWidth, lDash = [True] * 6
    if plotType == "boxplot":
        box = False
    elif plotType in ("scatter", "scatter3d", "scatter3d_animation"):
        scat, mSize, mOpac, lWidth, lDash = [False] * 5
    return scat, box, mSize, mOpac, lWidth, lDash


@app.callback(
    [Output("tag-x-axis-selection-dropdown", "disabled")],
    [Input("tag-enable-timeseries", "on")],
)
def tag_enable_timeseries(switch):
    if switch:
        xAxis = True
    else:
        xAxis = False
    return [xAxis]


@app.callback(
    [Output("tbr-x-axis-selection-dropdown", "disabled")],
    [Input("tbr-enable-timeseries", "on")],
)
def tbr_enable_timeseries(switch):
    if switch:
        xAxis = True
    else:
        xAxis = False
    return [xAxis]


@app.callback(
    [Output("pos-x-axis-selection-dropdown", "disabled")],
    [Input("pos-enable-timeseries", "on")],
)
def pos_enable_timeseries(switch):
    if switch:
        xAxis = True
    else:
        xAxis = False
    return [xAxis]


def get_axis_options_from_plot_type(axisOptions, plotType, xAxis):
    disableY, disableZ = False, True
    if plotType == "scatter":
        pass
    elif plotType == "scatter3d":
        disableZ = False
    elif plotType == "histogram":
        disableY = True
    elif plotType == "histogram2d":
        pass
    elif plotType == "boxplot":
        axOptions = list(axisOptions)
        # Remove Date and Timestamp as valid axis options for boxplot
        axOptions = axOptions[2:]
        axisOptions = axOptions
        xAxis = "hour"
    else:
        pass
    return (axisOptions, axisOptions, axisOptions, xAxis, disableY, disableZ)


@app.callback(
    [
        Output("tag-x-axis-selection-dropdown", "options"),
        Output("tag-y-axis-selection-dropdown", "options"),
        Output("tag-z-axis-selection-dropdown", "options"),
        Output("tag-x-axis-selection-dropdown", "value"),
        Output("tag-y-axis-selection-dropdown", "disabled"),
        Output("tag-z-axis-selection-dropdown", "disabled"),
    ],
    [Input("tag-plot-type-selection-dropdown", "value")],
    [State("tag-x-axis-selection-dropdown", "value")],
)
def update_tag_plot_options(plotType, xAxis):
    axisOptions = tag_axis_options
    return get_axis_options_from_plot_type(axisOptions, plotType, xAxis)


@app.callback(
    [
        Output("tbr-x-axis-selection-dropdown", "options"),
        Output("tbr-y-axis-selection-dropdown", "options"),
        Output("tbr-z-axis-selection-dropdown", "options"),
        Output("tbr-x-axis-selection-dropdown", "value"),
        Output("tbr-y-axis-selection-dropdown", "disabled"),
        Output("tbr-z-axis-selection-dropdown", "disabled"),
    ],
    [Input("tbr-plot-type-selection-dropdown", "value")],
    [State("tbr-x-axis-selection-dropdown", "value")],
)
def update_tbr_plot_options(plotType, xAxis):
    axisOptions = tbr_axis_options
    return get_axis_options_from_plot_type(axisOptions, plotType, xAxis)


@app.callback(
    [
        Output("pos-x-axis-selection-dropdown", "options"),
        Output("pos-y-axis-selection-dropdown", "options"),
        Output("pos-z-axis-selection-dropdown", "options"),
        Output("pos-x-axis-selection-dropdown", "value"),
        Output("pos-y-axis-selection-dropdown", "disabled"),
        Output("pos-z-axis-selection-dropdown", "disabled"),
    ],
    [Input("pos-plot-type-selection-dropdown", "value")],
    [State("pos-x-axis-selection-dropdown", "value")],
)
def update_plot_options(plotType, xAxis):
    axisOptions = pos_axis_options
    return get_axis_options_from_plot_type(axisOptions, plotType, xAxis)


def get_grid_pos(df, numPoints=10):
    times = df["timestamp"].unique()

    # Make the grid
    grid = pd.DataFrame()
    grid2 = pd.DataFrame()
    col_name_template = "{time}+{header}_grid"
    for i, tstamp in enumerate(times):
        if i < numPoints:
            df_by_time = df.iloc[0 : i + 1]
        else:
            df_by_time = df.iloc[i + 1 - numPoints : i + 1]
        for col in ["x", "y", "z"]:
            temp = col_name_template.format(time=tstamp, header=col)
            if df_by_time[col].size != 0:
                grid = grid.append(
                    {"value": list(df_by_time[col]), "key": temp}, ignore_index=True
                )
                grid2 = grid2.append(
                    {"value": list(df.iloc[i : i + 1][col]), "key": temp},
                    ignore_index=True,
                )
    return [grid, grid2]


def get_grid_tbr(df):
    dates = df["Date_str"].str.slice(0, 10, 1).unique()

    # Make the grid
    grid = pd.DataFrame()
    col_name_template = "{date}+{header}_grid"
    for date in dates:
        df_by_date = df[df.Date_str.str.contains(date)]
        for col in ["hour", "noise_avg"]:
            temp = col_name_template.format(date=date, header=col)
            if df_by_date[col].size != 0:
                grid = grid.append(
                    {"value": list(df_by_date[col]), "key": temp}, ignore_index=True
                )
    print("GRID")
    print(grid)
    return grid


def get_plot_data(dataset, dff, type, xAxis, yAxis, zAxis, mode, marker, line):
    traceKeys = {"tag": "tag_id", "tbr": "tbr_serial_id", "pos": "tag_id"}
    traceNames = {"tag": "tag", "tbr": "tbr", "pos": "tag"}
    traceKey, traceName = traceKeys[dataset], traceNames[dataset]
    if type == "scatter":
        data = [
            go.Scattergl(
                x=dff[dff[traceKey] == id][xAxis],
                y=dff[dff[traceKey] == id][yAxis],
                name=f"{traceName} {id}",
                mode=mode,
                marker=marker,
                line=line,
            )
            for id in dff[traceKey].unique()
        ]
    elif type == "scatter_ikke":
        data = [
            go.Scatter(
                x=dff[dff[traceKey] == id][xAxis],
                y=dff[dff[traceKey] == id][yAxis],
                name=f"{traceName} {id}",
                mode=mode,
                marker=marker,
                line=line,
            )
            for id in dff[traceKey].unique()
        ]
    elif type == "scatter3d":
        data = [
            go.Scatter3d(
                x=dff[dff[traceKey] == id][xAxis],
                y=dff[dff[traceKey] == id][yAxis],
                z=dff[dff[traceKey] == id][zAxis],
                mode=mode,
                name=f"{traceName} {id}",
                marker=marker,
                line=line,
            )
            for id in dff[traceKey].unique()
        ]
    elif type == "scatter3d_animation":
        data = get_grid_pos(dff)
    elif type == "histogram":
        data = [
            go.Histogram(x=dff[dff[traceKey] == id][xAxis], name=f"{traceName} {id}")
            for id in dff[traceKey].unique()
        ]
    elif type == "histogram2d":
        data = [go.Histogram2d(x=dff[xAxis], y=dff[yAxis])]
    elif type == "histogram2dcontour":
        data = [go.Histogram2dContour(x=dff[xAxis], y=dff[yAxis])]
    elif type == "histogram2dcontour_animation":
        data = get_grid_tbr(dff)
    elif type == "boxplot":
        data = [
            go.Box(
                x=dff[dff[traceKey] == id][xAxis],
                y=dff[dff[traceKey] == id][yAxis],
                name=f"{dataset} {id}",
            )
            for id in dff[traceKey].unique()
        ]
    else:
        data = []
    return data


def get_plot_layout(xAxis, yAxis, zAxis, plotType, boxMode):
    if plotType == "boxplot":
        layout = go.Layout(
            title=plotLabels[plotType],
            boxmode=boxMode,
            xaxis=dict(title=axisLabels[xAxis]),
            yaxis=dict(title=axisLabels[yAxis]),
        )
    elif plotType == "histogram":
        layout = go.Layout(
            title=plotLabels[plotType],
            xaxis=dict(title=axisLabels[xAxis]),
            yaxis=dict(title="Frequency"),
        )
    elif plotType == "scatter3d":
        layout = go.Layout(
            title=plotLabels[plotType],
            scene=dict(
                xaxis=dict(title=axisLabels[xAxis]),
                yaxis=dict(title=axisLabels[yAxis]),
                zaxis=dict(title=axisLabels[zAxis]),
            ),
        )
    else:
        layout = go.Layout(
            title=plotLabels[plotType],
            xaxis=dict(title=axisLabels[xAxis]),
            yaxis=dict(title=axisLabels[yAxis]),
        )
    return layout


def get_marker_line(markerSize, markerOpacity, lineWidth, lineDash):
    marker = {"size": markerSize, "opacity": markerOpacity}
    line = {"width": lineWidth, "dash": lineDash}
    return marker, line


# *------------------------------------------------*
# | PLOTTING FIGURES CALLBACKS FOR TAG / TBR / POS |
# *------------------------------------------------*


@app.callback(
    Output("tag-graph", "figure"),
    [Input("tag-submit-button", "n_clicks")],
    [
        State("tag-date-picker-range", "start_date"),
        State("tag-date-picker-range", "end_date"),
        State("tag-start-hour-picker", "value"),
        State("tag-start-minute-picker", "value"),
        State("tag-start-second-picker", "value"),
        State("tag-end-hour-picker", "value"),
        State("tag-end-minute-picker", "value"),
        State("tag-end-second-picker", "value"),
        State("tag-tbr-dropdown", "value"),
        State("tag-tag-id-dropdown", "value"),
        State("tag-snr-rangeslider", "value"),
        # PLOT OPTIONS
        State("tag-plot-type-selection-dropdown", "value"),
        State("tag-x-axis-selection-dropdown", "value"),
        State("tag-y-axis-selection-dropdown", "value"),
        State("tag-z-axis-selection-dropdown", "value"),
        State("tag-scatter-options-selection-dropdown", "value"),
        State("tag-boxplot-options-selection-dropdown", "value"),
        State("tag-plot-marker-size", "value"),
        State("tag-plot-marker-opacity", "value"),
        State("tag-plot-line-width", "value"),
        State("tag-plot-line-dash", "value"),
        State("tag-enable-timeseries", "on"),
    ],
)
def update_tag_graph(
    n_clicks,
    start_date,
    end_date,
    start_hour,
    start_min,
    start_sec,
    end_hour,
    end_min,
    end_sec,
    tbrs,
    tags,
    snr,
    plotType,
    xAxis,
    yAxis,
    zAxis,
    scatterMode,
    boxMode,
    markerSize,
    markerOpacity,
    lineWidth,
    lineDash,
    timeseries,
):
    # Read global dataframe from plasma store
    marker, line = get_marker_line(markerSize, markerOpacity, lineWidth, lineDash)
    df = read_from_plasma("tag")
    print(f"Plasma TAG")

    if timeseries:
        xAxis = "Date_str"

    # Filter dataframe
    start_time = get_time_of_day(start_hour, start_min, start_sec)
    end_time = get_time_of_day(end_hour, end_min, end_sec)
    dff = df.loc[start_date:end_date]
    dff = dff.between_time(start_time, end_time)
    dff = dff[dff["tbr_serial_id"].isin(tbrs)]
    dff = dff[dff["tag_id"].isin(tags)]
    dff = dff[dff.snr.between(snr[0], snr[1])]
    if xAxis != "millisecond" and yAxis != "millisecond":
        dff = dff.drop_duplicates(subset=["timestamp", "tag_id"], keep="first")
    print(f"Filter TAG")

    # Get data and layout and make figure
    data = get_plot_data(
        "tag", dff, plotType, xAxis, yAxis, zAxis, scatterMode, marker, line
    )
    layout = get_plot_layout(xAxis, yAxis, zAxis, plotType, boxMode)
    print(f"Data TAG")
    if timeseries:
        layout["xaxis"] = timeseries_xaxis_dict
    fig = {"data": data, "layout": layout}
    return fig


def get_animation_tbr_fig(grid, tstamps, dates, tags):
    fig = {"data": [], "layout": {}, "frames": []}
    date = min(dates)
    col_name_template = "{date}+{header}_grid"

    # Create initial trace and cage traces
    trace = {
        "x": grid.loc[
            grid["key"] == col_name_template.format(date=date, header="hour"), "value"
        ].values[0],
        "y": grid.loc[
            grid["key"] == col_name_template.format(date=date, header="noise_avg"),
            "value",
        ].values[0],
        "type": "histogram2d",
        "nbinsx": 24,
    }
    fig["data"].append(trace)

    # Modify the layout
    fig["layout"]["xaxis"] = {"title": "Hour of day", "range": [0, 24]}
    fig["layout"]["yaxis"] = {"title": "Average Ambient Noise", "range": [0, 75]}
    fig["layout"]["title"] = f"Average ambient noise per day over time"
    fig["layout"]["showlegend"] = False
    fig["layout"]["hovermode"] = "closest"
    fig["layout"]["sliders"] = {
        "args": ["slider.value", {"duration": 600, "ease": "cubic-in-out"}],
        "initialValue": date,
        "plotlycommand": "animate",
        "values": dates,
        "visible": True,
    }
    sliders_dict = {
        "active": 0,
        "yanchor": "top",
        "xanchor": "left",
        "currentvalue": {
            "font": {"size": 20},
            "prefix": "Date: ",
            "visible": True,
            "xanchor": "right",
        },
        "transition": {"duration": 500, "easing": "cubic-in-out"},
        "pad": {"b": 10, "t": 50},
        "len": 0.9,
        "x": 0.1,
        "y": 0,
        "steps": [],
    }

    for date in dates:
        # Make a frame for each timestamp
        frame = {"data": [], "name": date}

        # Make a trace for each frame
        trace = {
            "x": grid.loc[
                grid["key"] == col_name_template.format(date=date, header="hour"),
                "value",
            ].values[0],
            "y": grid.loc[
                grid["key"] == col_name_template.format(date=date, header="noise_avg"),
                "value",
            ].values[0],
            "type": "histogram2d",
            "nbinsx": 24,
        }

        # Add traces to the frame
        frame["data"].append(trace)
        fig["frames"].append(frame)

        slider_step = {
            "args": [
                [date],
                {
                    "frame": {"duration": 100, "redraw": True},
                    "mode": "immediate",
                    "transition": {"duration": 100},
                },
            ],
            "label": date,
            "method": "animate",
        }
        sliders_dict["steps"].append(slider_step)

    fig["layout"]["sliders"] = [sliders_dict]

    # Add play/pause button to figure
    fig["layout"]["updatemenus"] = [
        {
            "buttons": [
                {
                    "args": [
                        None,
                        {
                            "frame": {"duration": 500, "redraw": True},
                            "fromcurrent": True,
                            "transition": {
                                "duration": 400,
                                "easing": "quadratic-in-out",
                            },
                        },
                    ],
                    "label": "Play",
                    "method": "animate",
                },
                {
                    "args": [
                        [None],
                        {
                            "frame": {"duration": 0, "redraw": True},
                            "mode": "immediate",
                            "transition": {"duration": 0},
                        },
                    ],
                    "label": "Pause",
                    "method": "animate",
                },
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top",
        }
    ]

    return fig


@app.callback(
    Output("tbr-graph", "figure"),
    [Input("tbr-submit-button", "n_clicks")],
    [
        # FILTERS
        State("tbr-date-picker-range", "start_date"),
        State("tbr-date-picker-range", "end_date"),
        State("tbr-start-hour-picker", "value"),
        State("tbr-start-minute-picker", "value"),
        State("tbr-start-second-picker", "value"),
        State("tbr-end-hour-picker", "value"),
        State("tbr-end-minute-picker", "value"),
        State("tbr-end-second-picker", "value"),
        State("tbr-cage-tbr-dropdown", "value"),
        State("tbr-tbr-dropdown", "value"),
        State("tbr-temperature-rangeslider", "value"),
        State("tbr-amb-avg-noise-rangeslider", "value"),
        State("tbr-amb-peak-noise-rangeslider", "value"),
        # PLOT OPTIONS
        State("tbr-plot-type-selection-dropdown", "value"),
        State("tbr-x-axis-selection-dropdown", "value"),
        State("tbr-y-axis-selection-dropdown", "value"),
        State("tbr-z-axis-selection-dropdown", "value"),
        State("tbr-scatter-options-selection-dropdown", "value"),
        State("tbr-boxplot-options-selection-dropdown", "value"),
        State("tbr-plot-marker-size", "value"),
        State("tbr-plot-marker-opacity", "value"),
        State("tbr-plot-line-width", "value"),
        State("tbr-plot-line-dash", "value"),
        State("tbr-enable-timeseries", "on"),
    ],
)
def update_tbr_graph(
    _,
    start_date,
    end_date,
    start_hour,
    start_min,
    start_sec,
    end_hour,
    end_min,
    end_sec,
    tbr_cage,
    tbrs,
    temp,
    avg,
    peak,
    plotType,
    xAxis,
    yAxis,
    zAxis,
    scatterMode,
    boxMode,
    markerSize,
    markerOpacity,
    lineWidth,
    lineDash,
    timeseries,
):
    marker, line = get_marker_line(markerSize, markerOpacity, lineWidth, lineDash)

    # Read global dataframe from plasma store
    df = read_from_plasma("tbr")
    print(f"Plasma TBR")

    # Filter dataframe
    start_time = get_time_of_day(start_hour, start_min, start_sec)
    end_time = get_time_of_day(end_hour, end_min, end_sec)
    dff = df.loc[start_date:end_date]
    dff = dff.between_time(start_time, end_time)
    dff = dff[dff["tbr_serial_id"].isin(tbrs)]
    dff = dff[dff.temperature.between(temp[0], temp[1])]
    dff = dff[dff.noise_avg.between(avg[0], avg[1])]
    dff = dff[dff.noise_peak.between(peak[0], peak[1])]
    print(f"Filter TBR")
    data = get_plot_data(
        "tbr", dff, plotType, xAxis, yAxis, zAxis, scatterMode, marker, line
    )
    layout = get_plot_layout(xAxis, yAxis, zAxis, plotType, boxMode)
    print(f"Data TBR")
    if plotType == "histogram2dcontour_animation":
        times = dff["hour"].unique()
        dates = dff["Date_str"].str.slice(0, 10, 1).unique()
        fig = get_animation_tbr_fig(data, times, dates, tbrs)
    else:
        fig = {"data": data, "layout": layout}
    return fig


def get_animation_fig(grids, tstamps, dates, tags, date, cage):
    fig = {"data": [], "layout": {}, "frames": []}
    tstamp = min(tstamps)
    grid, grid2 = grids
    tag_id = tags[0]
    col_name_template = "{time}+{header}_grid"

    # Create initial trace and cage traces
    trace = {
        "x": grid.loc[
            grid["key"] == col_name_template.format(time=tstamp, header="x"), "value"
        ].values[0],
        "y": grid.loc[
            grid["key"] == col_name_template.format(time=tstamp, header="y"), "value"
        ].values[0],
        "z": grid.loc[
            grid["key"] == col_name_template.format(time=tstamp, header="z"), "value"
        ].values[0],
        "mode": "markers+lines",
        "type": "scatter3d",
        "marker": {"opacity": 0.5},
        "name": f"tag {tag_id}",
    }
    fig["data"].append(trace)
    if cage == "Aquatraz":
        if date > dt.strptime("2019-05-10", "%Y-%m-%d"):
            for trace in aq_cage_new.traces:
                fig["data"].append(trace)
        else:
            for trace in aq_cage.traces:
                fig["data"].append(trace)
    elif cage == "Reference":
        for trace in ref_cage.traces:
            fig["data"].append(trace)
    else:
        if date > dt.strptime("2019-05-10", "%Y-%m-%d"):
            for trace1, trace2 in zip(aq_cage_new.traces, ref_cage.traces):
                fig["data"].append(trace1)
                fig["data"].append(trace2)
        else:
            for trace1, trace2 in zip(aq_cage.traces, ref_cage.traces):
                fig["data"].append(trace1)
                fig["data"].append(trace2)

    # AQ: (21.14, 12.45) | AQ-NEW (19.81, 18.79) | REF (21.19, 13.27)
    if (cage in ("Aquatraz", "All")) and (date > dt.strptime("2019-05-10", "%Y-%m-%d")):
        xrange, yrange, zrange = ([20 - 40, 20 + 40], [19 - 40, 19 + 40], [-40, 0])
    elif cage == "Aquatraz":
        xrange, yrange, zrange = ([21 - 40, 21 + 40], [13 - 40, 13 + 40], [-40, 0])
    elif cage == "Reference":
        xrange, yrange, zrange = ([21 - 40, 21 + 40], [13 - 40, 13 + 40], [-40, 0])
    else:
        xrange, yrange, zrange = ([21 - 40, 21 + 40], [13 - 40, 13 + 40], [-40, 0])
    fig["layout"]["scene"] = {}
    fig["layout"]["scene"]["xaxis"] = {"title": "X [m]", "autorange": False}
    fig["layout"]["scene"]["yaxis"] = {"title": "Y [m]", "autorange": False}
    fig["layout"]["scene"]["zaxis"] = {"title": "Z [m]", "autorange": False}
    fig["layout"]["scene"]["xaxis"]["range"] = xrange
    fig["layout"]["scene"]["yaxis"]["range"] = yrange
    fig["layout"]["scene"]["zaxis"]["range"] = zrange
    fig["layout"]["title"] = f"3D fish (tag {tag_id}) position animation"
    fig["layout"]["showlegend"] = False
    fig["layout"]["hovermode"] = "closest"
    fig["layout"]["sliders"] = {
        "args": ["slider.value", {"duration": 400, "ease": "cubic-in-out"}],
        "initialValue": tstamp,
        "plotlycommand": "animate",
        "values": tstamps,
        "visible": True,
    }
    sliders_dict = {
        "active": 0,
        "yanchor": "top",
        "xanchor": "left",
        "currentvalue": {
            "font": {"size": 20},
            "prefix": "Time: ",
            "visible": True,
            "xanchor": "right",
        },
        "transition": {"duration": 300, "easing": "cubic-in-out"},
        "pad": {"b": 10, "t": 50},
        "len": 0.9,
        "x": 0.1,
        "y": 0,
        "steps": [],
    }

    for i, tstamp in enumerate(tstamps):
        # Make a frame for each timestamp
        frame = {"data": [], "name": str(tstamp)}

        # Make a trace for each frame
        trace = {
            "x": grid.loc[
                grid["key"] == col_name_template.format(time=tstamp, header="x"),
                "value",
            ].values[0],
            "y": grid.loc[
                grid["key"] == col_name_template.format(time=tstamp, header="y"),
                "value",
            ].values[0],
            "z": grid.loc[
                grid["key"] == col_name_template.format(time=tstamp, header="z"),
                "value",
            ].values[0],
            "mode": "markers+lines",
            "type": "scatter3d",
            "marker": {"opacity": 0.5},
        }
        trace_now = {
            "x": grid2.loc[
                grid2["key"] == col_name_template.format(time=tstamp, header="x"),
                "value",
            ].values[0],
            "y": grid2.loc[
                grid2["key"] == col_name_template.format(time=tstamp, header="y"),
                "value",
            ].values[0],
            "z": grid2.loc[
                grid2["key"] == col_name_template.format(time=tstamp, header="z"),
                "value",
            ].values[0],
            "mode": "markers+lines",
            "type": "scatter3d",
            "marker": {"color": "orange"},
        }

        # Add traces to the frame
        frame["data"].append(trace)
        frame["data"].append(trace_now)
        fig["frames"].append(frame)

        slider_step = {
            "args": [
                [tstamp],
                {
                    "frame": {"duration": 100, "redraw": False},
                    "mode": "immediate",
                    "transition": {"duration": 100},
                },
            ],
            "label": dates[i],
            "method": "animate",
        }
        sliders_dict["steps"].append(slider_step)

    fig["layout"]["sliders"] = [sliders_dict]

    # Add play/pause button to figure
    fig["layout"]["updatemenus"] = [
        {
            "buttons": [
                {
                    "args": [
                        None,
                        {
                            "frame": {"duration": 500, "redraw": False},
                            "fromcurrent": True,
                            "transition": {
                                "duration": 300,
                                "easing": "quadratic-in-out",
                            },
                        },
                    ],
                    "label": "Play",
                    "method": "animate",
                },
                {
                    "args": [
                        [None],
                        {
                            "frame": {"duration": 0, "redraw": False},
                            "mode": "immediate",
                            "transition": {"duration": 0},
                        },
                    ],
                    "label": "Pause",
                    "method": "animate",
                },
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top",
        }
    ]

    return fig


@app.callback(
    Output("pos-confirm-3d-animation", "displayed"),
    [Input("pos-plot-type-selection-dropdown", "value")],
)
def warn_user_3d_pos_animation(plotType):
    if plotType == "scatter3d_animation":
        return True
    return False


@app.callback(
    Output("pos-graph", "figure"),
    [Input("pos-submit-button", "n_clicks")],
    [
        State("pos-date-picker-range", "start_date"),
        State("pos-date-picker-range", "end_date"),
        State("pos-start-hour-picker", "value"),
        State("pos-start-minute-picker", "value"),
        State("pos-start-second-picker", "value"),
        State("pos-end-hour-picker", "value"),
        State("pos-end-minute-picker", "value"),
        State("pos-end-second-picker", "value"),
        State("pos-cage-tag-dropdown", "value"),
        State("pos-tag-id-dropdown", "value"),
        # PLOT OPTIONS
        State("pos-plot-type-selection-dropdown", "value"),
        State("pos-x-axis-selection-dropdown", "value"),
        State("pos-y-axis-selection-dropdown", "value"),
        State("pos-z-axis-selection-dropdown", "value"),
        State("pos-scatter-options-selection-dropdown", "value"),
        State("pos-boxplot-options-selection-dropdown", "value"),
        State("pos-plot-marker-size", "value"),
        State("pos-plot-marker-opacity", "value"),
        State("pos-plot-line-width", "value"),
        State("pos-plot-line-dash", "value"),
        State("pos-enable-timeseries", "on"),
    ],
)
def update_pos_graph(
    n_clicks,
    start_date,
    end_date,
    start_hour,
    start_min,
    start_sec,
    end_hour,
    end_min,
    end_sec,
    cage,
    tags,
    plotType,
    xAxis,
    yAxis,
    zAxis,
    scatterMode,
    boxMode,
    markerSize,
    markerOpacity,
    lineWidth,
    lineDash,
    timeseries,
):
    marker, line = get_marker_line(markerSize, markerOpacity, lineWidth, lineDash)

    # Read global dataframe from plasma store
    df = read_from_plasma("pos")
    print(f"Plasma POS")

    # Filter dataframe
    start_time = get_time_of_day(start_hour, start_min, start_sec)
    end_time = get_time_of_day(end_hour, end_min, end_sec)
    dff = df.loc[start_date:end_date]
    dff = dff.between_time(start_time, end_time)
    dff = dff[dff["tag_id"].isin(tags)]
    print(f"Filter POS")
    data = get_plot_data(
        "pos", dff, plotType, xAxis, yAxis, zAxis, scatterMode, marker, line
    )
    layout = get_plot_layout(xAxis, yAxis, zAxis, plotType, boxMode)
    print(f"Data POS")

    # Add cage and/or animate
    if plotType == "scatter3d":
        date = dt.strptime(start_date, "%Y-%m-%d")
        if cage == "Aquatraz":
            if date > dt.strptime("2019-05-10", "%Y-%m-%d"):
                data = data + aq_cage_new.traces
            else:
                data = data + aq_cage.traces
        elif cage == "Reference":
            data = data + ref_cage.traces
        else:
            if date > dt.strptime("2019-05-10", "%Y-%m-%d"):
                data = data + ref_cage.traces + aq_cage_new.traces
            else:
                data = data + ref_cage.traces + aq_cage.traces
        fig = {"data": data, "layout": layout}
    elif plotType == "scatter3d_animation":
        date = dt.strptime(start_date, "%Y-%m-%d")
        times = dff["timestamp"].unique()
        dates = dff["Date_str"].unique()
        fig = get_animation_fig(data, times, dates, tags, date, cage)
    else:
        fig = {"data": data, "layout": layout}
    return fig


@app.callback(
    Output("fig-save-button", "children"),
    [Input("fig-save-button", "n_clicks")],
    [
        State("fig-format-options", "value"),
        State("data-set-selection-dropdown", "value"),
        State("tag-graph", "figure"),
        State("tbr-graph", "figure"),
        State("pos-graph", "figure"),
    ],
)
def test_image_export(n_clicks, fig_format, type, tag_fig, tbr_fig, pos_fig):
    if tag_fig is None or tbr_fig is None or pos_fig is None:
        return "Save"
    path = dt.strftime(dt.today(), "figs/%Y_%m_%d")
    if not os.path.exists(path):
        os.mkdir(path)
    name = dt.strftime(dt.now(), f"{path}/%Y_%m_%d_%H%M%S_{type}")
    fig = {"tag": tag_fig, "tbr": tbr_fig, "pos": pos_fig}
    plotly.io.write_image(fig[type], name, format=fig_format, width=1320, height=700)
    return "Save"


if __name__ == "__main__":
    app.run_server(debug=True)
