# Python built-in modules and packages
import base64
import json
import time
import toml
import logging
import logging.handlers
from pathlib import Path
from typing import List, Mapping, NoReturn, Optional, Tuple, Union

# Third-party modules and packages
from paho.mqtt import client as mqtt

# Local modules and packages
from src.backend import initbackend
from src.backend.msghandler import msghandler
from src.backend.dbmanager import dbmanager
from src.backend.dbmanager import msgbackup


# --- Useful type hints ---
MQTTConfig = Tuple[str, int, str, str]
MQTTPayload = bytes
Base64BytesStr = str
DecodedMQTTMessage = Mapping[str, Union[Base64BytesStr, float]]
InternetOfFishMessage = bytes

# create logger with 'mqtt_client'
logger = logging.getLogger("mqtt_client")
logger.setLevel(logging.DEBUG)

# Load boolean value to decide whether to position tag messages or not
metaFileName: str = "src/backend/.config/metadata.toml"
positionTags: bool = toml.load(metaFileName)["3D"]["include"]


class CustomFormatter(logging.Formatter):
    """ Logging Formatter to have custom format for the different logging levels. """

    FORMATS = {
        logging.INFO: "{module:11s} - {message}",
        "DEFAULT": "[{asctime}] - {name} - [{levelname:8s}] - {message}",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMATS["DEFAULT"])
        formatter = logging.Formatter(log_fmt, style="{")
        return formatter.format(record)


def init_logging() -> None:
    # create file handler which logs with level WARNING (by default)
    fh = logging.handlers.TimedRotatingFileHandler(
        "src/backend/logs/client.log", when="midnight"
    )
    fh.setLevel(logging.WARNING)
    # create console handler which logs with level DEBUG
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    fh.setFormatter(CustomFormatter())
    ch.setFormatter(CustomFormatter())
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)


def mqtt_client_config() -> MQTTConfig:
    if not Path("src/backend/.config/config.toml").exists():
        logging.warning("no 'src/backend/.config/config.toml' (mqtt config) defined!")
        initbackend.define_mqtt_config(client=True)
    try:
        config = toml.load("src/backend/.config/config.toml")
        address, port, user, pw = (
            config["address_port"]["ip_address"],
            config["address_port"]["port"],
            config["usr_pwd"]["user"],
            config["usr_pwd"]["pwd"],
        )
    except toml.decoder.TomlDecodeError as e:
        logger.warning("MQTT Config file not formatted correctly! Exiting program")
        logger.error(e)
        exit()
    else:
        return (address, port, user, pw)


def unpack_json_payload(payload: MQTTPayload) -> Optional[DecodedMQTTMessage]:
    try:
        decode = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning(f"MQTT Message is wrongly formatted!")
        raise json.JSONDecodeError
    else:
        return decode


def load_iof_mqtt_topics() -> List[Tuple[str, int]]:
    if not Path("src/backend/.config/topics.toml").exists():
        logging.warning(
            "no 'src/backend/.config/topics.toml' (mqtt topics) defined! "
            "Restart client with topics.toml configured and placed correctly. "
            "If you wish to subscribe to wildcard '#', add it as a topic "
            "in the file. Exiting program."
        )
        exit()
    try:
        topDict = toml.load("src/backend/.config/topics.toml")
        logger.info(
            f"Subscribing to topics: {topDict['top']} with qos: {topDict['qos']}"
        )
        topics = list(zip(topDict["top"], topDict["qos"]))
    except toml.decoder.TomlDecodeError as e:
        logger.warning("MQTT topics file not formatted correctly! Exiting program")
        logger.error(e)
        exit()
    else:
        return topics


def on_connect(mqttc, obj, flags, rc) -> None:
    logger.info(f"Connection returned result: {mqtt.connack_string(rc)}")
    logger.info("Reading MQTT project topic names from file")
    topics = load_iof_mqtt_topics()
    mqttc.subscribe(topics)  # topics defined as list of tuples containing name and qos
    # mqttc.subscribe("#", qos=1)  # subscribe to # topic
    # mqttc.subscribe("$SYS/#")  # Subscribe to broker $SYS messages


