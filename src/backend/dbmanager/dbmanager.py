# Python built-in modules and packages
import logging
import sqlite3
import toml
import numpy as np  # Only needed for sqlite3.adapter
from dataclasses import astuple
from typing import Dict, Union, List, Tuple, Optional

# Local modules and packages
from src.backend.dbmanager import msgconversion
from src.backend.dbmanager import positioning as pos
from src.backend.dbmanager import dbformat


# --- Useful type hints ---
DatafieldName = str
PacketData = Union[int, str, float]
Packet = Dict[DatafieldName, PacketData]
Message = Dict[str, List[Packet]]
DatabasePacket = msgconversion.DatabasePacket
MessageDB = List[DatabasePacket]


logger = logging.getLogger("mqtt_client.dbmanager")

_db = "src/backend/dbmanager/databases/"
_dbConfig = "src/backend/.config/db_names.toml"
_dbPath = ""

# TODO(perkjelsvik) - Better path handling for complete case
# For positioning of complete database
# _db = "databases/"
# _dbConfig = "../.config/db_names.toml"
# _dbPath = "databases/iof.db"


def init_databasemanager():
    global _dbPath
    try:
        dbDict = toml.load(_dbConfig)
    except FileNotFoundError as e:
        logger.warning(f"{e} | Did not find toml config file with db_names")
    except toml.TomlDecodeError as e:
        logger.exception(f"{e} | db_names toml file wrongly formatted")
    else:
        _dbPath = _db + dbDict["main_database"]
        logger.info("database manager (path to main database) successfully initalized")
    finally:
        # Adapters needed to store np-values. Without them, values stored as binary blob
        sqlite3.register_adapter(np.uint64, lambda val: int(val))
        sqlite3.register_adapter(np.uint32, lambda val: int(val))
        sqlite3.register_adapter(np.uint16, lambda val: int(val))
        sqlite3.register_adapter(np.uint8, lambda val: int(val))
        pos.init_metadata()


class DatabaseManager:
    def __init__(self, name: str) -> None:
        try:
            self.con = sqlite3.connect(name)
            self.con.execute("pragma foreign_keys = on")
            self.con.commit()
            self.cur = self.con.cursor()
        except Exception:
            logger.exception("Caught an error while connecting to database")

    def add_del_update_db_record(self, sql_query: str, args=()) -> None:
        self.cur.execute(sql_query, args)
        self.con.commit()
        return

    def select_from_db_record(self, sql_query: str) -> List[Tuple]:
        return self.cur.execute(sql_query).fetchall()

    def __del__(self) -> None:
        self.cur.close()
        self.con.close()


def _db_get_message_number(dbObj: DatabaseManager) -> Tuple[str, int]:
    """
    Function that returns the message number. Should be called once for every message.
    Finds maximum by comparing last message_id of each table, returning maximum + 1.
    As database size grows, this should be faster than using sql command MAX().
    """
    msgID, dbTables = [], ("tag", "tbr", "gps")
    for table in dbTables:
        sql_query = dbformat.sql_query_get_message_id(table)
        id = dbObj.select_from_db_record(sql_query)[0][0]  # [(max_id, )]
        msgID.append(id + 1)
    return max(msgID)


def _db_insert_packet_in_table(dbObj: DatabaseManager, packet: DatabasePacket) -> None:
    """
    Function that inserts packet data to database.
    Input packet is a dataclass containing necessary variables for insertion
        | packet.table: name of table to insert into
        | packet.numOfValues: for nicer printing and construction of sql_values
        | packet.sql_columns: columns as 1 string instead of tuple of strings
        | packet.sql_values: string of (?, ...) for safer sql insertion
        | packet.values: tuple of data, matching order of sql_columns & sql_values
    """
    table = packet.table
    columns, valuesString = (packet.sql_columns, packet.sql_values)
    sql_query = dbformat.sql_query_insert_packet(table, columns, valuesString)
    try:
        dbObj.add_del_update_db_record(sql_query, packet.values)
    except sqlite3.OperationalError as e:
        raise sqlite3.OperationalError(f"{e} | query: {sql_query} | packet {packet}")


