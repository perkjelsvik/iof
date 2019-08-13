import utm
import toml
import numpy as np


def cart2pol(x, y):
    r = np.sqrt(x ** 2 + y ** 2)
    theta = np.arctan2(y, x)
    return (theta, r)


def pol2cart(theta, r):
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return (x, y)


def extract_positioning_b_cx_cy(dict_3D):
    cageMeta = {}
    for cage in dict_3D["cages"]:
        lat_A, lon_A = (
            dict_3D[cage]["latlong"]["lat_A"],
            dict_3D[cage]["latlong"]["lon_A"],
        )
        lat_B, lon_B = (
            dict_3D[cage]["latlong"]["lat_B"],
            dict_3D[cage]["latlong"]["lon_B"],
        )
        lat_C, lon_C = (
            dict_3D[cage]["latlong"]["lat_C"],
            dict_3D[cage]["latlong"]["lon_C"],
        )
        utm_A = utm.from_latlon(lat_A, lon_A)
        utm_B = utm.from_latlon(lat_B, lon_B)
        utm_C = utm.from_latlon(lat_C, lon_C)

        # Find the distance from B to A and from C to A
        BA = np.array([utm_B[0] - utm_A[0], utm_B[1] - utm_A[1]])
        CA = np.array([utm_C[0] - utm_A[0], utm_C[1] - utm_A[1]])

        # Find the angle to rotate B to x=0, and which angle to rotate C with
        theta_b, b = cart2pol(BA[0], BA[1])
        theta_c, r_c = cart2pol(CA[0], CA[1])
        theta_c_t = theta_c - theta_b

        # Find xy-coordinate for C
        cx, cy = pol2cart(theta_c_t, r_c)

        # Add to cageMeta dictionary (convert numpy64.float to float)
        cageMeta[cage] = {"b": float(b), "cx": float(cx), "cy": float(cy)}
    return cageMeta


def convert_backend_meta_to_frontend(filename_backend, filename_frontend):
    # Load back-end metadata file to dict
    meta = toml.load(filename_backend)

    # Extract date-range and 3D
    dateRange = meta["date_range"]
    cage3D = meta["3D"]

    # Prepare for extraction of tag ID metadata
    tags = meta["tags"]
    freqTags = {"frequencies": []}
    dataTags = {"datatypes": ["all"]}
    cageTags = {"cages": ["all"]}
    allTags = []

    # Iterate through tag dict keys
    for key in tags:
        # Check if this tag ID should be included in the frontend metadata
        if not tags[key]["in"]:  # in = include
            continue

        # Extract frequency, datatype, cage name and tag ID
        frequency = str(tags[key]["f"])  # f = frequency
        datatype = tags[key]["dt"]  # dt = dataype
        cagename = tags[key]["cn"]  # cn = cagename
        tagID = int(tags[key]["i"])  # i = tag_id

        # For every new frequency, datatype, or cage, add a new list
        if frequency not in freqTags:
            freqTags[frequency] = []
            freqTags["frequencies"].append(int(frequency))
        if datatype not in dataTags:
            dataTags[datatype] = []
            dataTags["datatypes"].append(datatype)
        if cagename not in cageTags:
            cageTags[cagename] = []
            cageTags["cages"].append(cagename)

        # Add the tag ID to the appropriate lists
        freqTags[frequency].append(tagID)
        dataTags[datatype].append(tagID)
        cageTags[cagename].append(tagID)
        allTags.append(tagID)

    # Organize tags metadata into dict
    tags = {
        "all": allTags,
        "frequencies": freqTags,
        "cages": cageTags,
        "datatypes": dataTags,
    }

    # Prepare for TBR serial number metadata extraction
    tbrs = meta["tbrs"]
    cageTBRs = {"cages": ["all"]}
    freqTBRs = {"frequencies": []}
    allTBRs = []

    # Iterate through tbr dict keys
    for key in tbrs:
        # Check if tbr serial number should be included in frontend metadata
        if not tbrs[key]["in"]:
            continue

        # Extract frequency, cagename and tbr serial id
        frequency = str(tbrs[key]["f"])  # f = frequency
        cagename = tbrs[key]["cn"]  # cn = cagename
        tbrID = int(tbrs[key]["i"])  # i = tbr_serial_id

        # For every new frequency and cage, add a new list
        if frequency not in freqTBRs:
            freqTBRs[frequency] = []
            freqTBRs["frequencies"].append(int(frequency))
        if cagename not in cageTBRs:
            cageTBRs[cagename] = []
            cageTBRs["cages"].append(cagename)

        # Add the TBR serial ID to the appropriate lists
        freqTBRs[frequency].append(tbrID)
        cageTBRs[cagename].append(tbrID)
        allTBRs.append(tbrID)

    # Organize tbrs metadata into dict
    tbrs = {"all": allTBRs, "frequencies": freqTBRs, "cages": cageTBRs}
    print(cage3D)
    # Get 3D paramters b, cx, and cy for all cages
    pos_parameters = extract_positioning_b_cx_cy(cage3D)
    print(pos_parameters)
    for cage in pos_parameters:
        cage3D["cages"][cage]["geometry"].update(pos_parameters[cage])
    print(cage3D)
    # Organize all gathered metadata to dict and write to toml-file
    metaDict = {"date_range": dateRange, "tags": tags, "tbrs": tbrs, "3D": cage3D}

    # overwrites previous file contents
    with open(filename_frontend, "w") as f:
        toml.dump(metaDict, f)

    print("DONE GENERATING FRONTEND METADATA FILE")


if __name__ == "__main__":
    backMeta = "../backend/.config/metadata.toml"
    frontMeta = "frontend_metadata.toml"
    convert_backend_meta_to_frontend(backMeta, frontMeta)
