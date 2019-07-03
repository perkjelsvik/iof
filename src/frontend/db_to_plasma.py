import sqlite3
import pandas as pd
import pyarrow as pa
import pyarrow.plasma as plasma
import numpy as np
import pickle

start_project_time = 1541498400

# Init
tz = "Europe/Oslo"
date_format = "%Y-%m-%d %H:%M:%S"
depth_tags = tuple(
    *[
        list(range(10, 90, 2))
        + list(range(97, 107))
        + list(range(107, 109))
        + list(range(110, 126, 2))
    ]
)
acc_tags = tuple(range(11, 91, 2))
aqz_tags = tuple(*[list(range(10, 50)) + list(range(97, 107))])
aqz_depth = tuple(*[list(range(10, 50, 2)) + list(range(97, 107))])
ref_depth = tuple(*[list(range(50, 90, 2)) + list(range(110, 126, 2)) + [107, 108]])
ref_tags = tuple(*[list(range(50, 90)) + [107, 108] + list(range(110, 126, 2))])
all_tags = tuple(sorted([*aqz_tags, *ref_tags]))
aqz_tbrs = tuple([732, 735, 837])
ref_tbrs = tuple([730, 734, 836])
all_tbrs = tuple(sorted([*aqz_tbrs, *ref_tbrs]))


def db_sql_query(starts_ts, table):
    # Shared filters
    ts_filt = f"timestamp > {starts_ts}"
    order = "timestamp ASC"
    freq = (69, 71, 73)  # tag and positions
    if table == "tag":
        comm = "S256"
        columns = "timestamp, tbr_serial_id, tag_id, tag_data, snr, millisecond"
        freq_filt = f"frequency IN {freq}"
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
        freq_filt = f"frequency IN {freq}"
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
    df["Date_str"] = df.Date.dt.strftime(date_format)
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
    print(df)
    return df


def write_to_plasma(df, name):
    print("Connecting to Plasma store...")
    client = plasma.connect("/tmp/plasma")
    # Convert the Pandas DataFrame into a PyArrow RecordBatch
    print("Converting df to recordbatch...")
    record_batch = pa.RecordBatch.from_pandas(df)
    # Create the Plasma object from the PyArrow RecordBatch. Most of the work here
    # is done to determine the size of buffer to request from the object store.
    print("Determine size of buffer to request etc...")
    object_id = plasma.ObjectID(np.random.bytes(20))
    mock_sink = pa.MockOutputStream()
    stream_writer = pa.RecordBatchStreamWriter(mock_sink, record_batch.schema)
    stream_writer.write_batch(record_batch)
    stream_writer.close()
    data_size = mock_sink.size()
    buf = client.create(object_id, data_size)
    # Write the PyArrow RecordBatch to Plasma
    print("Write the recordbatch to Plasma...")
    stream = pa.FixedSizeBufferWriter(buf)
    stream_writer = pa.RecordBatchStreamWriter(stream, record_batch.schema)
    stream_writer.write_batch(record_batch)
    stream_writer.close()
    # Seal the Plasma object
    print("Sealing the plasma object in store")
    client.seal(object_id)
    # end the client
    print("Disconnecting from plasma store")
    client.disconnect()
    # Write the new object ID
    print("Storing the object_id to plasma_store")
    with open("plasma_state.pkl", "rb") as f:
        plasma_state = pickle.load(f)
    plasma_state[name] = object_id
    with open("plasma_state.pkl", "wb") as f:
        pickle.dump(plasma_state, f)


def read_from_plasma(name):
    # get the current plasma_state
    with open("plasma_state.pkl", "rb") as f:
        plasma_state = pickle.load(f)
    # get the object ID for the dataframe
    object_id = plasma_state[name]
    # get the client and read from it
    client = plasma.connect("/tmp/plasma")
    # Fetch the Plasma object
    [data] = client.get_buffers([object_id])  # Get PlasmaBuffer from ObjectID
    buffer = pa.BufferReader(data)
    # Convert object back into an Arrow RecordBatch
    reader = pa.RecordBatchStreamReader(buffer)
    record_batch = reader.read_next_batch()
    # Convert back into Pandas
    df = record_batch.to_pandas()
    # close out and finish
    client.disconnect()
    return df


def clean_data(start_ts, name):
    db = "Aquatraz.db"
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


if __name__ == "__main__":
    for type in ("tag", "tbr", "pos"):
        print(f"\n\nNow reading and optimizing {type} data")
        df = clean_data(start_project_time, type)
        print("Write to plasma!")
        write_to_plasma(df, type)
        print(f"DONE sending {type} data to plasma store!")
    print("COMPLETED STORING TO PLASMA STORE, EXITING")