def _db_insert_position_in_table(
    dbObj: DatabaseManager, position: pos.Position
) -> None:
    # INSERT INTO 'positions' 'columns' VALUES '(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    sql_query = dbformat.sql_query_insert_position()
    try:
        dbObj.add_del_update_db_record(sql_query, astuple(position))
    except sqlite3.OperationalError as e:
        raise sqlite3.OperationalError(
            f"{e} | query: {sql_query} | position {position}"
        )
    except sqlite3.IntegrityError as e:
        raise sqlite3.IntegrityError(f"{e} | query: {sql_query} | position {position}")
    else:
        logger.info(f"|--- Inserted position of tag {position.tag_id} in database")
        print(f"|--- Inserted position of tag {position.tag_id} in database")


def insert_message_in_db(msg: Message) -> Optional[int]:
    atLeastOneInserted = False
    logger.info("Inserting message to database")  # For nice printing
    dbObj = DatabaseManager(_dbPath)
    msgID = _db_get_message_number(dbObj)
    dbMSG: MessageDB = msgconversion.convert_msg_to_database_format(msg, msgID)

    # Insert each packet to respective database tables
    for i, packet in enumerate(dbMSG):
        logger.info(f"| packet {i} ({packet.table})")  # For nice printing
        try:
            _db_insert_packet_in_table(dbObj, packet)
        except sqlite3.OperationalError as err:
            logger.error(err)
        else:
            atLeastOneInserted = True
    if atLeastOneInserted:
        logger.info("Successfully inserted message to database")
    else:
        raise ValueError("Failed database insertion!")

    # Deleting dbObj commits and saves all insertions, and closes connection to database
    del dbObj
    return msgID


def position_and_insert_positions_from_msg(msg: Message):
    atLeastOneInserted = False
    print()
    logger.info("Looking for new positions from msg")
    dbObj = DatabaseManager(_dbPath)
    positions = pos.position_new_msg(msg, dbObj)
    if positions:
        for position in positions:
            try:
                _db_insert_position_in_table(dbObj, position)
            except sqlite3.OperationalError as e:
                logger.error(e)
            except sqlite3.IntegrityError as e:
                logger.error(e)
            else:
                atLeastOneInserted = True
        if atLeastOneInserted:
            logger.info("Successfully positioned this message")
    else:
        logger.info(f"No positions found from this message")
    print()  # for nice printing
    del dbObj


def go_through_database_for_positions() -> None:
    # Adapters needed to store np-values. Without them, values stored as binary blob
    sqlite3.register_adapter(np.uint64, lambda val: int(val))
    sqlite3.register_adapter(np.uint32, lambda val: int(val))
    sqlite3.register_adapter(np.uint16, lambda val: int(val))
    sqlite3.register_adapter(np.uint8, lambda val: int(val))
    pos.init_metadata(old=False)
    # dbObj = DatabaseManager("src/backend/dbmanager/databases/Aquatraz.db")
    dbObj = DatabaseManager("src/backend/dbmanager/databases/iof.db")
    # dbObj = DatabaseManager("databases/iof_bench.db")
    # dbObj2 = DatabaseManager("databases/benchmark.db")
    # dbObj = DatabaseManager("databases/iof.db")
    # dbObj2 = DatabaseManager("databases/iof2.db")
    positions = pos.position_database(dbObj)
    for position in positions:
        try:
            _db_insert_position_in_table(dbObj, position)
        except sqlite3.OperationalError as e:
            # logger.error(e)
            print(e)
        except sqlite3.IntegrityError as e:
            # logger.error(e)
            print(e)
        except Exception as e:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(e)
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("Completed positioning of database")
    del dbObj


# TODO(perkjelsvik) - Improve path handling for positioning complete database
if __name__ == "__main__":
    go_through_database_for_positions()
