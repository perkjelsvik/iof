# Python built-in modules and packages
import logging
import os
from pathlib import Path

# Third-party modules and packages
import toml

# Local modules and packages
from src.backend.dbmanager import dbmanager
from src.backend.dbmanager import dbformat


# create logger with 'init_backend' and with level DEBUG
logger = logging.getLogger("main.dbmanager.databaseinit")

dbPath = "src/backend/dbmanager/databases/"
dbConfig = "src/backend/.config/db_names.toml"
dbDict = dict()


def _update_db_config_file(dbName="", dbBackupName="", reset=False) -> None:
    """
    Saves dbName and dbBackupName to 'src/backend/.config/db_names.toml'.
    If reset=True: saves with empty db names to 'src/backend/.config/db_names.toml'.
    """
    global dbDict
    if reset:
        dbDict = {"main_database": "", "backup_database": ""}
    else:
        dbDict = {"main_database": dbName, "backup_database": dbBackupName}
    with open(dbConfig, "w") as f:
        toml.dump(dbDict, f)


# if db_names.toml doesn't exist: create it. If exists, load dbDict from it.
if not Path("src/backend/.config/db_names.toml").exists():
    logger.info(
        "Did not find toml config file for db_names - "
        "creating default empty toml config file"
    )
    _update_db_config_file(reset=True)
else:
    try:
        dbDict = toml.load(dbConfig, _dict=dict)
    except Exception:
        logger.exception("Caught an error while loading db names for backup")


def _ask_yes_no(prompt: str) -> bool:
    """Simple function that prompts user until they answer 'y' or 'n'"""
    answer = input(prompt).lower()
    while answer not in ("y", "n"):
        answer = input("Please enter 'y' or 'n': ").lower()
    if answer == "y":
        return True
    else:
        return False


def _add_metadata_to_database(dbObj: dbmanager.DatabaseManager) -> None:
    """
    loads 'src/backend/.config/metadata.toml' and inserts the data from there in
    metadata table of main database.
    Also saves 'tag_id', 'frequency', and 'conversion_factor' in
    'src/backend/.config/metadata_conversion.toml' for all combinations of tag_id and
    frequency that has a conversion_factor.
    Takes dbObj (DatabaseManager object) of main_database as argument
    """
    # load metadata from .toml file
    try:
        metaDict = toml.load("src/backend/.config/metadata.toml", _dict=dict)
        code = metaDict["code"]
        meta = metaDict["metadata"]
        cages = metaDict["cages"]
    except FileNotFoundError:
        logger.error(
            "no metadata toml file found in src/backend/.config! exiting program"
        )
        exit()
    except Exception:
        logger.exception("Caught an error when loading metadata - not adding to db")
        return None  # simply stop the function at this point

    # extract data from dict and make ready for database insertion
    data = []
    convData = {}
    posData = {"cages": cages, "tags": {}}
    for rowKey in meta:
        row = []
        # Convert python list to str for database insertion: [a, b, c] -> '[a, b, c]'
        for codeKey in meta[rowKey]:
            id = meta[rowKey][code["tag_id"]]
            freq = meta[rowKey][code["frequency"]]
            # extract conversion factors for tag_id and frequency if they exist
            if codeKey == code["conversion_factor"]:
                conv = meta[rowKey][code["conversion_factor"]]
                convRow = {"tag_id": id, "frequency": freq, "conversion_factor": conv}
                convData.update({rowKey: convRow})
            # if tag data is depth, add to position metadata toml-file
            if meta[rowKey][code["data_type"]] == "Depth [m]":
                cageName = meta[rowKey][code["cage_name"]]
                posRow = {"tag_id": id, "frequency": freq, "cage_name": cageName}
                posData["tags"].update({rowKey: posRow})
            row.append(meta[rowKey][codeKey])
        data.append(row)

    print("*--------------------------------------------*")
    print("| Sucessfully loaded data from metadata.toml |")
    print("*--------------------------------------------*")

    # Add conversion factors with tag_id and frequency to separate file
    if convData:
        with open("src/backend/.config/metadata_conversion.toml", "w") as f:
            toml.dump(convData, f)

    # Add cage name with tag_id and frequency to separate file:
    if posData:
        with open("src/backend/.config/metadata_positioning.toml", "w") as f:
            toml.dump(posData, f)

    # create sql insertion queries
    colConv, valConv, lenConv, col, val = dbformat.conversion_columns_values_len()

    # insert metadata in metadata table of main_database
    for i, values in enumerate(data):
        try:
            if len(values) == lenConv:
                dbObj.add_del_update_db_record(
                    f"INSERT INTO metadata {colConv} {valConv};", values
                )
            else:
                dbObj.add_del_update_db_record(
                    f"INSERT INTO metadata {col} {val};", values
                )
        except Exception:
            logger.exception("Caught an error while inserting metadata to db, exiting!")
            logger.info("Exiting program. Make sure metadata correct, please try again")
            exit()

    print("*-------------------------------------------------*")
    print("| Sucessfully done inserting metadata to database |")
    print("*-------------------------------------------------*")


