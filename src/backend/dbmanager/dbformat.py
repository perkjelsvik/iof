# Python built-in modules and packages
from typing import Tuple, Union


# --- Useful type hints ---
TableQuerySQL = str
TableInsertSQL = str
RowQuerySQL = str
TableDummySQL = Tuple[TableQuerySQL, RowQuerySQL, Tuple[Union[int, str]]]


# *-----------------------------*
# | SQL STR CONSTRUCT FUNCTIONS |
# *-----------------------------*


def _sql_values_string(numOfValues: int) -> str:
    return f"({'?, '*(numOfValues-1)}?)"


def conversion_columns_values_len() -> Tuple[str, str, str, str, int]:
    # create sql insertion queries
    conv = """
        (serial_number, transmitter_type, tag_id,
        frequency, duty_sec, protocol, auto_off_after_start, lifetime,
        conversion_factor, data_type, cage, comment_range_etc)"""
    noConv = """
        (serial_number, transmitter_type, tag_id,
        frequency, duty_sec, protocol, auto_off_after_start, lifetime,
        data_type, cage, comment_range_etc)"""

    lenConv = 12
    valuesConv = f"VALUES {_sql_values_string(lenConv)}"
    valuesNoConv = f"VALUES {_sql_values_string(lenConv-1)}"
    return conv, valuesConv, lenConv, noConv, valuesNoConv


# *--------------------------*
# | CREATE TABLE SQL QUERIES |
# *--------------------------*


def sql_query_gps_create_table_dummy() -> TableDummySQL:
    """
    returns table gps create statement, dummy data insertion, and dummy data.
    The dummy data is not constructed correctly, all are equal to -1 for
    clarity. Message_id = -1 also ensures that first message_id will be set to 0.

    Example where the right types of data is used in gps message:
        | (1, 754605000, 33, "low battery", 7.31442, 13.59674, 1.2, "3D-fix", 22)

    * DECIMAL(7, 5) and DECIMAL(8, 5) used for latitude and longitude is not supported
    in sqlite like other sql solutions. However, the data affinity will be NUMERIC,
    and the keyword informs users that these numbers should have fixed-precision set to
    5 decimal places.
    """
    query = """
        CREATE TABLE IF NOT EXISTS gps (
            message_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            tbr_serial_id INTEGER NOT NULL,
            slim_status TEXT NOT NULL,
            latitude DECIMAL(7,5),
            longitude DECIMAL(8,5),
            pdop FLOAT NOT NULL,
            fix TEXT NOT NULL,
            num_sat_tracked INTEGER NOT NULL
        );"""  # 11 columns
    table = "gps"
    columns = (
        "(message_id, timestamp, date, hour, tbr_serial_id, "
        "slim_status, latitude, longitude, pdop, fix, num_sat_tracked)"
    )
    numOfValues = 11
    dummy_data = (-1,) * numOfValues
    valuesString = _sql_values_string(numOfValues)
    dummy_query = f"INSERT INTO {table} {columns} VALUES {valuesString};"
    return (query, dummy_query, dummy_data)


def sql_query_tag_create_table_dummy() -> TableDummySQL:
    """
    returns table tage create statement, dummy data insertion, and dummy data.
    The dummy data is not constructed correctly, all are equal to -1 for
    clarity. Message_id = -1 also ensures that first message_id will be set to 0.

    Example where the right types of data is used in gps message:
        | (1, 33, 754605000, "S256", 69, 88, 6.2, 31, 17, 330)
    """
    query = """
        CREATE TABLE IF NOT EXISTS tag (
            message_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            tbr_serial_id INTEGER NOT NULL,
            comm_protocol TEXT NOT NULL,
            frequency INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            tag_data FLOAT,
            tag_data_raw INTEGER,
            snr INTEGER NOT NULL,
            millisecond INTEGER NOT NULL
        );"""  # 12 columns
    numOfValues = 12
    dummy_data = (-1,) * numOfValues
    table = "tag"
    columns = (
        "(message_id, timestamp, date, hour, tbr_serial_id, "
        "comm_protocol, frequency, tag_id, tag_data, tag_data_raw, snr, millisecond)"
    )
    valuesString = _sql_values_string(numOfValues)
    dummy_query = f"INSERT INTO {table} {columns} VALUES {valuesString};"
    return (query, dummy_query, dummy_data)


def sql_query_tbr_create_table_dummy() -> TableDummySQL:
    """
    returns table tbr create statement, dummy data insertion, and dummy data.
    The dummy data is not constructed correctly, all are equal to -1 for
    clarity. Message_id = -1 also ensures that first message_id will be set to 0.

    Example where the right types of data is used in gps message:
        | (1, 33, 754605000, 9.2, 142, 31, 55, 69, "this is a comment")

    * DECIMAL(3, 1) used for temperature is not supported in sqlite.
    However, the data affinity will be NUMERIC, and the keyword informs users that
    these numbers should have fixed-precision set to 1 decimal places.
    """
    query = """
        CREATE TABLE IF NOT EXISTS tbr (
            message_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            tbr_serial_id INTEGER NOT NULL,
            temperature DECIMAL(3,1),
            temperature_data_raw INTEGER NOT NULL,
            noise_avg INTEGER NOT NULL,
            noise_peak INTEGER NOT NULL,
            frequency INTEGER NOT NULL
        );"""
    table = "tbr"
    numOfValues = 10
    dummy_data = (-1,) * 10
    columns = (
        "(message_id, timestamp, date, hour, tbr_serial_id, "
        "temperature, temperature_data_raw, noise_avg, noise_peak, frequency)"
    )
    valuesString = _sql_values_string(numOfValues)
    dummy_query = f"INSERT INTO {table} {columns} VALUES {valuesString};"
    return (query, dummy_query, dummy_data)


