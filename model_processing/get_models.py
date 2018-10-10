import sys
import os
import os.path
import json
from datetime import datetime
from datetime import timedelta
import time
import pprint
import urllib2

def write_to_log (message):
    global config
    with open (directory + "/" + config["logFile"], 'a+') as f:
        timewrite = datetime.now().replace(microsecond=0).strftime ("%Y-%m-%d %H:%M:%S")
        f.write ("[" + timewrite + "] " + message + "\n")

def make_grib_filter_url (modelDate, modelHour, fmtTimestep):
    global model, config
    gribFilterFilename = model["gribFilename"].replace("%D",modelDate).replace("%H",modelHour).replace("%T",fmtTimestep)
    gribDirectory = model["gribDirectory"].replace("%D",modelDate).replace("%H",modelHour).replace("%T",fmtTimestep)

    extraParams = ""

    if "variables" in model:
        for variable in model["variables"]:
            extraParams += "&var_" + variable + "=on"
    else:
        extraParams += "&all_var=on"
        
    if "levels" in model:
        for level in model["levels"]:
            levelName = level.replace (" ", "_")
            extraParams += "&lev_" + levelName + "=on"
    else:
        extraParams += "&all_lev=on"

    # download every grib file from NOMADS grib filter
    return (config["downloadTypes"]["GRIBFILTER"]["connectionProtocol"] + 
        config["downloadTypes"]["GRIBFILTER"]["gribFilterBaseUrl"] + 
        model["gribFilterName"] +
        config["downloadTypes"]["GRIBFILTER"]["gribFilterExtension"] + 
        "file=" + gribFilterFilename +
        config["downloadTypes"]["GRIBFILTER"]["gribFilterParams"] + 
        extraParams +
        "&leftlon=" + config["bounds"]["left"] +
        "&rightlon=" + config["bounds"]["right"] +
        "&toplat=" + config["bounds"]["top"] +
        "&bottomlat=" + config["bounds"]["bottom"] +
        "&dir=" + gribDirectory
    )

def make_file_url (modelDate, modelHour, fmtTimestep):
    global model
    url = model["url"].replace("%D",modelDate).replace("%H",modelHour).replace("%T",fmtTimestep)
    return url

def normalize_extents ():
    global config
    # return array of [xmin ymin xmax ymax]
    xmin = float(config["bounds"]["left"])
    if xmin > 180:
        xmin = xmin - 360
    ymin = config ["bounds"]["bottom"]
    xmax = float(config["bounds"]["right"])
    if xmax > 180:
        xmax = xmax - 360
    ymax = config["bounds"]["top"]

    return [str(xmin), ymin, str(xmax), ymax]


directory = os.path.dirname(os.path.realpath(__file__)) + "/"

if os.path.exists(directory + "/.get_models_lockfile"):
    print "Lock file exists, exiting."
    sys.exit(0)

with open (directory + '/config.json') as f:
    data = json.load(f)

config = data["config"]
models = data["models"]

if not config["debug"]:
    open (directory + '/.get_models_lockfile', 'a').close()

modelsToUpdate = {}
totalEnabledModels = 0

write_to_log ("=======================")
write_to_log ("Model processing start.")
write_to_log ("-----------------------")

# First, for each model, check the latest model run that exists on NCEP
# against the last model run that was retrieved.
for modelName, model in models.items():
    print ""
    print "============================="
    print "Checking " + modelName + "..."
    # model run format on NCEP is YYYYMMDDHH
    now = datetime.utcnow().replace(microsecond=0,second=0,minute=0)

    if not model["enabled"]:
        print "This model is disabled."
        print "============================="
        continue

    lastChecked = datetime.fromtimestamp (0)
    totalEnabledModels += 1

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
            write_to_log (modelName + ": No new run found.")
            break

        modelDate = modelTime.strftime ("%Y%m%d")
        modelHour = modelTime.strftime ("%H")

        print "Checking run for this datetime: " + modelDate + " " + modelHour + "Z"
        
        if model["downloadType"] == "GRIBFILTER":
            gribFilename = model["gribFilename"].replace("%D",modelDate).replace("%H",modelHour).replace("%T",str(model["endTime"]))
            fullDirectory = model["baseDirectory"] + model["gribDirectory"].replace("%D", modelDate).replace("%H", modelHour)
            url = config["downloadTypes"]["GRIBFILTER"]["connectionProtocol"] + config["downloadTypes"]["GRIBFILTER"]["nomadsBaseUrl"] + fullDirectory + "/" + gribFilename
        elif model["downloadType"] == "FILESERIES":
            url = model["url"].replace("%D",modelDate).replace("%H",modelHour).replace("%T",str(model["endTime"]))
        
        print "Checking URL: " + url

        try:
            ret = urllib2.urlopen(url)

            if ret.code == 200 or ret.code == None:
                print " *** New model run found. ***"
                write_to_log (modelName + ": New run found (" + modelDate + modelHour + "Z)")
                modelsToUpdate[modelName] = model
                model["lastUpdated"] = modelTimeTotalSeconds
                break

        except:
            print "Not found."

        # Wait a bit between polling server,
        # per NCEP's usage guidelines.
        time.sleep (config["sleepTime"])

    print "Last updated is now " + str(model["lastUpdated"])
    print "============================="
    print ""

