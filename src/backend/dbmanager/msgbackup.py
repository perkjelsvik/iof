# Python built-in modules and packages
import logging
import sqlite3  # only needed for error handling
from typing import Mapping, Optional, Union

# Third-party modules and packages
import toml

# Local modules and packages
from src.backend.dbmanager import dbmanager
from src.backend.dbmanager import dbformat


logger = logging.getLogger("mqtt_client.message_backup")


dbPath = "src/backend/dbmanager/databases/"
dbConfig = "src/backend/.config/db_names.toml"
db = ""

# --- Useful type hints ---
BytesData = str  # base64 format
SNR = float
JSONDict = Mapping[str, Union[BytesData, SNR]]


def init_msgbackup():
    global db
    try:
        dbDict = toml.load(dbConfig)
    except FileNotFoundError as e:
        logger.warning(f"{e} | Did not find toml config file with db_names")
    except toml.decoder.TomlDecodeError as e:
        logger.exception(f"{e} | db_names toml file wrongly formatted")
    else:
        db = dbPath + dbDict["backup_database"]
        logger.info("message backup database path successfully initalized")


def store_message_to_backup_db(msg: JSONDict, msgID: Optional[int] = None) -> None:
    """Stores raw bytearray message as hex in backup database"""
    data, snr = msg["data"], msg["snr"]
    if data == b"":
        raise ValueError("MQTT Message Data is empty!")

    # Create database connection and insert backup
    dbObj = dbmanager.DatabaseManager(db)
    query_insert = dbformat.sql_query_insert_backup(msgID)
    if msgID:
        values = (msgID, data, snr)
    else:
        values = (data, snr)
    try:
        dbObj.add_del_update_db_record(query_insert, values)
    except sqlite3.OperationalError as e:
        logger.error(f"{e} | Error while storing msg {msg} into backup!")

    if msgID is not None:
        logger.info("Successfully stored MQTT msg in backup database")
    else:
        # Something wrong with this message or the handling of it
        # | Message stored in backup without message_id
        table = "backup"
        query_rowID = dbformat.sql_query_get_ROWID(table)
        rowID = dbObj.select_from_db_record(query_rowID)[0][0]  # [(rowid, )]
        logger.warning(f"Inserted raw failed message {msg} in backup, rowID = {rowID}")
    del dbObj  # commit and store changes to database