def sql_query_metadata_create_table() -> TableQuerySQL:
    """
    Returns table metadata create statement.
    See src/backend/.config/metadata.toml for relevant construction/format of metadata.
    """
    query = """
        CREATE TABLE IF NOT EXISTS metadata (
            serial_number INTEGER NOT NULL,
            transmitter_type TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            frequency INTEGER NOT NULL,
            duty_sec TEXT NOT NULL,
            protocol TEXT NOT NULL,
            auto_off_after_start TEXT NOT NULL,
            lifetime TEXT NOT NULL,
            conversion_factor REAL,
            data_type TEXT NOT NULL,
            comment_range_etc TEXT,
            cage TEXT NOT NULL
        );"""

    return query


def sql_query_positions_create_table() -> TableQuerySQL:
    query = """
        CREATE TABLE IF NOT EXISTS positions (
            timestamp INTEGER NOT NULL,
            date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            frequency INTEGER NOT NULL,
            cage_name TEXT NOT NULL,
            millisecond INTEGER NOT NULL,
            x FLOAT NOT NULL,
            y FLOAT NOT NULL,
            z FLOAT NOT NULL,
            latitude DECIMAL(7,5),
            longitude DECIMAL(8,5),
            UNIQUE(timestamp, tag_id, frequency)
    );"""
    return query


def sql_query_backup_create_table() -> TableQuerySQL:
    query = """
        CREATE TABLE IF NOT EXISTS backup (
            message_id INTEGER,
            data TEXT NOT NULL,
            SNR REAL NOT NULL
        );"""
    return query


# *-------------------------*
# | INSERT TO TABLE QUERIES |
# *-------------------------*


def sql_query_insert_packet(
    table: str, columns: str, valuesString: str
) -> TableInsertSQL:
    sql_query = f"INSERT INTO {table} {columns} VALUES {valuesString};"
    return sql_query


def sql_query_insert_position() -> TableInsertSQL:
    columns = """
        (timestamp, date, hour, tag_id, frequency, cage_name, millisecond,
        x, y, z, latitude, longitude)"""  # 12 columns
    table = "positions"
    numOfValues = 12
    valuesString = _sql_values_string(numOfValues)
    sql_query = f"INSERT INTO {table} {columns} VALUES {valuesString};"
    return sql_query


def sql_query_insert_backup(msgID: int) -> TableInsertSQL:
    table = "backup"
    if msgID:
        columns = "(message_id, data, snr)"
        valuesString = _sql_values_string(3)
    else:
        columns = "(data, snr)"
        valuesString = _sql_values_string(2)
    sql_query = f"INSERT INTO {table} {columns} VALUES {valuesString}"
    return sql_query


# *------------------------*
# | GET FROM TABLE QUERIES |
# *------------------------*


def sql_query_get_message_id(table: str) -> RowQuerySQL:
    numOfValues = 1
    column = "message_id"
    limit_filter = f"{column} DESC LIMIT {numOfValues}"
    sql_query = f"SELECT {column} FROM {table} ORDER BY {limit_filter};"
    return sql_query


def sql_query_get_ROWID(table: str) -> RowQuerySQL:
    numOfValues = 1
    column = "ROWID"
    limit_filter = f"{column} DESC LIMIT {numOfValues}"
    sql_query = f"SELECT {column} FROM {table} ORDER BY {limit_filter};"
    return sql_query


def sql_query_get_latest_TBR_pos(tbr_id: int, pdop: float) -> RowQuerySQL:
    # Get newest latitude/longitude positions for TBRs
    numOfValues = 1
    table = "gps"
    columns = "latitude, longitude"
    fix = "'3D-fix'"
    tbr_filter = f"tbr_serial_id = {tbr_id}"
    fix_filter = f"fix = {fix}"
    pdop_filter = f"pdop < {pdop}"
    limit_filter = f"timestamp DESC LIMIT {numOfValues}"
    sql_query = (
        f"SELECT {columns} FROM {table} "
        f"WHERE {tbr_filter} AND {fix_filter} AND {pdop_filter} "
        f"ORDER BY {limit_filter};"
    )
    return sql_query


def sql_query_tag_df(
    ref_timestamp: int, numOfTBRs: int, tag_id: int, frequency: int, interval: int
) -> str:
    table = "tag"
    columns = "timestamp, millisecond, frequency, tag_id, tag_data, tbr_serial_id"
    tstamp_low = ref_timestamp - interval
    tstamp_high = ref_timestamp + interval

    # Create filters to get appropiate data
    filter_tstamp = f"timestamp BETWEEN {tstamp_low} AND {tstamp_high}"
    substituion = _sql_values_string(numOfTBRs)
    filter_tbr = f"tbr_serial_id IN {substituion}"
    filter_tag = f"tag_id = {tag_id}"
    filter_freq = f"frequency = {frequency}"
    sql_query = (
        f"SELECT {columns} FROM {table} "
        f"WHERE {filter_tstamp} AND {filter_tbr} AND {filter_tag} AND {filter_freq};"
    )
    return sql_query


def sql_query_get_db_all_tag_freq_detections(tag_id, frequency):
    numOfTBRs = 3
    columns = "timestamp, tbr_serial_id, tag_data, millisecond"
    table = "tag"
    tbr_filter = f"tbr_serial_id IN {_sql_values_string(numOfTBRs)}"  # (?, ?, ?)
    freq_filter = f"frequency = {frequency}"
    tag_filter = f"tag_id = {tag_id}"
    sql_query = (
        f"SELECT {columns} FROM {table} "
        f"WHERE {tbr_filter} AND {freq_filter} AND {tag_filter};"
    )
    return sql_query
