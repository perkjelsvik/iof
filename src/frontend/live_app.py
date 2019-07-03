import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_daq as daq
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import sqlite3
import pandas as pd
from datetime import timedelta
from datetime import datetime as dt
from flask_caching import Cache
import dash_auth
import toml

from layoutCode import app_page_layout, header_colors

usrpwd = toml.load("usrpwd.toml")
VALID_USERNAME_PASSWORD_PAIR = [[usrpwd["username"], usrpwd["password"]]]
app = dash.Dash(__name__)
auth = dash_auth.BasicAuth(app, VALID_USERNAME_PASSWORD_PAIR)
cache = Cache(
    app.server,
    config={
        "CACHE_TYPE": "redis",
        "CACHE_TYPE": "filesystem",
        "CACHE_DIR": "live-cache-directory",
        "CACHE_THRESHOLD": 100,
    },
)
timeout = 2 * 60 * 60  # 2 hour timeout for filesystem cache

# Init
tz = "Europe/Oslo"
dt_format = "%Y-%m-%d %H:%M:%S"
depth_tags = tuple(*[list(range(10, 90, 2))])
acc_tags = tuple(range(11, 91, 2))
aqz_tags = tuple(*[list(range(10, 50))])
aqz_depth = tuple(*[list(range(10, 50, 2))])
ref_depth = tuple(*[list(range(50, 90, 2))])
ref_tags = tuple(*[list(range(50, 90))])
all_tags = tuple(sorted([*aqz_tags, *ref_tags]))
aqz_tbrs = tuple([732, 735, 837])
ref_tbrs = tuple([730, 734, 836])
all_tbrs = tuple(sorted([*aqz_tbrs, *ref_tbrs]))
tag_frequencies = (69,)
tag_freq_69 = tuple(range(10, 90))

# PROBABLY LAST AVAILABLE 71/73 data timestamp: 1549949008 | 12.02.2019 06:23:28


def db_sql_query(starts_ts, table):
    # Shared filters
    ts_filt = f"timestamp > {starts_ts}"
    order = "timestamp ASC"
    freq = 69  # tag and positions

    if table == "tag":
        comm = "S256"
        columns = "timestamp, tbr_serial_id, tag_id, tag_data, snr, millisecond"
        freq_filt = f"frequency = {freq}"
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
        freq_filt = f"frequency = {freq}"
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
        # Add metadata
        rename_dict = {
            "tbr_serial_id": "tbrSerialNo",
            "tag_id": "tagID",
            "tag_data": "tagData",
        }
    elif name == "tbr":
        df.tbr_serial_id = df.tbr_serial_id.astype("uint16")
        df.noise_avg = df.noise_avg.astype("uint8")
        df.noise_peak = df.noise_peak.astype("uint8")
        # Add metadata
        rename_dict = {
            "tbr_serial_id": "tbrSerialNo",
            "noise_avg": "ambNoiseAvg",
            "noise_peak": "ambNoisePeak",
        }
    elif name == "pos":
        df.tag_id = df.tag_id.astype("uint8")
        df.frequency = df.frequency.astype("uint8")
        df.millisecond = df.millisecond.astype("uint16")
        df.z = -df.z
        # Add metadata
        rename_dict = {"tag_id": "tagID"}
    # print("Renaming dataframe columns...")
    # df = df.rename(index=str, columns=rename_dict)
    # print(df)
    return df


@cache.memoize(timeout=timeout)
def clean_data_cached(start_ts, name):
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