def _delete_databases() -> bool:
    """
    Deletes databases with names from 'src/backend/.config/db_names.toml'
    in 'dbmanager/databases/'
    """
    noDeletions = True
    for key in dbDict:
        try:
            file = dbPath + dbDict[key]
            if Path(file).exists() and file:
                os.remove(file)
                print(f"removed {file} from {dbPath}")
                noDeletions = False
        except Exception:
            logger.exception("Caught an error when deleting db!")
    _update_db_config_file(reset=True)
    return noDeletions


def _create_database_tables(dbObj: dbmanager.DatabaseManager) -> None:
    """
    Creates 'gps', 'tag', 'tbr' database tables,
    based on formats defined in src.dbmanager.databaseformat.
    """
    # add gps table and a dummy data row for gps table
    gps_sql, gps_dummy_sql, gps_dummy_data = dbformat.sql_query_gps_create_table_dummy()
    dbObj.add_del_update_db_record(gps_sql)
    dbObj.add_del_update_db_record(gps_dummy_sql, gps_dummy_data)

    # add tag table and a dummy data row for tag table
    tag_sql, tag_dummy_sql, tag_dummy_data = dbformat.sql_query_tag_create_table_dummy()
    dbObj.add_del_update_db_record(tag_sql)
    dbObj.add_del_update_db_record(tag_dummy_sql, tag_dummy_data)

    # add tbr table and a dummy data row for tbr table
    tbr_sql, tbr_dummy_sql, tbr_dummy_data = dbformat.sql_query_tbr_create_table_dummy()
    dbObj.add_del_update_db_record(tbr_sql)
    dbObj.add_del_update_db_record(tbr_dummy_sql, tbr_dummy_data)

    # add positions table without dummy data row for positions table
    sql_query = dbformat.sql_query_positions_create_table()
    dbObj.add_del_update_db_record(sql_query)


def databases_ready() -> bool:
    """
    Checks if both main and bakup database exists, and return True if they do
    """
    count = 0
    for key in dbDict:
        if dbDict[key]:
            count += 1
    if count == 2:
        return True
    else:
        return False


def check_if_reset_of_iof_wanted(dbName: str, dbBackupName: str) -> bool:
    """
    Checks if new database names match old ones, if they do, prompts user to delete old
    databases. Also checks if old dbDict has different names for databases and prompts
    user to delete these as well if so.
    """
    ans = None
    if [dbName, dbBackupName] == list(dbDict.values()):
        print(f"{dbName} and {dbBackupName} already exists")
        print(
            """
            If you still want to init (fresh start),
            it is recommended to overwrite these databases
            """
        )
        ans = _ask_yes_no("Do you wish to delete them before continuing? [y/n]: ")
        if ans:
            return True
    if (dbDict["main_database"] or dbDict["backup_database"]) and not ans:
        print(f"found other db-files in {dbConfig}")
        ans = _ask_yes_no("Do you want to delete these first? [y/n]: ")
        if ans == "y":
            return True
    return False


def reset_databases() -> None:
    """
    resets package by deleting databases in 'dbmanager/datbases/' and by
    resetting 'src/backend/.config/db_names.toml'. Should be called when --reset
    argument called with main.py
    """
    print(f"NB! You are about to delete all databases in {dbConfig}")
    wantsToReset = _ask_yes_no("Are you sure you wish to proceed? [y/n]: ")
    if wantsToReset:
        logger.warning("Deleting databases in src/backend/dbmanager/databases/")
        noDeletions = _delete_databases()
        if noDeletions:
            print(f"no databases found in {dbConfig}, none deleted")


def init_databases(dbName: str, dbBackupName: str) -> None:
    """
    Creates main_database and backup_database in 'dbmanager/databases/'.
    dbName is name of main_database, dbBackupName is name of backup_database.
    The names will also be saved to 'src/backend/.config/db_names.toml'.
    """
    # Make main database
    print("Creating databases")
    dbObj = dbmanager.DatabaseManager(dbPath + dbName)

    # Create 'gps', 'tag', 'tbr' and 'positions' tables
    _create_database_tables(dbObj)

    if Path("src/backend/.config/metadata.toml").exists():
        # create and insert metadata table as well
        metadata_sql = dbformat.sql_query_metadata_create_table()
        dbObj.add_del_update_db_record(metadata_sql)
        _add_metadata_to_database(dbObj)

    # Close DB
    del dbObj

    # Make backup database
    dbObj = dbmanager.DatabaseManager(dbPath + dbBackupName)

    # create and insert 'backup' table
    backup_sql = dbformat.sql_query_backup_create_table()
    dbObj.add_del_update_db_record(backup_sql)

    # Close DB
    del dbObj

    # Update db_names config file and dbDict
    _update_db_config_file(dbName, dbBackupName)

    for database in dbDict:
        logger.info(f"Done initializing {dbDict[database]}, stored in {dbPath}")

    print("*-------------------------*")
    print("| Done creating databases |")
    print("*-------------------------*")
