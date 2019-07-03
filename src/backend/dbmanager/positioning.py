# Python built-in modules and packages
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional, Any, Dict, Union

# Third-party modules and packages
import pandas as pd
import toml

# Local modules and packages
from src.backend.dbmanager import tdoa
from src.backend.dbmanager import dbformat


# --- Useful type hints ---
ListTBR = List[int]
DatabaseManager = Any  # Any type to avoid uneccesary import
msghandler = Any  # Any type to avoid uneccesary import
CageMetaDict = Dict[str, List[ListTBR]]
TagsMetaDict = Dict[str, Union[int, str]]
MetaDict = Dict[str, Dict[str, Union[CageMetaDict, TagsMetaDict]]]

# TODO(perkjelsvik) - Improve path handling when positioning complete database

logger = logging.getLogger("mqtt_client.positioning")


# Definitions of dataclasses used in this module.
@dataclass
class Point(tdoa.Point):
    pass


@dataclass
class CageCircle(tdoa.Circle):
    pass


@dataclass
class CageGeometry:
    circle: CageCircle
    lat_A: float
    lat_B: float
    lat_C: float
    lon_A: float
    lon_B: float
    lon_C: float


@dataclass
class CageMeta:
    cageName: str
    tbr: List[ListTBR]
    depth: float
    geometry: Optional[CageGeometry]


@dataclass
class TagsMeta:
    tag_id: int
    frequency: int
    cageName: str


@dataclass
class Position:
    timestamp: int
    tag_id: int
    frequency: int
    cage_name: str
    millisecond: int
    x: float
    y: float
    z: float
    latitude: float
    longitude: float


_cages, _depth_tags = None, None


def init_metadata(old=False) -> Optional[Tuple[CageMetaDict, List[TagsMeta]]]:
    """Loads positoning metadata from .toml file if it exists.

    Loads metadata from toml-file into dictonary, and if successful, iterates through
    said metadata. For cages metadata, it creates an instance of CageMeta for each
    cage, and for tags metdata, it creates an instance of TagsMeta for each depth tag.
    These instances are added to lists 'cages' and 'depth_tags'.

    Returns:
        Returns a tuple of two lists, where the first list contains multiple instances
        of CageMeta, and the second contains multiple instances of TagsMeta.
        If metadata cannot be loaded for some reason, the function returns None.

    Raises:
        FileNotFoundError: NB! No metadata position config file found.
            Can't do positioning.
        Exception: Caught an error while loading metadata positioning
    """
    global _cages
    global _depth_tags
    try:
        # metaDict: MetaDict = toml.load("../.config/bench_position.toml")
        # metaDict: MetaDict = toml.load("../.config/metadata_positioning.toml")
        metaDict: MetaDict = toml.load("src/backend/.config/metadata_positioning.toml")
    except FileNotFoundError:
        logger.error(
            "NB! No metadata position config file found. Can't do positioning."
        )
        return None
    except Exception:
        logger.exception("Caught an error while loading metadata positioning")
        return None
    else:
        cages, depth_tags = {}, []
        for cage_key in metaDict["cages"]:
            cageGeo = None
            cageName = cage_key
            tbrList = metaDict["cages"][cage_key]["tbr"]
            if old:
                depth = metaDict["cages"][cage_key]["depth_old"]
            else:
                depth = metaDict["cages"][cage_key]["depth"]
            if "geometry" in metaDict["cages"][cage_key]:
                geo = metaDict["cages"][cage_key]["geometry"]
                center = Point(geo["centerX"], geo["centerY"])
                circle = CageCircle(center, geo["radius"])
                if old:
                    cageGeo = CageGeometry(
                        circle=circle,
                        lat_A=geo["lat_A_old"],
                        lat_B=geo["lat_B_old"],
                        lat_C=geo["lat_C_old"],
                        lon_A=geo["lon_A_old"],
                        lon_B=geo["lon_B_old"],
                        lon_C=geo["lon_C_old"],
                    )
                else:
                    cageGeo = CageGeometry(
                        circle=circle,
                        lat_A=geo["lat_A"],
                        lat_B=geo["lat_B"],
                        lat_C=geo["lat_C"],
                        lon_A=geo["lon_A"],
                        lon_B=geo["lon_B"],
                        lon_C=geo["lon_C"],
                    )
            cages.update({cageName: CageMeta(cageName, tbrList, depth, cageGeo)})
        for tag_key in metaDict["tags"]:
            tag_id = metaDict["tags"][tag_key]["tag_id"]
            frequency = metaDict["tags"][tag_key]["frequency"]
            cageName = metaDict["tags"][tag_key]["cage_name"]
            depth_tags.append(TagsMeta(tag_id, frequency, cageName))
        _cages, _depth_tags = cages, depth_tags
    return None


