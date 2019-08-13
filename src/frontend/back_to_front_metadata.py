import toml


# Load back-end metadata file to dict
filename = "../backend/.config/metadata.toml"
meta = toml.load(filename)

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

# Organize all gathered metadata to dict and write to toml-file
metaDict = {"date_range": dateRange, "tags": tags, "tbrs": tbrs, "3D": cage3D}


newFile = "frontend_metadata.toml"
with open(newFile, "w") as f:  # overwrites previous file contents
    toml.dump(metaDict, f)

print("DONE GENERATING FRONTEND METADATA FILE")