print ""
print ""
print "All models have been checked for updates."
print "Number of models needing updates: " + str(len(modelsToUpdate.items())) + "/" + str(totalEnabledModels)
print ""
print ""
# Parse the list of models needing updates
for modelName, model in modelsToUpdate.items():

    print ""
    print "============================="
    print "Updating " + modelName + "..."
    print "---------------"
    print ""

    workingDir = directory + "/" + config["tempDir"] + modelName + "/"
    if not os.path.exists(workingDir):
        os.makedirs(workingDir)

    modelHour = datetime.fromtimestamp (model["lastUpdated"]).strftime ("%H")
    modelDate = datetime.fromtimestamp (model["lastUpdated"]).strftime ("%Y%m%d")

    write_to_log ("Starting update for " + modelName)

    for modelTimestep in range (model["startTime"], model["endTime"]+1):
        fmtTimestep = str(modelTimestep).rjust (len(str(model["endTime"])), '0')
        url = ""
        # for gdalwarp -te extent clip parameter
        extent = ""

        if model["downloadType"] == "GRIBFILTER":
            url = make_grib_filter_url (modelDate, modelHour, fmtTimestep)
        elif model["downloadType"] == "FILESERIES":
            url = make_file_url (modelDate, modelHour, fmtTimestep)
            # for gdalwarp -te extent clip parameter
            extent = "-te " + " ".join (normalize_extents())
        
        print "---------------"
        print "Downloading grib file for timestep " + fmtTimestep + "/" + str(model["endTime"]) + "..."

        try:
            gribFile = urllib2.urlopen (url)
        except:
            print "URL error.  " + url
            print "Could not get a model for this timestamp.  Moving to the next timestamp..."
            print "---------------"
            print ""
            # Wait a bit between polling server,
            # per NCEP's usage guidelines.
            time.sleep (config["sleepTime"])
            continue
 
        filename = workingDir + modelName + "_" + modelDate + "_" + modelHour + "Z_f" + fmtTimestep

        with open (filename + "." + model["filetype"], 'wb') as outfile:
            outfile.write (gribFile.read())

        print "Downloaded."
        print ""
        print "Reprojecting and converting to GeoTIFF..."
        os.system ("gdalwarp " + filename + "." + model["filetype"] + " " + filename + ".vrt -q -t_srs EPSG:4326 " + extent + " -multi --config CENTER_LONG 0")
        os.system ("gdal_translate -co compress=lzw " + filename + ".vrt " + filename + ".tif")
        print "Filesize: " + str(os.path.getsize(filename + ".tif") * 0.000001) + "MB."
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
        
        if not config["debug"]:
            os.system ("psql -h " + config["postgres"]["host"] + " -d " + config["postgres"]["db"] + " -U " + config["postgres"]["user"] + " --set=sslmode=require -f " + filename + ".sql")

        print ""
        print "Deleting temp files..."
        
        if not config["debug"]:
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
        print ""

    print "Done."
    print "============================="
    print ""
    modelRun = datetime.fromtimestamp(model["lastUpdated"]).strftime ("%Y-%m-%d %H:00:00+00")
    finishTime = datetime.utcnow().strftime ("%Y-%m-%d %H:%M:%S+00")

    if not config["debug"]:
        os.system ("psql -h " + config["postgres"]["host"] + " -d " + config["postgres"]["db"] + " -U " + config["postgres"]["user"] + " --set=sslmode=require -c \"INSERT INTO rasters.update_log VALUES ('" + modelName + "','" + modelRun + "','" + finishTime + "')\"")
    
    write_to_log ("Finished updating " + modelName)

print ""
print ""

if not config["debug"]:
    # Re-save the config json
    with open (directory + '/config.json', 'w') as f:
        json.dump (data, f)
    print "Config rewritten."

    os.remove (directory + '/.get_models_lockfile')
    print "Lock file removed."

write_to_log ("-----------------------")
write_to_log ("Model processing complete.")
write_to_log ("=======================\n")