# *------------------------------------------------*
# | "private" helper-functions used by this module |
# *------------------------------------------------*


def _adjust_tstamp_drift_of_triplet(df: pd.Dataframe) -> List[pd.DataFrame]:
    """Return list of pandas DataFrames where timestamp offsets has been adjusted.

    Sorts dataframe based on timestamp, finds triplets where timestamp is equal +-2, and
    adjusts any timestamps +-2 from 2nd timestamp to be equal to 2nd timestamp. Returns
    a list of all valid triplets.

    Args:
        df: pd.DataFrame where columns "timestamp" and "millisecond" are used to adjust.

    Returns:
        Returns list of pd.DataFrame where timestamps offset +-2 from middle timestamp
        is adjusted. For example:

        | timestamp  | millisecond | frequency | tagID | tagData |
        | 1556555369 |     995     |     69    |   12  |   3.5   |
        | 1556555370 |     005     |     69    |   12  |   3.5   |
        | 1556555371 |     010     |     69    |   12  |   3.5   |

        becomes -->

        | timestamp  | millisecond | frequency | tagID | tagData |
        | 1556555370 |     995     |     69    |   12  |   3.5   |
        | 1556555370 |     005     |     69    |   12  |   3.5   |
        | 1556555370 |     010     |     69    |   12  |   3.5   |
    """
    ts_drift_threshold = 2
    ms_1km = 0.667

    # Sort dataframe by timestamps in case some timestamps are in the wrong order
    df = df.sort_values("timestamp")
    df = df.reset_index(drop=True)

    # Extract timestamps and find all triplets within dataframe
    ts = df["timestamp"]
    last_indices = ts.index[ts.diff(periods=2) <= ts_drift_threshold]
    all_indices = last_indices.append(
        [last_indices - 1, last_indices - 2]
    ).sort_values()

    # Mask out all detections that aren't triplets
    mask_values = [i for i in range(len(last_indices)) for _ in range(3)]
    df.loc[all_indices, "mask"] = mask_values
    df = df[df["mask"].notnull()]
    if df.empty:
        return []

    # Adjust timestamps that have drifted
    # | if 2nd timestamp in triplet is much larger than the 1st, add 2nd index to list
    # | if 3rd timestamp in triplet is much larger than the 2nd, add 2nd index to list
    df["drift"] = df.apply(lambda x: x["timestamp"] + x["millisecond"] / 1000, axis=1)
    drift = df["drift"].diff()
    drift_3rd = drift[last_indices].where(abs(drift[last_indices]) >= ms_1km)
    drift_1st = drift[last_indices - 1].where(abs(drift[last_indices - 1]) >= ms_1km)
    drift_indices = drift_3rd.dropna().index - 1  # -1 to get index of 2nd timestamp
    drift_indices = drift_indices.append(drift_1st.dropna().index)

    # Set timestamp 1 and 3 of each triplet with drift has equal to 2nd timestamp
    df.loc[drift_indices - 1, "timestamp"] = ts[drift_indices].values
    df.loc[drift_indices + 1, "timestamp"] = ts[drift_indices].values

    # get and return triplets as list of dataframes
    triplets = [v.drop(["mask", "drift"], axis=1) for _, v in df.groupby("mask")]
    # triplets = [v.drop(["mask"], axis=1) for _, v in df.groupby("mask")]
    return triplets


