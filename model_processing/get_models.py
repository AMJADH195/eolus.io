import sys
import os
import os.path
import json
from datetime import datetime
from datetime import timedelta
import time
import pprint
import urllib2
import subprocess

def write_to_log (message):
    global config
    if config["debug"]:
        print "[LOGMESSAGE] " + message
        return
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

try:
    from osgeo import gdal, osr
except:
    print "Error: GDAL API is not installed for python."
    sys.exit (1)

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
    print "Checking " + modelName + "..."
    print "============================="
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

    # A list of the possible model run hours, e.g. 0, 6, 12, 18
    # This is so that we only check for the existence of models
    # that would exist in the first place -- instead of checking
    # model run times that are never performed for a model
    modelRunPossibilities = []
    i = model["updateOffset"]
    modelRunPossibilities.append (model["updateOffset"])
    while i < 24:
        i += model["updateFrequency"]
        modelRunPossibilities.append (i)


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

        # If this hour does not correspond with the hours
        # that the model is run at, skip it
        if int(modelHour) not in modelRunPossibilities:
            continue

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

    numWarnings = 0
    numErrors = 0 # TODO
    numSkips = 0

    write_to_log ("Starting update for " + modelName)

    # maxTime can be used for debugging purposes to only grab a few model runs per model
    modelLoopEndTime = model["endTime"] + 1
    if config["maxTime"] > 0:
        modelLoopEndTime = config["maxTime"] + 1

    for modelTimestep in range (model["startTime"], modelLoopEndTime):
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
        print "Downloading grib file for timestep " + fmtTimestep + "/" + str(modelLoopEndTime - 1) + "..."

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

        warpFileType = model["filetype"]

        '''
            This is a super magical function that should probably be
            actually made into a standalone function.

            GRIB files generally don't have the same number of bands or
            a consistent band order, even for the same model in one model run.
            For instance, a model might have APCP01 in its f001 timestamp,
            but have that in addition to APCP12 in its f012 timestamp.

            In order for bands to have a consistency (for futuring querying of
            the entire raster as a single Postgres column), we have to build our own
            raster and slowly copy the bands over as we find them.  This was
            previously done with gdal_translate's -b flag, but since -b cannot write
            an empty band to the raster that would mean that any rasters missing a single
            band would have to be skipped.  This is a problem for models like NBM,
            which start dropping useful variables after f080 or so...  yet, still have useful
            variables through their entire model run like TMP.  So, here we are.
        '''
        if "extractBandsByMetadata" in model:
            print " ---> Extracting specific bands."
            warpFileType = "tif"

            # Open the grib file and read the bands and SRS
            gribFile = gdal.Open (filename + "." + model["filetype"])
            gribSrs = osr.SpatialReference()
            gribSrs.ImportFromWkt (gribFile.GetProjection())
            geoTransform = gribFile.GetGeoTransform()
            width = gribFile.RasterXSize
            height = gribFile.RasterYSize
            numSrcBands = gribFile.RasterCount

            # Create an in-memory raster that we will write the desired bands to as we find them
            newRaster = gdal.GetDriverByName('MEM').Create('', width, height, 0, gdal.GDT_Float64)
            newRaster.SetGeoTransform (geoTransform)

            # For each band in the list, search through the bands of the raster for the match
            # if not found, print a warning and write an empty band
            for extractBand in model["extractBandsByMetadata"]:
                extractBandElement = extractBand[0]
                extractBandName = extractBand[1]
                matched = False

                for i in range (1, numSrcBands):
                    band = gribFile.GetRasterBand(i)
                    bandMetadata = band.GetMetadata()
                    if (bandMetadata["GRIB_ELEMENT"] == extractBandElement and
                        bandMetadata["GRIB_SHORT_NAME"] == extractBandName):

                        # WE COULD JUST DO A BREAK HERE BUT -- this warning might be useful
                        # so we're going to iterate the whole thing, even if a match is found
                        # just to alert the user that they might not be getting the expected band
                        if matched:
                            numWarnings += 1
                            print " !!! WARNING : The same variable (" + extractBandElement + " @ " + extractBandName + ") has already been found in the GRIB bands.  They probably have different GRIB_FORECAST_SECONDS values."
                        else:
                            matched = True
                            newBand = newRaster.GetRasterBand (newRaster.RasterCount)
                            data = band.ReadAsArray()
                            dataType = band.DataType
                            newRaster.AddBand(dataType)
                            newBand = newRaster.GetRasterBand (newRaster.RasterCount)
                            newBand.WriteArray (data)
                            newBand.FlushCache()
                if not matched:
                    numWarnings += 1
                    print " !!! WARNING: This run is missing a desired band: " + extractBandElement + " @ " + extractBandName
                    # Add an empty band to not upset the sacred order of raster bands
                    # Careful with the type!  Tif driver gets angry if the types are different across bands
                    newRaster.AddBand(gdal.GDT_Float64)

            newRaster.SetProjection (gribSrs.ExportToWkt())
            outRaster = gdal.GetDriverByName('GTiff').CreateCopy (filename + ".tif", newRaster, 0)

            # This is important, or else gdalwarp and gdal_translate
            # can't read the raster and you get an empty raster in the end
            del newRaster
            del outRaster

        # This could be replaced with gdal library commands but
        # I'm lazy and the documentation is much nicer for the shell commands
        # than it is for the API :)
        os.system ("gdalwarp " + filename + "." + warpFileType + " " + filename + ".vrt -q -t_srs EPSG:4326 " + extent + " -multi --config CENTER_LONG 0 -r average")
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
        else:
            print "Skipped (DEBUG)"

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
        else:
            print "Skipped (DEBUG)"

        print ""
        print "Tasks complete, moving to next model timestep."
        print "---------------"
        print ""

    print "Done."
    print "Err: " + str(numErrors) + " | Skips: " + str(numErrors) + " | Warn: " + str(numWarnings)
    print "============================="
    print ""
    modelRun = datetime.fromtimestamp(model["lastUpdated"]).strftime ("%Y-%m-%d %H:00:00+00")
    finishTime = datetime.utcnow().strftime ("%Y-%m-%d %H:%M:%S+00")

    if not config["debug"]:
        os.system ("psql -h " + config["postgres"]["host"] + " -d " + config["postgres"]["db"] + " -U " + config["postgres"]["user"] + " --set=sslmode=require -c \"INSERT INTO rasters.update_log VALUES ('" + modelName + "','" + modelRun + "','" + finishTime + "')\"")
        os.system ("psql -h " + config["postgres"]["host"] + " -d " + config["postgres"]["db"] + " -U " + config["postgres"]["user"] + " --set=sslmode=require -c \"VACUUM ANALYZE rasters." + modelName + ";\"")
        if config["deleteOldTimestamps"]:
            os.system ("psql -h " + config["postgres"]["host"] + " -d " + config["postgres"]["db"] + " -U " + config["postgres"]["user"] + " --set=sslmode=require -c \"DELETE FROM rasters." + modelName + " WHERE timestamp < now()-'1 hour'::interval;\"")
            os.system ("psql -h " + config["postgres"]["host"] + " -d " + config["postgres"]["db"] + " -U " + config["postgres"]["user"] + " --set=sslmode=require -c \"VACUUM ANALYZE rasters." + modelName + ";\"")
    
    write_to_log ("Finished updating " + modelName + " | Err: " + str(numErrors) + " | Skips: " + str(numErrors) + " | Warn: " + str(numWarnings))

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