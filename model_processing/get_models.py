import os
import json
from datetime import datetime
from datetime import timedelta
import time
import pprint
import urllib2

with open ('config.json') as f:
    data = json.load(f)

config = data["config"]
models = data["models"]

modelsToUpdate = {}

# First, for each model, check the latest model run that exists on NCEP
# against the last model run that was retrieved.
for modelName, model in models.items():
    
    print ""
    print "============================="
    print "Checking " + modelName + "..."

    # model run format on NCEP is YYYYMMDDHH
    now = datetime.utcnow().replace(microsecond=0,second=0,minute=0)

    if not model["enabled"]:
        continue

    lastChecked = datetime.fromtimestamp (0)

    if model["lastUpdated"] != "":
        lastChecked = datetime.utcfromtimestamp(model["lastUpdated"])

    print "Last checked: " + lastChecked.strftime ("%Y %m %d %HZ")

    modelTime = now
    modelTimeTotalSeconds = 0

    # Look up to 24 hours back in time
    for hourSubtract in range (0, 25):
        modelTime = now-timedelta(hours=hourSubtract)

        modelTimeTotalSeconds = time.mktime(modelTime.timetuple())
        lastCheckedTotalSeconds = time.mktime(lastChecked.timetuple())

        if modelTimeTotalSeconds <= lastCheckedTotalSeconds:
            print "No new model run has been found."

        timeString = modelTime.strftime ("%Y%m%d")
        

        if model["includeHourInPrefix"]:
            timeString = modelTime.strftime ("%Y%m%d%H")

        print "Checking run for this datetime: " + timeString + " " + modelTime.strftime ("%H") + "Z"

        url = (config["connectionProtocol"] + config["nomadsBaseUrl"] + model["nomadsPrefix"] +
                timeString + model["nomadsSuffix"] + model["gribFilterFileStart"] + modelTime.strftime ("%H") +
                model["gribFilterFileMiddle"] + str(model["endTime"]) + model["gribFilterFileEnd"])

        print "Checking URL: " + url

        try:
            ret = urllib2.urlopen(url)

            if ret.code == 200:
                print "New model run found."
                modelsToUpdate[modelName] = model
                break

        except:
            print "Not found."

    model["lastUpdated"] = modelTimeTotalSeconds
    print "Last updated is now " + str(model["lastUpdated"])

    print "============================="
    print ""

print ""
print ""
print "All models have been checked for updates."
print "Number of models needing updates: " + str(len(modelsToUpdate.items()))
print ""
print ""
# Parse the list of models needing updates
for modelName, model in modelsToUpdate.items():

    print ""
    print "============================="
    print "Updating " + modelName + "..."
    print "---------------"
    print ""

    workingDir = config["tempDir"] + modelName + "/"
    if not os.path.exists(workingDir):
        os.makedirs(workingDir)

    modelHour = datetime.fromtimestamp (model["lastUpdated"]).strftime ("%H")
    modelDate = datetime.fromtimestamp (model["lastUpdated"]).strftime ("%Y%m%d")

    for modelTimestep in range (model["startTime"], model["endTime"]+1):

        fmtTimestep = str(modelTimestep).rjust (2, '0')
        # download every grib file from NOMADS grib filter
        url = (config["connectionProtocol"] + config["gribFilterBaseUrl"] + model["gribFilterName"] +
            config["gribFilterExtension"] + "file=" + model["gribFilterFileStart"] + modelHour +
            model["gribFilterFileMiddle"] + fmtTimestep + model["gribFilterFileEnd"] +
            config["gribFilterParams"] + 
            "&leftlon=" + config["bounds"]["left"] +
            "&rightlon=" + config["bounds"]["right"] +
            "&toplat=" + config["bounds"]["top"] +
            "&bottomlat=" + config["bounds"]["bottom"] +
            "&dir=" + model["gribFilterDirPrefix"] + modelDate + model["gribFilterDirSuffix"])

        print "---------------"
        print "Downloading grib file for timestep " + fmtTimestep + "..."

        gribFile = urllib2.urlopen (url)
        filename = workingDir + modelName + "_" + modelDate + "_" + modelHour + "Z_f" + fmtTimestep

        with open (filename + ".grib2", 'wb') as outfile:
            outfile.write (gribFile.read())

        print "Downloaded."
        print ""
        print "Reprojecting and converting to GeoTIFF..."
        os.system ("gdalwarp " + filename + ".grib2 " + filename + ".tif" + " -q -t_srs EPSG:4326 -overwrite -multi --config CENTER_LONG 0 ")
        
        print ""
        print "Running raster2pgsql..."
        os.system ("raster2pgsql -a -s 4326 " + filename + ".tif" + " rasters." + modelName + " > " + filename + ".sql")

        print ""
        print "Editing SQL to include timestep..."
        sql = ""
        with open(filename + ".sql") as sqlFile:
            sql = sqlFile.read()

        runTime = datetime.fromtimestamp(model["lastUpdated"])+timedelta(hours=modelTimestep)
        timestamp = runTime.strftime ("%Y-%m-%d %H:00:00+00")

        print "Timestamp: " + timestamp

        sql = sql.replace ('("rast") VALUES (', '("timestamp","rast") VALUES (\'' + timestamp + '\',')

        with open(filename + ".sql", 'w') as sqlFile:
            sqlFile.write (sql)

        print "The file has been rewritten."
        print ""

        print "Loading into database..."

        os.system ("psql -h " + config["postgres"]["host"] + " -d " + config["postgres"]["db"] + " -U " + config["postgres"]["user"] + " --set=sslmode=require -f " + filename + ".sql")

        print ""
        print "Deleting temp files..."

        for aFile in os.listdir(workingDir):
            filePath = os.path.join(workingDir, aFile)
            try:
                if os.path.isfile(filePath):
                    os.unlink(filePath)
            except Exception as e:
                print(e)

        print ""
        print "Tasks complete, moving to next model timestep."


        print "---------------"

    print "Done."
    print "============================="
    print ""

# Re-save the config json
with open ('config.json') as f:
    json.dump (data, f)