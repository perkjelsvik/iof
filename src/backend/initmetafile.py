import toml
import pandas as pd
from pathlib import Path


def excel_mqtt_topics_to_toml(
    excelFile="metadata.xlsx", tomlDestination="src/backend/.config/topics.toml"
):
    df = pd.read_excel(excelFile, sheet_name="mqtt_topics")
    d = df.to_dict()
    topics = [d["topic"][row] for row in d["topic"]]
    qos = [d["quality_of_service"][row] for row in d["quality_of_service"]]
    if topics:
        tomlTopics = {"top": topics, "qos": qos}
    else:
        print(
            "WARNING! No topics defined in excel file. Will instead add wildcard '#' as subscription, "
            "meaning backend will subscribe to all topics from broker. "
            "If you do not wish this, either rerun the conversion from excel with topics in excel file, "
            "or remove the subscroption from 'src/backend/.config/topics.toml'."
        )
        tomlTopics = {"top": ["#"], "qos": [1]}

    for topic, qlevel in zip(topics, qos):
        print(f"Adding topic '{topic}' with qos {qlevel}.")

    with open(tomlDestination, "w") as f:
        toml.dump(tomlTopics, f)


def excel_meta_to_toml(
    excelFile="metadata.xlsx", tomlDestination="src/backend/.config/metadata.toml"
):

    # Process the date_range sheet
    df = pd.read_excel(
        excelFile,
        sheet_name="date_range",
        dtype={"Project_start": str, "Project_end": str},
    )
    d = df.to_dict()
    dateDict = {
        "Project_start": d["Project_start"][0],
        "Project_end": d["Project_end"][0],
    }

    # Process the tbrs sheet
    df = pd.read_excel(excelFile, sheet_name="tbrs")
    d = df.to_dict()
    tbrDict = {}
    for row in d["tbr_serial_id"]:
        tbrDict[f"tbr_{row}"] = {
            "tbr_serial_id": d["tbr_serial_id"][row],
            "frequency": d["frequency"][row],
            "include": d["include"][row],
            "cage_name": d["cage_name"][row],
        }

    # Process the 3D sheet
    df = pd.read_excel(excelFile, sheet_name="3D")
    d = df.to_dict()
    dict3D = {
        "include": d["include"][0],
        "active_cages": list(str.split(d["active_cages"][0], ", ")),
    }

    # Process the 3D_cages sheet if include is set to True
    if dict3D["include"]:
        df = pd.read_excel(excelFile, sheet_name="3D_cages")
        d = df.to_dict("list")
        cage3D = {}
        length = len(d["name"])
        for i in range(0, length):
            name = d["name"][i]
            cagename = d["cagename"][i]
            tbrCageDict = {
                "tbrs": [int(tbrID) for tbrID in str.split(d["tbrs"][i], ", ")],
                "tbr_depth": d["tbr_depth"][i],
                "lines_depth": [
                    float(depth) for depth in str.split(d["lines_depth"][i], ", ")
                ],
                "circles_depth": [
                    float(depth) for depth in str.split(d["circles_depth"][i], ", ")
                ],
            }
            geometryDict = {
                "radius": d["radius"][i],
                "centerX": d["centerX"][i],
                "centerY": d["centerY"][i],
            }
            latlongDict = {
                "lat_A": d["lat_A"][i],
                "lon_A": d["lon_A"][i],
                "lat_B": d["lat_B"][i],
                "lon_B": d["lon_B"][i],
                "lat_C": d["lat_C"][i],
                "lon_C": d["lon_C"][i],
            }
            cage3D[name] = {
                "name": cagename,
                "tbr": tbrCageDict,
                "geometry": geometryDict,
                "latlong": latlongDict,
            }
        dict3D["cages"] = cage3D

    # Process the tags sheet
    df = pd.read_excel(excelFile, sheet_name="tags")
    d = df.to_dict()
    tagsDict = {}
    for row in d["tag_id"]:
        tagsDict[f"tag_{row}"] = {
            "s": d["serial_number"][row],
            "t": d["transmitter_type"][row],
            "i": d["tag_id"][row],
            "f": d["frequency"][row],
            "d": d["duty_sec"][row],
            "p": d["protocol"][row],
            "a": d["auto_off_after_start"][row],
            "l": d["lifetime"][row],
            "cf": d["conversion_factor"][row],
            "dt": d["data_type"][row],
            "in": d["include"][row],
            "cn": d["cage_name"][row],
            "cr": d["commentrange_etc"][row],
        }
        if pd.isna(d["conversion_factor"][row]):
            del tagsDict[f"tag_{row}"]["cf"]

    # Add code dictionary for translation between full and shorthand notation
    codeDict = {
        "serial_number": "s",
        "transmitter_type": "t",
        "tag_id": "i",
        "frequency": "f",
        "duty_sec": "d",
        "protocol": "p",
        "auto_off_after_start": "a",
        "lifetime": "l",
        "include": "in",
        "cage_name": "cn",
        "conversion_factor": "cf",
        "commentrange_etc": "cr",
        "data_type": "dt",
        "tbr_serial_id": "i",
    }

    # Organize all dicts to a toml-compatible dictionary
    tomlDict = {
        "code": codeDict,
        "date_range": dateDict,
        "tbrs": tbrDict,
        "3D": dict3D,
        "tags": tagsDict,
    }

    with open(tomlDestination, "w") as f:
        toml.dump(tomlDict, f)


if __name__ == "__main__":
    if not Path("metadata.xlsx").exists():
        print("Make sure you are running 'python -m src.backend.initmetafile'")
        print("And that 'metadata.xlsx' is in the same location you are running from.")
    else:
        if not Path("src/backend/.config/").exists():
            print("You are not running from root location. Run from outside 'src/'")
            print("Run like so: 'python -m src.backend.initmetafile'")
        else:
            print("Now converting metadata from excel file to project metadata file")
            excel_meta_to_toml()
            print("Now making a 'topics.toml' file for MQTT topics.")
            excel_mqtt_topics_to_toml()
