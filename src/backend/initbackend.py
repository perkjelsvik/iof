# Python built-in modules and packages
import logging
import os
from getpass import getpass
from pathlib import Path
from typing import Dict, Union, List

# Third-party modules and packages
import toml

# Local modules and packages
from src.backend.dbmanager import dbinit
from src.backend import initmetafile


# --- Useful type hints ---
Dict_IPPORT_USRPWD = Dict[str, Dict[str, Union[str, int]]]

# create logger with 'init_backend' and with level DEBUG
logger = logging.getLogger("main.initbackend")
client_logger = logging.getLogger("mqtt_client.mqttconfig")


def _ask_yes_no(prompt: str) -> bool:
    """Simple function that prompts user until they answer 'y' or 'n'"""
    answer = input(prompt).lower()
    while answer not in ("y", "n", "yes", "no"):
        answer = input("Please enter 'y' or 'n': ").lower()
    if answer == "y" or answer == "yes":
        return True
    else:
        return False


def _mqtt_config_ip_port_usr_pwd() -> Dict_IPPORT_USRPWD:
    """
    prompts user to input ip-address, port, username and password for mqtt.
    returns (address, port, user, pwd).
    """
    address = input("Please input ip-address: ")
    if len(address.split(".")) != 4:
        raise ValueError("write ip-address like '127.0.0.1'")
    port = int(input("and port number: "))
    user = input("username: ")
    pwd = getpass()
    return {
        "address_port": {"ip_address": address, "port": port},
        "usr_pwd": {"user": user, "pwd": pwd},
    }


def define_mqtt_config(client: bool = False) -> None:
    """
    prompts user to input ip-address, port, username and password for mqtt
    by calling _mqtt_config_ip_port_usr_pwd().
    Writes result to 'src/backend/.config/config.toml'
    """
    print(
        "need ip-address, port number, username and password for mqtt.\n"
        " | e.g: ip:port = '127.0.0.0.1:1883', usr:passwd = 'iof:iof_pwd'"
    )
    if Path("src/backend/.config/config.toml").exists():
        try:
            config = toml.load("src/backend/.config/config.toml")
            address, port, user, pw = (
                config["address_port"]["ip_address"],
                config["address_port"]["port"],
                config["usr_pwd"]["user"],
                "******",
            )
        except toml.decoder.TomlDecodeError as e:
            if client:
                client_logger.exception(f"{e} | Error loading mqtt config file")
            else:
                logger.exception(f"{e} | Error loading mqtt config file")
        else:
            print(
                f"current configuration\n"
                f" |   ip: {address}\n"
                f" | port: {port}\n"
                f" | user: {user}\n"
                f" | pass: {pw}\n"
            )
    while True:
        try:
            answers = _mqtt_config_ip_port_usr_pwd()
        except ValueError:
            if client:
                client_logger.warning("Incorrect ip-address")
            else:
                logger.warning("Incorrect ip-address")
            print("Please input the data correctly as in the example")
        else:
            with open("src/backend/.config/config.toml", "w") as f:
                toml.dump(answers, f)
            break


def reset_iof() -> None:
    dbinit.reset_databases()
    if Path("src/backend/.config/metadata.toml").exists():
        wantsToDelete = _ask_yes_no("Do you wish to delete 'metadata.toml'? [y/n]: ")
        if wantsToDelete:
            logger.warning(
                "NB! To reinitalize with metadata, you need to "
                "place correctly formatted 'metadata.toml' in 'src/backend/.config/'"
            )
            try:
                os.remove("src/backend/.config/metadata.toml")
            except NotImplementedError as e:
                logger.exception(
                    f"{e} | caught error deleting 'src/backend/.config/metadata.toml'"
                )
            if Path("src/backend/.config/metadata_conversion.toml").exists():
                try:
                    os.remove("src/backend/.config/metadata_conversion.toml")
                except NotImplementedError as e:
                    logger.exception(
                        f"{e} | caught error deleting 'metadata_conversion.toml'"
                    )
            if Path("src/backend/.config/metadata_positioning.toml").exists():
                try:
                    os.remove("src/backend/.config/metadata_positioning.toml")
                except NotImplementedError as e:
                    logger.exception(
                        f"{e} | caught error deleting 'metadata_positioning.toml'"
                    )
    wantsToChange = _ask_yes_no("Do you wish to change mqtt configuration? [y/n]: ")
    if wantsToChange:
        define_mqtt_config()


def iof_ready() -> bool:
    """Returns True if ready to run iof backend. Else returns False"""
    # check that ip-address and port is defined as well as usr/pwd for mqtt
    if not Path("src/backend/.config/config.toml").exists():
        logger.warning("no 'src/backend/.config/config.toml' defined! needed for mqtt")
        define_mqtt_config()
    # Return true if name of main_database and backup_database is defined
    return dbinit.databases_ready()


def init_metadata():
    metaExists = Path("src/backend/.config/metadata.toml").exists()
    if metaExists:
        convertExcel = _ask_yes_no(
            "A metadata.toml file already exists. Do you wish to overwrite "
            "it by converting metadata from an excel (xlsx) file?"
        )
    else:
        convertExcel = _ask_yes_no(
            "No project metadata file exists "
            "(needed for data type conversion, positioning and front-end etc.). "
            "Do you wish to convert metadata from an excel (xlsx) file?"
        )
    if convertExcel:
        logger.info("Converting excel metadata to project metadata.")
        initmetafile.excel_meta_to_toml()
        initmetafile.excel_mqtt_topics_to_toml()
    else:
        logger.info("Not converting excel metadata to project metadata.")


def init_iof(args: List[str]) -> None:
    """
    inits databases. If args contain --metadata it will also load in metadata
    if they exist in 'src/backend/.config/metadata.toml'. If args contain -db argument,
    database names in 'dbmanager/databases/' will be named with arguments
    passed in -db.
    """
    dbBackupName = "backupDB.db"  # default backup name
    if args.database is not None:
        dbName = args.database[0]
        if dbName[-3:] != "db":  # add .db if user forgot
            dbName += ".db"
        if len(args.database) > 1:
            dbBackupName = args.database[1]
            if dbBackupName[-3:] != "db":  # add .db if user forgot
                dbBackupName += ".db"
    else:
        dbName = "iof.db"  # default main name
    resetWanted = dbinit.check_if_reset_of_iof_wanted(dbName, dbBackupName)
    if resetWanted:
        reset_iof()
    init_metadata()
    dbinit.init_databases(dbName, dbBackupName)
    if not Path("src/backend/.config/config.toml").exists():
        define_mqtt_config()