def circleFromThreePoints(P0: Point, P1: Point, P2: Point) -> CageCircle:
    """Finds and returns minimal circle (center, radius) based on three xy-points.

    Function derived from:
    | https://www.xarg.org/2018/02/create-a-circle-out-of-three-points/

    Args:
        P0: Point 0
        P1: Point 1
        P2: Point 2

    Returns:
        Instance of dataclass 'Circle' with center and radius attributes.
    """
    # get magnitude of points and extract xy-values of points
    # print(f"\t\t\tA: {P0} | B: {P1} | C: {P2}")
    (x0, y0), (x1, y1), (x2, y2) = (P0.x, P0.y), (P1.x, P1.y), (P2.x, P2.y)
    mag0, mag1, mag2 = (x0 ** 2 + y0 ** 2), (x1 ** 2 + y1 ** 2), (x2 ** 2 + y2 ** 2)

    # equations used to find center
    a = x0 * (y1 - y2) - y0 * (x1 - x2) + x1 * y2 - x2 * y1
    b = mag0 * (y2 - y1) + mag1 * (y0 - y2) + mag2 * (y1 - y0)
    c = mag0 * (x1 - x2) + mag1 * (x2 - x0) + mag2 * (x0 - x1)

    # find center and radius
    x = -b / (2 * a)
    y = -c / (2 * a)
    r = tdoa.distance_xy(Point(x0, y0), Point(x, y))
    return CageCircle(Point(x, y), r)


def _is_depth_tag(tag_id: int, frequency: int) -> bool:
    """Checks if tag_id and frequency combination is a depth tag.

    Iterates through list of dataclass instances of MetaTag, and checks if the provided
    tag_id and frequency combination is a depth tag. If so, it retusn True.

    Args:
        tag_id: Integer ID number representing tag.
        frequency: Integer representing which frequency the tag is detected.

    Returns:
        If a match is found in metadata, the function returns True.
        Else it returns False
    """
    for tagMeta in _depth_tags:
        if (tag_id == tagMeta.tag_id) & (frequency == tagMeta.frequency):
            return True
    return False


def _get_tag_df(
    ref_timestamp: int,
    tag_id: int,
    frequency: int,
    TBRs: ListTBR,
    dbObj: DatabaseManager,
) -> Tuple[bool, pd.DataFrame]:
    """Finds tag msgs of tag id in db with matching TBR ids close to timestamp.

    Uses reference timestamp, tag id and possible TBR IDs to find tag detections in main
    database within interval of reference timestamp. If a triplet exists, a boolean
    value returns true, and the pandas dataframe of the detections is memory optimized.

    Args:
        ref_timestamp: Integer in unix epoch format.
        tag_id: Integer representing tag id, used for database retrieval.
        cage: Instance of dataclass CageMeta with relevant member variables 'tbr', a
            list of TBR IDs for this cage, and 'depth', float of the TBRs depth.
        dbObj: dbmanager.DatabaseManager instance, with open connection to database.

    Returns:
        Tuple containing a boolean to indicate whether a triplet of tag detections (one
        tag detection for each possible TBR) exists in database, and a pandas dataframe
        containing said detections. For example:

        (True, df) where df is a pandas dataframe constructedl like:

            | timestamp  | milliseconds | cage  | frequency | tagID | tagData |
            | 1556555369 |     995      | "Ref" |     69    |   12  |   3.5   |
            | 1556555370 |     005      | "Ref" |     69    |   12  |   3.5   |
            | 1556555370 |     010      | "Ref" |     69    |   12  |   3.5   |

        Dataframe is returned even if triplet does not exist.
    """
    triplet = False
    interval = 5
    query_tag = dbformat.sql_query_tag_df(
        ref_timestamp, len(TBRs), tag_id, frequency, interval
    )
    df = pd.read_sql(query_tag, dbObj.con, params=TBRs)
    if len(df.index) == 3 and df.tbr_serial_id.unique().size > 2:
        triplet = True
        # Make dataframe more memory efficient
        df.tbr_serial_id = df.tbr_serial_id.astype("uint16")
        df.timestamp = df.timestamp.astype("uint32")
        df.millisecond = df.millisecond.astype("uint16")
        df.frequency = df.frequency.astype("uint8")
        # tag_data is already float type, tag_id uint16 in case of 'S64K'
        df.tag_id = df.tag_id.astype("uint16")
        # sort by timestamp and adjust timestamps that has drifted
        df = _adjust_tstamp_drift_of_triplet(df)[0]  # [df]
    return (triplet, df)