def get_cage_tbr_dropdown(type):
    return html.Div(
        id=f"{type}-cage-tbr-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name", children=["Select cage (TBR)"]
            ),
            dcc.Dropdown(
                id=f"{type}-cage-tbr-dropdown",
                value="All",
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


def get_cage_tag_dropdown(type):
    return html.Div(
        id=f"{type}-cage-tag-dropdown-div",
        className="app-controls-block",
        children=[
            html.Div(
                className="fullwidth-app-controls-name", children=["Select cage (TAGs)"]
            ),
            dcc.Dropdown(
                id=f"{type}-cage-tag-dropdown",
                value="All",
                options=[
                    {"label": i, "value": i} for i in ("Aquatraz", "Reference", "All")
                ],
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
                value=depth_tags,
                options=[{"label": f"tag {i}", "value": i} for i in depth_tags],
                multi=True,
                clearable=False,
                placeholder="Select at least one tag!",
            ),
        ],
    )


tag_filter_options = [
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

tag_plot_options = [{"label": "Scatter", "value": "scatter"}]

all_plot_options = {"tag": tag_plot_options}

tag_axis_options = [
    {"label": "Date", "value": "Date_str"},
    {"label": "Timestamp", "value": "timestamp"},
    {"label": "Hour of day", "value": "hour"},
    {"label": "Millisecond", "value": "millisecond"},
    {"label": "TBR ID", "value": "tbr_serial_id"},
    {"label": "Tag ID", "value": "tag_id"},
    {"label": "Tag Data", "value": "tag_data"},
    {"label": "SNR", "value": "snr"},
]

plot_scatter_options = [
    {"label": "Markers", "value": "markers"},
    {"label": "Markers + Lines", "value": "markers+lines"},
    {"label": "Lines", "value": "lines"},
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
    temperature="Temperature [°C]",
    noise_avg="Ambient Noise Average",
    noise_peak="Ambient Noise Peak",
    x="X-position [m]",
    y="Y-position [m]",
    z="Depth [m]",
    latitude="Latitude",
    longitude="Longitude",
)


def get_graph_div(type, style={"display": "none"}):
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


def layout_test():
    return html.Div(
        id="iofp-page-content",
        className="app-body",
        children=[
            # Graph
            html.Div(
                id="loading-graph-div",
                className="dashiof-loading",
                children=[get_graph_div("tag", {"display": "inline-block"})],
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
                                            "This is a simplified dash app that lets "
                                            "you monitor live fish data. It is "
                                            "designated to view fish depth data with "
                                            "a simple scatter plot, but you can select "
                                            "other types of data for the x and y axis. "
                                            "Other plot types or data sets (tbr/pos) "
                                            "is however not available in this version. "
                                        ),
                                        html.P(
                                            "You can adjust how the scatter plot looks "
                                            "in the 'plot' tab. Here you can select "
                                            "size of markers, width of lines, opacity "
                                            "as well as whether you want the plot to "
                                            "be 'markers' / 'lines+markers' / 'lines'. "
                                            "In addition there is a button to turn "
                                            "on/off timeseries. Timeseries is a simple "
                                            "slider beneath the x-axis that simplifies "
                                            "Time navigation in the plot. It also "
                                            "Includes some button in the plot for time "
                                            "period selection (1h, 3h, 24h etc.). "
                                            "The y-axis will be locked with timeseries "
                                            "on. Timeseries will only work for a Date "
                                            "axis."
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
                                        # Choose X axis
                                        html.Div(
                                            className="app-controls-block",
                                            children=[
                                                html.Div(
                                                    className="fullwidth-app-controls-name",
                                                    children=["X-axis"],
                                                ),
                                                dcc.Dropdown(
                                                    id="x-axis-selection-dropdown",
                                                    value="Date_str",
                                                    clearable=False,
                                                    options=tag_axis_options,
                                                ),
                                            ],
                                        ),
                                        # Choose Y axis
                                        html.Div(
                                            className="app-controls-block",
                                            children=[
                                                html.Div(
                                                    className="fullwidth-app-controls-name",
                                                    children=["Y-axis"],
                                                ),
                                                dcc.Dropdown(
                                                    id="y-axis-selection-dropdown",
                                                    # value="hour",
                                                    value="tag_data",
                                                    clearable=False,
                                                    options=tag_axis_options,
                                                ),
                                            ],
                                        ),
                                        html.Hr(),
                                        # Choose mode
                                        html.Div(
                                            className="app-controls-block",
                                            children=[
                                                html.Div(
                                                    id="plot-options-dropdown-div",
                                                    className="fullwidth-app-controls-name",
                                                    children=["Scatter mode"],
                                                ),
                                                dcc.Dropdown(
                                                    id="plot-options-selection-dropdown",
                                                    value="markers+lines",
                                                    clearable=False,
                                                    options=plot_scatter_options,
                                                ),
                                            ],
                                        ),
                                        # Choose marker options
                                        html.Div(
                                            className="app-controls-block",
                                            children=[
                                                html.Div(
                                                    id="plot-marker-size-div",
                                                    className="fullwidth-app-controls-name",
                                                    children=["Marker options"],
                                                ),
                                                daq.NumericInput(
                                                    id=f"plot-marker-size",
                                                    className="app-controls-name",
                                                    value=6,
                                                    min=1,
                                                    max=20,
                                                    label="Size",
                                                ),
                                                daq.PrecisionInput(
                                                    id=f"plot-marker-opacity",
                                                    className="app-controls-name",
                                                    value=0.5,
                                                    min=0,
                                                    max=1,
                                                    label="Opacity",
                                                    precision=1,
                                                ),
                                            ],
                                        ),
                                        # Choose Line options
                                        html.Div(
                                            className="app-controls-block",
                                            children=[
                                                html.Div(
                                                    id="plot-line-options-div",
                                                    className="fullwidth-app-controls-name",
                                                    children=["Line options"],
                                                ),
                                                daq.NumericInput(
                                                    id=f"plot-line-width",
                                                    className="app-controls-name",
                                                    value=2,
                                                    label="Width",
                                                ),
                                                dcc.Dropdown(
                                                    id=f"plot-line-dash",
                                                    className="app-controls-name",
                                                    value="solid",
                                                    clearable=False,
                                                    options=[
                                                        {
                                                            "label": "Solid",
                                                            "value": "solid",
                                                        },
                                                        {
                                                            "label": "dot",
                                                            "value": "dot",
                                                        },
                                                        {
                                                            "label": "Dash",
                                                            "value": "dash",
                                                        },
                                                        {
                                                            "label": "Long Dash",
                                                            "value": "longdash",
                                                        },
                                                        {
                                                            "label": "Dash Dot",
                                                            "value": "dashdot",
                                                        },
                                                        {
                                                            "label": "Long Dash Dot",
                                                            "value": "longdashdot",
                                                        },
                                                    ],
                                                ),
                                            ],
                                        ),
                                        # On/off switch for timeseries
                                        html.Div(
                                            id="enable-timeseries-div",
                                            className="app-controls-block",
                                            children=[
                                                html.Div(
                                                    className="fullwidth-app-controls-name",
                                                    children=["Enable timeseries"],
                                                ),
                                                daq.BooleanSwitch(
                                                    id="enable-timeseries", on=True
                                                ),
                                            ],
                                        ),
                                        # Bottom-line
                                        html.Hr(),
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
                                        # TAG options
                                        html.Div(
                                            id="tag-tab", children=tag_filter_options
                                        )
                                    ],
                                ),
                            ),
                        ],
                    ),
                    # Interval to update graph
                    html.Div(
                        id="interval-component-div",
                        style={"display": "none"},
                        children=[
                            html.H1(id="number-out", children=""),
                            dcc.Interval(
                                id="interval-component",
                                interval=(10) * 1000,  # Every 10 seconds
                                n_intervals=0,
                            ),
                        ],
                    ),
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