def on_disconnect(mqttc, obj, rc) -> None:
    if rc != 0:
        logger.info(f"Unexpected disconnection: {mqtt.connack_string(rc)}")


def on_message(mqttc, obj, msg) -> None:
    # Accepts all topics except $SYS topics for message handling
    if msg.topic.startswith("$SYS") is True:
        return

    msgID = None
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{now}] Received new message! ")
    logger.info(f"topic: {msg.topic} | QoS: {msg.qos} ")
    logger.info(f"| payload: {msg.payload}\n")

    # iof client loop
    while True:
        # Unpack data from json, and get data content of message
        try:
            decode = json.loads(msg.payload)
            data = base64.b64decode(decode["data"])
        except json.JSONDecodeError:
            logger.error(f"Failed json unpacking of MQTT payload: {msg.payload}")
            break
        except KeyError:
            logger.error(f"MQTT message formatted wrongly from sender: {decode}")
            break
        # Used for debugging
        except Exception:
            logger.exception(f"Unexpected error occured! {msg.payload}")
            break

        # Unpack, organize, and convert message data
        try:
            message = msghandler.handle_message(data)
        except ValueError as e:
            logger.error(f"{e} | MQTT Message {msg.payload}")
            break
        # Used for debugging
        except Exception:
            logger.exception(f"Unexpected error! {msg.payload} | Data {data}")
            break

        # Insert message data in database
        try:
            msgID = dbmanager.insert_message_in_db(message)
        except ValueError as e:
            logger.error(f"{e}")
            logger.error(f"| MQTT Message {msg.payload}")
            logger.error(f"| header: {message.header}")
            logger.error(f"| payload: {message.payload}")
            break
        # Used for debugging
        except Exception as e:
            logger.exception(f"{e}")
            logger.error(f"| MQTT Message {msg.payload}")
            logger.error(f"| header: {message.header}")
            logger.error(f"| payload: {message.payload}")
            break

        # See if any positions can be found with the latest message
        try:
            # Only look if 'include' set to True in metadata file
            if positionTags:
                dbmanager.position_and_insert_positions_from_msg(message)
        # used for debugging
        except Exception as e:
            logger.exception(f"{e}")
            logger.error(f"| MQTT Message {msg.payload}")
            logger.error(f"| header: {message.header}")
            logger.error(f"| payload: {message.payload}")
        finally:
            break

    # Insert message in backup database, retuns last rowID
    msgbackup.store_message_to_backup_db(decode, msgID)

    # Message handling finished
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{now}] waiting for new message...\n")


def on_publish(mqttmessage_handlerc, obj, mid) -> None:
    logger.info(f"mid: {mid}")


def on_subscribe(mqttc, obj, mid, granted_qos) -> None:
    logger.info(f"Subscribed | mid: {mid}, granted_qos: {granted_qos}")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{now}] waiting for new message...\n")


def on_log(mqttc, obj, level, string) -> None:
    logger.info(string)


def main() -> NoReturn:
    # Get username, password and broker address needed for connection
    address, port, user, pw = mqtt_client_config()

    # Create and start running subscribing client
    mqttc = mqtt.Client(protocol=mqtt.MQTTv311)
    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect
    mqttc.on_publish = on_publish
    mqttc.on_subscribe = on_subscribe
    mqttc.username_pw_set(username=user, password=pw)
    try:
        mqttc.connect(address, port)
    except Exception:
        logger.exception("Error when connecting to mqtt broker! Shutting down")
        raise SystemExit

    logger.info("Starting MQTT client")

    # Start Client loop
    mqttc.loop_forever()


if __name__ == "__main__":
    init_logging()
    msgbackup.init_msgbackup()
    dbmanager.init_databasemanager(positionTags)
    main()