def _get_station_data(
    TBRs: List[int], depth: float, dbObj: DatabaseManager
) -> tdoa.StationData:
    """Finds latest position of TBRs.

    For each TBR_id provided in TBRs argument, retrieves latest latitude-longitude
    position and packs it into a dataclass StationData instance. Only accepts a position
    where fix='3D-fix', and pdop in range(1, 7) (choosing the lowest available one).
    Does not work if there isn't at least one valid position for each TBR.

    Args:
        TBRs: A list of TBR IDs for this cage.
        depth: float, depth variable provided my metadata file shared between each TBR.
        dbObj: dbmanager.DatabaseManager instance, with open connection to database.

    Returns:
        After retrieving latiude longitude for each TBR in cage, packs the TBR ID,
        position and depth into a dataclass 'StationData' instance and returns it.

    Raises:
        ValueError: Did not find a position for each TBR!
    """
    # Get newest latitude/longitude positions for TBRs
    # | Looks for most recent '3D-fix' quality position
    # | And accepts the newest found position with pdop lower than 1, or 2, ..., or 6
    tbr_pos = []
    # Combak(perkjelsvik) - Should I also add timestamp filter, f. ex. last 24 hours?
    pdopValues = range(1, 7)
    for tbr_id in TBRs:
        for pdop in pdopValues:
            sql_query = dbformat.sql_query_get_latest_TBR_pos(tbr_id, pdop)
            latlon = dbObj.select_from_db_record(sql_query)  # [(lat, lon)]
            if latlon:
                lat, lon = latlon[0]
                tbr_pos.append(tdoa.LatLong(lat, lon))
                break
    if len(tbr_pos) < 3:
        raise ValueError(
            f"Did not find position for all TBRs ({TBRs}) in database! "
            f"Found {tbr_pos}"
        )
    station_data = tdoa.StationData(*TBRs, *tbr_pos, depth)
    return station_data


def _get_tag_depth_and_timestamps(
    station_data: tdoa.StationData, df: pd.DataFrame
) -> Tuple[float, tdoa.Timestamps]:
    """Retrieves timestamps and depth from pandas.DataFrame instance.

    Defines depth of a tag detection as the average of the dataframe tag_data column.
    Extracts timestamp and millisecond value for each tag detection, and packs them
    into a dataclass Timestamps instance which it returns.

    Args:
        station_data: Dataclass positioning_algorithm.StationData instance, relevant for
            this function is its member variable 'TBR_X' where X is either A, B or C.
            station_data.TBR_X is an integer representing tbr_serial_id.
        df: A pandas.DataFrame with a triplet of tag detections.

    Returns:
        Tuple with depth of tag and positioning_algorithm.Timestamps dataclass instance.
    """
    depth = df.mean().tag_data
    sec_a = df[df["tbr_serial_id"] == station_data.TBR_A]["timestamp"].item()
    sec_b = df[df["tbr_serial_id"] == station_data.TBR_B]["timestamp"].item()
    sec_c = df[df["tbr_serial_id"] == station_data.TBR_C]["timestamp"].item()
    msec_a = df[df["tbr_serial_id"] == station_data.TBR_A]["millisecond"].item()
    msec_b = df[df["tbr_serial_id"] == station_data.TBR_B]["millisecond"].item()
    msec_c = df[df["tbr_serial_id"] == station_data.TBR_C]["millisecond"].item()
    tstamps = tdoa.Timestamps(sec_a, sec_b, sec_c, msec_a, msec_b, msec_c)
    return (depth, tstamps)