def tag_dropdown_options(cage, dataType=None):
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

    # Pack possible tags into options list and return with tags
    options = [{"label": f"tag {i}", "value": i} for i in tags]
    return options, tags


def cage_tbr_dropdown(cage):
    cageTbrs = {"All": all_tbrs, "Aquatraz": aqz_tbrs, "Reference": ref_tbrs}
    tbrs = cageTbrs[cage]
    options = [{"label": f"tbr {i}", "value": i} for i in tbrs]
    return options, tbrs


def empty_tags_selection(cage, dataType):
    defaultTags = {
        "acc": {"Aquatraz": [11, 0], "Reference": [51, 0]},
        "depth": {"Aquatraz": [10, 0], "All": [10, 0], "Reference": [50, 0]},
    }
    return defaultTags[dataType][cage]


def get_time_of_day(hour, minute, second):
    return f"{hour}:{minute}:{second}"


# *--------------------------------------*
# | SWITCHING BETWEEN DATA SETS CALLBACK |
# *--------------------------------------*


# *------------------------------*
# | GLOBAL DATA UPDATE CALLBACKS |
# *------------------------------*


# *------------------------------*
# | TAG DATA FILTERING CALLBACKS |
# *------------------------------*


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
    [Input("tag-cage-tag-dropdown", "value"), Input("tag-data-type-dropdown", "value")],
    [State("tag-tag-id-dropdown", "value")],
)
def update_tag_tag_id_dropdown(tagsCage, tagsType, selected):
    options, validTags = tag_dropdown_options(tagsCage, tagsType)
    tags = list(set(selected).intersection(validTags))
    if not tags:
        tags = empty_tags_selection(tagsCage, tagsType)
    return options, tags


# SNR SLIDER
@app.callback(Output("snr-values", "children"), [Input("tag-snr-rangeslider", "value")])
def show_snr_filter_values(value):
    return f"[{value[0]}, {value[1]}]"


# *--------------------*
# | PLOT TAB CALLBACKS |
# *--------------------*


@app.callback(
    Output("enable-timeseries", "on"), [Input("x-axis-selection-dropdown", "value")]
)
def disable_timeseries(xaxis):
    if xaxis == "Date_str":
        return True
    else:
        return False


# *------------------------------------------------*
# | PLOTTING FIGURES CALLBACKS FOR TAG / TBR / POS |
# *------------------------------------------------*


