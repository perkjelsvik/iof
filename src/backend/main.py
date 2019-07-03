# Python built-in modules and packages
import argparse
import logging
import time
from subprocess import Popen
from typing import NoReturn

# Local modules and packages
from src.backend import initbackend


# create logger with 'main'
logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)


def init_logging():
    logPath = "src/backend/logs/main.log"
    # create file handler which logs with level DEBUG
    fh = logging.FileHandler(logPath)
    fh.setLevel(logging.DEBUG)
    # create console handler which also logs with level DEBUG
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)


def main() -> NoReturn:
    """
    A function that spawns the main MQTT client as a subprocess.
    If the MQTT client terminates for some reason, this function will restart
    the client.
    """
    parser = argparse.ArgumentParser(description="Start iof-backend")
    parser.add_argument(
        "--init",
        "-i",
        dest="init",
        action="store_const",
        const=list,
        help="flag to inidicate first-time running",
    )
    parser.add_argument(
        "--databases",
        "-db",
        dest="database",
        metavar="database name",
        type=str,
        nargs="*",
        help=(
            "desired name of main and backup databases"
            "if only one argument is provided, backup is"
            'by default set to "backupDB.db".'
            'If -db argument not provided, will use "IoF.db"'
            "requires -i to run"
        ),
    )
    parser.add_argument(
        "--reset",
        "-r",
        dest="reset",
        metavar="resetFlag",
        action="store_const",
        const=list,
    )
    parser.add_argument(
        "--config",
        "-c",
        dest="config",
        metavar="mqttConfig",
        action="store_const",
        const=list,
        help=(
            "use this flag if you want to change mqtt config "
            "can't be used together with -reset flag"
        ),
    )
    # COMBAK(perkjelsvik) - Add argument for logger level

    args = parser.parse_args()
    # Be careful! This will delete databases in project folder
    if args.reset:
        initbackend.reset_iof()
    # if user want to change ip-address:port and/or usr:pwd
    if args.config and not args.reset:
        initbackend.define_mqtt_config()
    # Only run init if init flag is set
    if args.init:
        initbackend.init_iof(args)
    if not initbackend.iof_ready():
        logger.warning("application not ready to run")
        print(
            (
                "Please run main.py with --init flag.\n"
                "if unsuccesful, run with --reset flag as well, \n"
                "but be sure to backup any databases in dbmanager/databases"
            )
        )
        exit()
    client = "src.backend.mqttclient"
    # define time now in case of consistent error when running mqtt client
    timeNow = time.time()
    # define wait time in seconds in case of consistent error with client
    timeout, timeLimit = (20, 1)
    while True:
        logger.info(f"Starting {client}")
        p = Popen(f"python -m {client}", shell=True)
        p.wait()
        if time.time() - timeNow < timeLimit:
            logger.warning(
                f"mqtt client terminated in less than {timeLimit} "
                f"seconds. Will wait {timeout} seconds before retrying"
            )
            time.sleep(timeout)
        timeNow = time.time()
        print(f"{client} terminated. Restarting now. Ctrl+C to cancel\n")
        print("--------------------------------")


if __name__ == "__main__":
    init_logging()
    main()