def _get_cage_and_TBR_data(tbr_serial_id: int) -> Optional[CageMeta]:
    """Retrives list of TBR IDs and shared depth of TBRs.

    Iterates through list of loaded cage metadata containing lists of TBR serial IDs,
    and returns cage information as an instance of dataclass 'CageMeta' if a match is
    found between input tbr_id and list of TBRs.

    Args:
        tbr_serial_id: Integer representing serial ID number of TBR.

    Returns:
        If a match is found, the functions returns the relevant CageMeta instance of
        said TBR. For example:

        cage - An instance of dataclass CageMeta with member variables:
            cageName: str="ref",
            tbr: List[List[int]]=[[32, 33, 34], [128, 129, 130]],
            depth: float=3

        If no match is found, the function returns None.
    """
    for cage in _cages:
        for listOfTBRs in _cages[cage].tbr:
            if tbr_serial_id in listOfTBRs:
                return (_cages[cage], listOfTBRs)
    logger.warning(f"No matching set of TBRs were found for {tbr_serial_id}")
    return None


def _get_list_of_triplets_from_db(
    tag_id: int, frequency: int, TBRs: List[int], dbObj: DatabaseManager
) -> list[pd.DataFrame]:
    """Return list of pandas DataFrames of tag triplets for complete database.

    Extracts all messages of (tag_id, frequency) combination from main database into a
    pandas DataFrame. Then calls on '_adjust_tstamp_drift_of_triplet' to find triplets.

    Args:
        tag_id: Integer ID for tag_id wanted.
        frequency: Integer ID for frequency wanted.
        TBRs: A list of TBR IDs, used to filter from database.
        dbObj: dbmanager.DatabaseManager instance, with connection to main database.

    Returns:
        Returns list of pd.DataFrame where wach dataframe represents a tag triplet.
    """
    sql_query = dbformat.sql_query_get_db_all_tag_freq_detections(tag_id, frequency)

    # Read from main database into pandas dataframe, and optimize df memory usage
    df = pd.read_sql(sql_query, dbObj.con, params=TBRs)
    df.timestamp = df.timestamp.astype("uint32")
    df.tbr_serial_id = df.tbr_serial_id.astype("uint16")
    df.millisecond = df.millisecond.astype("uint16")
    # tag_data is already float type, tag_id uint16 in case of 'S64K'

    triplets = _adjust_tstamp_drift_of_triplet(df)
    return triplets


# *------------------------------------------------------*
# | Positioning functions used by this and other modules |
# *------------------------------------------------------*


