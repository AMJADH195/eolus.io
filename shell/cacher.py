import json
import argparse
import os
import subprocess
import datetime

# Get the list of cacheable locations/coords
with open('./cache-list.json') as f:
    data = json.load(f)

# Get the settings
with open('./cache-settings.json') as f:
    settings = json.load(f)

# Usage: cacher.py --model gfs
parser = argparse.ArgumentParser()
parser.add_argument ("--model", type=str)
args = parser.parse_args()

# Set up correct times for the lookupForecast args
now = datetime.datetime.now()
date = now.strftime ("%Y%m%d")
time = now.strftime ("%H")

model = args.model
model_dirs = []
directory = "/wxdata/" + model

# Get the list of model outputs from the model's
# base directory
print "------"
print "Checking " + directory
for dirname in os.walk(directory):
    name = dirname[0].rsplit('/', 1)[-1]
    if name != model:
        model_dirs.append (name)

print "Date: " + str(date)
print "Time: " + str(time)
print "------"
print ""

# Loop through each subdirectory in the main model
# directory.  Each cacheable location will be evaluated
# per directory (model output), and when all locations
# have received data, the script will write the cache.json
# to the folder.
for modelout in model_dirs:
    print "====="
    print "Getting data for " + modelout
    prefix = directory + "/" + modelout + "/" + settings["prefixes"][modelout]
    hours = str(settings["numhours"][model])
    print "Prefix: " + prefix
    print "No. Hours: " + hours
    final_data = {}
    print ""

    # Loop through all locations and get the forecast
    for location in data:
        coords = data[location]["coords"]
        print "--> Caching data for " + data[location]["name"]
        model_data = subprocess.check_output([
            "/wxdata/lookupForecast",
            str(coords[0]),
            str(coords[1]),
            str(prefix),
            str(date),
            str(time),
            hours,
            "1"
        ])

        final_data[location] = model_data.splitlines()

    # Write the combined dictionary of forecast locations
    # for this model output to the directory
    print ""
    print "Done with " + modelout + ", saving cache JSON."
    with open (directory + "/" + modelout + "/cache.json", "w+") as f:
        f.write(json.dumps(final_data))
    print "====="
    print ""