@app.callback(
    [Output("tag-graph", "figure"), Output("interval-component", "interval")],
    [
        Input("interval-component", "n_intervals"),
        Input("tag-data-type-dropdown", "value"),
        Input("tag-tbr-dropdown", "value"),
        Input("tag-tag-id-dropdown", "value"),
        Input("tag-snr-rangeslider", "value"),
        # PLOT OPTIONS
        Input("x-axis-selection-dropdown", "value"),
        Input("y-axis-selection-dropdown", "value"),
        Input("plot-options-selection-dropdown", "value"),
        Input("enable-timeseries", "on"),
        Input("plot-marker-size", "value"),
        Input("plot-marker-opacity", "value"),
        Input("plot-line-width", "value"),
        Input("plot-line-dash", "value"),
    ],
    [State("interval-component", "interval")],
)
def update_live_graph(
    n,
    dataType,
    tbrs,
    tags,
    snr,
    xAxis,
    yAxis,
    plotMode,
    timeseries,
    markerSize,
    markerOpacity,
    lineWidth,
    lineDash,
    interval,
):
    # start_date = dt.today().strftime("%Y-%m-%d")
    # end_date = (dt.today()+timedelta(1)).strftime("%Y-%m-%d")
    hour_offset = 24
    now, prev = dt.now(), dt.now() - timedelta(hours=hour_offset)
    ts_now = int(dt.timestamp(now - timedelta(seconds=60 * 3)))
    ts_cache = int(dt.timestamp(now - timedelta(hours=hour_offset)))
    df_old = clean_data_cached(ts_cache, "tag")
    df_new = clean_data(ts_now, "tag")
    if df_new.empty:
        print("No new data since previous poll")
        if interval == (10) * 1000:  # Every 10 seconds
            interval = (60) * 1000  # Every minute
        elif interval == (60) * 1000:
            interval = (60) * 10 * 1000  # Every 10 minutes
        elif interval == (60) * 10 * 1000:
            interval = (60) * 60 * 1000  # Every 1 hour
    else:
        interval = (10) * 1000
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates()

    # FILTER
    dff = df[df["tag_id"].isin(tags)]
    dff = dff[dff["tbr_serial_id"].isin(tbrs)]
    dff = dff[dff.snr.between(snr[0], snr[1])]
    if plotMode == "markers":
        data = [
            go.Scattergl(
                x=dff[dff["tag_id"] == id][xAxis],
                y=dff[dff["tag_id"] == id][yAxis],
                mode=plotMode,
                name=f"tag {id}",
                marker=dict(size=markerSize, opacity=markerOpacity),
            )
            for id in sorted(dff.tag_id.unique())
        ]
    elif plotMode == "lines":
        data = [
            go.Scattergl(
                x=dff[dff["tag_id"] == id][xAxis],
                y=dff[dff["tag_id"] == id][yAxis],
                mode=plotMode,
                name=f"tag {id}",
                # marker=dict(
                #    size=markerSize,
                #    opacity=markerOpacity,
                # ),
                line=dict(width=lineWidth, dash=lineDash),
            )
            for id in sorted(dff.tag_id.unique())
        ]
    else:
        data = [
            go.Scattergl(
                x=dff[dff["tag_id"] == id][xAxis],
                y=dff[dff["tag_id"] == id][yAxis],
                mode=plotMode,
                name=f"tag {id}",
                marker=dict(size=markerSize, opacity=markerOpacity),
                line=dict(width=lineWidth, dash=lineDash),
            )
            for id in sorted(dff.tag_id.unique())
        ]
    layout = dict(
        title="Live tag scatter graph",
        xaxis=dict(title=axisLabels[xAxis], range=[prev, now]),
        yaxis=dict(title=axisLabels[yAxis]),
        uirevision="foo",
    )
    if timeseries:
        layout = dict(
            title=f"{axisLabels[xAxis]}",
            xaxis=dict(
                rangeselector=dict(
                    buttons=list(
                        [
                            dict(count=1, label="1h", step="hour", stepmode="backward"),
                            dict(count=2, label="2h", step="hour", stepmode="backward"),
                            dict(count=3, label="3h", step="hour", stepmode="backward"),
                            dict(count=6, label="6h", step="hour", stepmode="backward"),
                            dict(count=9, label="9h", step="hour", stepmode="backward"),
                            dict(
                                count=12, label="12h", step="hour", stepmode="backward"
                            ),
                            dict(
                                count=15, label="15h", step="hour", stepmode="backward"
                            ),
                            dict(
                                count=18, label="18h", step="hour", stepmode="backward"
                            ),
                            dict(
                                count=21, label="21h", step="hour", stepmode="backward"
                            ),
                            dict(
                                count=24, label="24h", step="hour", stepmode="backward"
                            ),
                            dict(step="all"),
                        ]
                    )
                ),
                rangeslider=dict(visible=True),
                type="date",
                title="Time",
            ),
            yaxis=dict(title=f"{axisLabels[yAxis]}"),
            uirevision="foo",
        )
    fig = dict(data=data, layout=layout)
    return fig, interval


if __name__ == "__main__":
    # app.run_server(debug=True)
    app.run_server(debug=True)