def position_tag(
    cage: CageMeta,
    stations: tdoa.StationData,
    tag_depth: float,
    tstamps: tdoa.Timestamps,
    cageVerify: bool = True,
) -> Optional[tdoa.CoordXYZ]:
    """Attemtps to position and resolve tag positions, returns CoordXYZ if successful.

    Uses station data, cage information, and tag data to call TDOA hyperbola based
    positioning. If successful, attempts to resolve ambiguity of position candidates
    by viewing distance from stations to candidates, and order of arrival. In addition,
    if enabled, tries to validate position based on distance from cage center.
    Returns CoordXYZ(x, y, z) of tag if successful, else returns None.

    Args:
        cage: Instance of CageMeta, used to filter based on cage center.
        stations: Instance of StationData, containing positions of stations, depth of
            stations etc. Used in TDOA algorithm, and for arrival-resolvement.
        tag_depth: depth of tag. Stations depth is subtracted from tag_depth in TDOA.
        tstamps: Instance of dataclass Timestamps, containing second and millisecond
            values for arrival of message in station A, B and C.
        cageVerify: Boolean argument to enable validation based on distance from cage
            center. By default True.

    Returns:
        If valid position candidates are found from TDOA algorithm, resolvement and
        validation is performed. If position is successfully found, it is returned,
        otherwise None is returned.
    """
    # Cage geoemtry used to filter out valid positions (i.e. not outside cage)
    if cage.geometry is None:
        P_A, P_B, P_C = stations.xyz_A, stations.xyz_B, stations.xyz_C
        cageCircle = circleFromThreePoints(P_A, P_B, P_C)
    else:
        cageCircle = cage.geometry.circle

    # Try to find position candidates for tag data
    positions = tdoa.tdoa_hyperbola_algorithm(tag_depth, tstamps, stations)

    # Resolve which solution is correct
    if positions is not None:
        P0, P1, position = tdoa.resolve_position_based_on_order_of_arrival(
            tstamps, stations, positions
        )
        if cageVerify:
            position = tdoa.verify_position_within_sea_cage(
                P0, P1, position, cageCircle
            )

        if position is not None:
            return position
    return None


def position_new_msg(
    msg: msghandler.Message, dbObj: DatabaseManager
) -> Optional[List[tdoa.CoordXYZ]]:
    """Return list of xyz-position of new msg if triplets of tag detections exists.

    Iterates through msg and checks whether two other messages from the same tag_id with
    matching cage TBR IDs exists in database. If so, runs positoning algorithm on tag
    detection triplet, and returns a list of the positions.

    Args:
        msg: Dictionary following msghandler.Message format, where a string is used for
            each key, with corresponding values being of type Union[int, str, float].
        dbObj: dbmanager.DatabaseManager instance, with open connection to database.

    Returns:
        If any positions has been found for tags in message, returns a list of the
        positions. If no positions has been found, returns None.
    """
    # If metadata for positioning doesn't exist, don't run positoning
    if _cages is None or _depth_tags is None:
        logger.warning(
            """
            No metadata information of cage/fjord TBR setup,
            and/or which (tag, frequency) combinations are depth tags.
            Cannot do positioning of tag messages.
            """
        )
        return None
    tag_positions = []
    logger.info("|--- Looking through message packets for depth tag triplets")
    for packet in msg.payload:
        cage = None

        # Skip packet if it isn't a tag detection
        if packet["packetType"] != "tag":
            continue

        # Skip packet if data type is not depth
        tag_id = packet["tag_id"]
        freq = packet["frequency"]
        depthTag = _is_depth_tag(tag_id, freq)
        if not depthTag:
            continue

        # Determine which cage the packet belongs to
        tbr_serial_id = packet["tbr_serial_id"]
        cage, TBRs = _get_cage_and_TBR_data(tbr_serial_id)

        # In case the cage is invalid somehow
        if cage is None:
            logger.error("Cage/fjord TBR is defined wrong in config-file!")
            continue

        # Check if a triplet of tag detections with this cage exists and load tag_data
        ref_timestamp = packet["timestamp"]
        tripletExists, df_tag = _get_tag_df(ref_timestamp, tag_id, freq, TBRs, dbObj)

        # if triplet exists, attempt to do positioning
        if tripletExists:
            logger.info(f"|--- Triplet of tag_id {tag_id} exists")
            try:
                stations = _get_station_data(TBRs, cage.depth, dbObj)
            except ValueError as e:
                logger.error(f"{e} | Couldn't position tag, lacking TBR positions")
            tag_depth, tstamps = _get_tag_depth_and_timestamps(stations, df_tag)

            # Perform TDOA hyperbola based positioning
            # | Uses order of arrival to resolve position ambiguity
            # | In addition, validates candidates whether they are inside/outside cage
            xyzTag = position_tag(cage, stations, tag_depth, tstamps)

            if xyzTag is None:
                logger.info("|------ Could not find valid position")
                continue  # Reject position if it could not be resolved
            # Convert position to latitude-longitude and pack into dataclass
            latlonTag = tdoa.convert_tag_xyz_to_latlong(xyzTag, stations)
            position = Position(
                timestamp=df_tag.timestamp[0],
                tag_id=tag_id,
                frequency=freq,
                cage_name=cage.cageName,
                millisecond=df_tag.millisecond[0],
                x=xyzTag.x,
                y=xyzTag.y,
                z=xyzTag.z,
                latitude=latlonTag.lat,
                longitude=latlonTag.lon,
            )
            tag_positions.append(position)
            x, y, z = round(position.x, 2), round(position.y, 2), round(position.z, 2)
            logger.info(f"|------ Found position: (x, y, z) = ({x}, {y}, {z})")
    if tag_positions:
        return tag_positions


def position_database(dbObj: DatabaseManager):
    """Searches through complete database and returns all found positions as a list.

    Goes through all valid tag_id/frequency combinations for a given project and find
    triplets of them in the database, and uses this as well as station data to position
    all tag messages from all messages. Returns a list of found positions.

    args:
        dbObj: dbmanager.DatabaseManager instance, with connection to main database.

    returns:
        List of all found positions, where each position is an instance of dataclass
        'Position'.
    """
    tag_positions = []
    for tag in _depth_tags:
        tag_id, frequency = tag.tag_id, tag.frequency
        cage = _cages[tag.cageName]
        print(cage)
        print("\n\n-------------------")
        print(f"STARTING TAG_ID {tag_id}")
        print("-------------------")
        for TBRs in cage.tbr:
            print("\n\n-------------------------------------------")
            print(f"STARTING CAGE {tag.cageName} TBRs {TBRs}")
            print("-------------------------------------------")
            A_pos = tdoa.LatLong(cage.geometry.lat_A, cage.geometry.lon_A)
            B_pos = tdoa.LatLong(cage.geometry.lat_B, cage.geometry.lon_B)
            C_pos = tdoa.LatLong(cage.geometry.lat_C, cage.geometry.lon_C)
            tbr_pos = [A_pos, B_pos, C_pos]
            stations = tdoa.StationData(*TBRs, *tbr_pos, cage.depth)
            # print(stations)

            # do positioning for all database messages
            triplets = _get_list_of_triplets_from_db(tag_id, frequency, TBRs, dbObj)
            for df_tag in triplets:
                # print(df_tag)
                if len(df_tag.tbr_serial_id.unique()) < 3:
                    print("Duplicate TBR ID, skipping detection")
                    continue
                elif len(df_tag.index) > 3:
                    print("More than 3 detections of same message, skipping")
                    continue

                tag_depth, tstamps = _get_tag_depth_and_timestamps(stations, df_tag)

                # Perform TDOA hyperbola based positioning
                # | Uses order of arrival to resolve position ambiguity
                # | In addition, validates candidates whether they are inside/outside cage
                xyzTag = position_tag(cage, stations, tag_depth, tstamps)
                if xyzTag:
                    x, y, z = round(xyzTag.x, 2), round(xyzTag.y, 2), round(xyzTag.z, 2)
                    print(f"\t(x, y, z) = ({x},\t\t{y},\t\t{z})")
                    # Convert position to latitude-longitude and pack into dataclass
                    latlonTag = tdoa.convert_tag_xyz_to_latlong(xyzTag, stations)
                    position = Position(
                        timestamp=df_tag.timestamp.iloc[0].item(),
                        tag_id=tag_id,
                        frequency=frequency,
                        cage_name=cage.cageName,
                        millisecond=df_tag.millisecond.iloc[0].item(),
                        x=xyzTag.x,
                        y=xyzTag.y,
                        z=xyzTag.z,
                        latitude=latlonTag.lat,
                        longitude=latlonTag.lon,
                    )
                    # print(position)
                    tag_positions.append(position)
    print("XXXXXXXXXXXXXXXXXXX")
    print("XXXXXXXXXXXXXXXXXXX")
    return tag_positions
