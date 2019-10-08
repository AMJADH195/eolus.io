import psycopg2
import urllib3
import requests
import json
import os
import sys
import os.path
import argparse
from osgeo import ogr, gdal, osr, gdalconst
from datetime import datetime, timedelta, tzinfo, time

conn = None
curr = None
http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=5.0, read=10.0))

directory = os.path.dirname(os.path.realpath(__file__)) + "/"
gdal.UseExceptions()

try:
    with open (directory + '/config3.json') as f:
        data = json.load(f)
except:
    print ("Error: Config file does not exist.")
    sys.exit (1)

config = data["config"]
levelMaps = data["levelMaps"]
models = data["models"]

ZERO = timedelta(0)

class UTC(tzinfo):
    def utcoffset(self, dt):
        return ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return ZERO

utc = UTC()

def killScript (exitCode): 
    curr.close()
    conn.close()
    sys.exit (exitCode)


def sqlConnect():
    print ("Connecting to database [" + config["postgres"]["host"] + "]") 
    return psycopg2.connect (
        host=config["postgres"]["host"],
        port=5432,
        dbname=config["postgres"]["db"],
        user=config["postgres"]["user"],
        sslmode="require")

def printLine():
    print ("-----------------")


def makeUrl (modelName, modelDate, modelHour, fh):
    model = models[modelName]
    return model["url"].replace("%D",modelDate).replace("%H",modelHour).replace("%T", fh)


def endModelProcessing (modelName):
    print ("    ✓ This model is completely finished processing.")
    curr.execute ("UPDATE eolus3.models SET status = %s WHERE model = %s", ("WAITING", modelName))
    conn.commit ()


def addModelToDb (modelName):
    print ("    ✓ Added model to models table.")
    curr.execute ("INSERT INTO eolus3.models (model, status, \"bandsLeft\") VALUES (%s, %s, %s)", (modelName, "WAITING", 0))
    conn.commit ()


def getLastAvailableTimestamp (model, prev=0):
    now = datetime.utcnow()
    startOfDay = now - timedelta(
        hours=now.hour, 
        minutes=now.minute, 
        seconds=now.second, 
        microseconds=now.microsecond
    )
    yesterdayMidnight = startOfDay - timedelta(days=1)

    startOfDateChecker = yesterdayMidnight + timedelta(hours=model["updateOffset"])

    maxTime = now - timedelta (hours=prev*model["updateFrequency"])
    nowNotExceeded = True
    checkedTime = startOfDateChecker
    while nowNotExceeded:
        if checkedTime + timedelta(hours=(model["updateFrequency"])) > maxTime:
            break
        else:
            checkedTime = checkedTime + timedelta(hours=(model["updateFrequency"]))

    print ("    · Last available timestamp: " + str(checkedTime))

    return checkedTime


def getModelStatus (modelName):
    try:
        curr.execute ("SELECT status FROM eolus3.models WHERE model LIKE '" + modelName + "'")
        result = curr.fetchone()

        return result[0]

    except:
        return None


def startProcessingModel (modelName, timestamp):

    model = models[modelName]
    formattedTimestamp = timestamp.strftime('%Y%m%d_%HZ')

    print ("    · Processing " + modelName + " | " + formattedTimestamp)
    
    curr.execute ("UPDATE eolus3.models SET (status, timestamp) = (%s, %s) WHERE model = %s", ("PROCESSING", timestamp, modelName))
    conn.commit ()

    modelBandArray = makeModelBandArray (modelName)
    tableName = modelName + "_" + formattedTimestamp

    if len(modelBandArray) == 0:
        print ("    (i) This model is indexless.")
        createBandTable (modelName, tableName)
    else:
        for band in modelBandArray:
            createBandTable (modelName, tableName + "_" + band["shorthand"])


def getFullFh (modelName, fh):
    model = models[modelName]
    return str(fh).rjust (len(str(model["endTime"])), '0')


def getRemainingBandTableCount (modelName):
    curr.execute ("SELECT \"bandsLeft\" FROM eolus3.models WHERE model = %s", (modelName,))
    return curr.fetchone()[0]


def createBandTable (modelName, tableName):
    model = models[modelName]
    curr.execute ("CREATE TABLE eolus3." + tableName + " (fh text, status text, band integer, start_time timestamp with time zone, end_time timestamp with time zone) WITH ( OIDS = FALSE )")
    conn.commit ()

    bandsRemaining = getRemainingBandTableCount (modelName) + 1
    curr.execute ("UPDATE eolus3.models SET \"bandsLeft\" = %s WHERE model = %s", (bandsRemaining, modelName))
    conn.commit ()

    fh = model["startTime"]
    i = 1

    populated = False

    while not populated:
        fullFh = getFullFh (modelName, fh)
        curr.execute ("INSERT INTO eolus3." + tableName + " (fh, status, band) VALUES (%s, %s, %s)", (fullFh, "WAITING", str(i)))
        conn.commit ()
        fh = addAppropriateFhStep (modelName, fh)
        i += 1

        if fh > model["endTime"]:
            return


def findModelStepToProcess(modelName):
    found = False
    model = models[modelName]
    fh = model["startTime"]

    curr.execute ("SELECT timestamp FROM eolus3.models WHERE model = %s", (modelName,))
    timestamp = curr.fetchone()[0]

    formattedTimestamp = timestamp.strftime('%Y%m%d_%HZ')

    while not found:
        fullFh = getFullFh (modelName, fh)
        modelBandArray = makeModelBandArray (modelName)
        tableName = modelName + "_" + formattedTimestamp

        # If empty model band array, just check the only existing table
        if len(modelBandArray) == 0:
            status = getModelStepStatus (tableName, fullFh)
            if status == "WAITING":
                found = processModelStep (modelName, tableName, fullFh, timestamp, None)
                if found:
                    print ("    ✓ Forecast hour " + fullFh + " was processed.")
                    return True

        else:
            for band in modelBandArray:
                status = getModelStepStatus (tableName + "_" + band["shorthand"], fullFh)
                if status == "WAITING":
                    found = processModelStep (modelName, tableName + "_" + band["shorthand"], fullFh, timestamp, band)
                    if found:
                        print ("    ✓ Forecast hour " + fullFh + " for band " + band["shorthand"] + " was processed.")
                        return True

        fh = addAppropriateFhStep (modelName, fh)

        if fh > model["endTime"]:
            print ("    × No model bands/hours are available for processing at this time.")
            return False


def getModelStepStatus (tableName, fullFh):
    curr.execute ("SELECT status FROM eolus3." + tableName + " WHERE fh = %s", (fullFh,))
    return curr.fetchone()[0]


def getBaseFileName (modelName, timestamp, band):
    date = timestamp.strftime ("%Y%m%d")
    time = timestamp.strftime ("%HZ")
    if band is not None:
        return modelName + "_" + date + "_" + time + "_" + band["shorthand"]


def downloadBand (modelName, timestamp, fh, band, tableName):
    model = models[modelName]

    curr.execute ("SELECT band FROM eolus3." + tableName + " WHERE fh = %s", (fh,))
    bandNumber = curr.fetchone()[0]

    url = makeUrl (modelName, timestamp.strftime("%Y%m%d"), timestamp.strftime("%H"), fh)

    fileName = getBaseFileName (modelName, timestamp, band)
    targetDir = config["mapfileDir"] + "/" + modelName + "/bands/" 
    downloadFileName = config["tempDir"] + "/" + fileName + "_t" + fh  + "." + model["filetype"]
    targetFileName = targetDir + fileName + ".tif"

    byteRange = getByteRange (band, url + ".idx")

    if not byteRange:
        print ("       (i) This band doesn't exist.")
    else:
        print ("        ┼ Downloading the data.")
        response = http.request('GET',url,
            headers={
                'Range': 'bytes=' + byteRange
            },
            retries=5)

        f = open(downloadFileName, 'wb')
        f.write (response.data)
        f.close ()
        print ("        ✓ Done.")

        bounds = config["bounds"]
        width = model["imageWidth"]

        epsg4326 = osr.SpatialReference()
        epsg4326.ImportFromEPSG(4326)

        print ("        (i) Warping downloaded data.")
        gribFile = gdal.Open (downloadFileName)
        outFile = gdal.Warp(
            downloadFileName + ".tif", 
            gribFile, 
            format='GTiff', 
            outputBounds=[bounds["left"], bounds["bottom"], bounds["right"], bounds["top"]], 
            dstSRS=epsg4326, 
            width=width,
            resampleAlg=gdal.GRA_CubicSpline)
        outFile.FlushCache()
        outFile = None

        # check to see if the working raster exists
        if not os.path.exists(targetFileName):
            print ("       (i) Making a fresh TIF...")
            try:
                os.makedirs (targetDir)
            except:
                print ("        (i) Directory already exists.")

            curr.execute ("SELECT COUNT(*) FROM eolus3." + tableName)
            numBands = curr.fetchone()[0]

            gribFile = gdal.Open (downloadFileName + ".tif")
            gribSrs = osr.SpatialReference()
            gribSrs.ImportFromWkt (gribFile.GetProjection())
            geoTransform = gribFile.GetGeoTransform()
            width = gribFile.RasterXSize
            height = gribFile.RasterYSize

            newRaster = gdal.GetDriverByName('MEM').Create('', width, height, numBands, gdal.GDT_Float64)
            newRaster.SetProjection (gribSrs.ExportToWkt())
            gdal.GetDriverByName('GTiff').CreateCopy (targetFileName, newRaster, 0)
            print ("       ✓ Fresh TIF created.")

        print ("        (i) Writing the data to the temp GTiff.")
        # Copy the downloaded band to this temp file
        gribFile = gdal.Open (downloadFileName + ".tif")
        data = gribFile.GetRasterBand(1).ReadAsArray()

        tif = gdal.Open (targetFileName, gdalconst.GA_Update)
        tif.GetRasterBand(bandNumber).WriteArray(data)
        tif.FlushCache()

    curr.execute ("UPDATE eolus3." + tableName + " SET status = 'DONE' WHERE fh = %s", (fh,))
    conn.commit()


'''
    Copied a bit from https://github.com/cacraig/grib-inventory/ - thanks!
'''
def getByteRange (band, idxFile):
    print ("        ---> Searching for band defs in index file " + idxFile)
    response = http.request('GET', idxFile)
    data = response.data.decode('utf-8')
    varNameToFind = band["band"]["var"]
    levelToFind = getLevelNameForLevel(band["band"]["level"], "idxName")
    found = False
    startByte = None
    endByte = None

    for line in data.splitlines():
        line = str(line)
        parts = line.split(':')
        varName = parts[3]
        level = parts[4]

        if found:
            endByte = parts[1]
            break

        if varName == varNameToFind and level == levelToFind:
            print ("           ✓ Found.")
            found = True
            startByte = parts[1]
            continue

    if found:
        print ("            (i) Bytes " + startByte + " to " + endByte)
        return startByte + "-" + endByte

    return None


def processModelStep (modelName, tableName, fullFh, timestamp, band):
    model = models[modelName]
    processed = False

    curr.execute ("SELECT band FROM eolus3." + tableName + " WHERE fh = %s", (fullFh,))
    bandNumber = curr.fetchone()[0]

    fileExists = checkIfModelFhAvailable (modelName, timestamp, fullFh)

    if fileExists:
        curr.execute ("UPDATE eolus3." + tableName + " SET (status, start_time) = (%s, %s) WHERE fh = %s", ("PROCESSING", datetime.now(), fullFh))
        conn.commit ()
        if band is None:
            downloadFullFile (modelName, timestamp, fullFh)
        else:
            downloadBand (modelName, timestamp, fullFh, band, tableName)
        processed = True

    #delete the table if all steps are done
    fileName = getBaseFileName (modelName, timestamp, band)
    workingFileName = config["tempDir"]  + "/" + fileName + ".tif"
    curr.execute ("SELECT COUNT(*) FROM eolus3." + tableName + " WHERE status != 'DONE'")
    numBandsRemaining = curr.fetchone()[0]

    print ("    (i) There are " + str(numBandsRemaining) + " remaining bands to process.")

    if numBandsRemaining == 0:
        curr.execute ("DROP TABLE eolus3." + tableName)
        conn.commit ()

        bandsRemaining = getRemainingBandTableCount (modelName) - 1
        curr.execute ("UPDATE eolus3.models SET \"bandsLeft\" = %s WHERE model = %s", (bandsRemaining, modelName))
        conn.commit ()
    
        if bandsRemaining == 0:
            endModelProcessing(modelName)

    # If success, return True
    return processed

    

# This iterates a fh by the appropriate step size,
# given the fh. This is for models where the fh step size
# increases after a certain hour.
def addAppropriateFhStep (modelName, fh):
    model = models[modelName]

    for key in reversed(sorted(model["fhStep"].keys())):

        if fh >= int(key):
            return fh + model["fhStep"][key]

    print ("Couldn't match the appropriate step size.")
    return fh


def makeModelBandArray (modelName):
    model = models[modelName]
    modelBandArray = []
    if model["index"]:
        for band in model["bands"]:
            modelBandArray.append({ 
                "shorthand": band["var"].lower() + "_" + band["level"].lower(),
                "band": band
            })
                

    return modelBandArray


def getLevelNameForLevel (levelShorthand, nameType):
    return levelMaps[levelShorthand][nameType]


def checkIfModelFhAvailable (modelName, timestamp, fh):
    model = models[modelName]
    url = makeUrl (modelName, timestamp.strftime("%Y%m%d"), timestamp.strftime("%H"), fh)
    print ("    ---> Checking URL: " + url)

    try:
        ret = requests.head(url)

        if ret.status_code == 200 or ret.status_code == None:
            print ("        ✓ Found.")
            return True
        else:
            print ("        × Not found.")

    except:
        print ("        × Not found.")
    
    return False


def modelTimestampMatches (modelName, timestamp):
    curr.execute ("SELECT timestamp FROM eolus3.models WHERE model = %s", (modelName,))
    modelTime = str(curr.fetchone()[0])[0:16]
    tTime = str(timestamp)[0:16]
    return modelTime == tTime


def init():
    global conn, curr

    # It's THAT kind of script :)
    print ('''
    ╔══════════════════════════════╗
    ║  █▀▀ █▀▀█ █░░ █░░█ █▀▀ █▀▀█  ║
    ║  █▀▀ █░░█ █░░ █░░█ ▀▀█ ░░▀▄  ║
    ║  ▀▀▀ ▀▀▀▀ ▀▀▀ ░▀▀▀ ▀▀▀ █▄▄█  ║
    ╚══════════════════════════════╝
    ''')

    try:
        conn = sqlConnect ()
        curr = conn.cursor()
    except psycopg2.Error as e:
        print ("    × Could not connect to database.")
        print (str(e))
        print (str(e.pgerror))
        sys.exit (1)

    print ("    ✓ Connected.")
    printLine()
    print ()
    main ()


def main():

    processingModels = []
    processed = False
    # Check only brand new models, or models that are waiting first
    for modelName, model in models.items():
        print ("Checking " + modelName)
        # Flag this model as disabled in the DB
        if not model["enabled"]:
            curr.execute ("UPDATE eolus3.models SET status = %s WHERE model = %s", ("DISABLED", modelName))
            conn.commit ()
            print ("    × Disabled.")
            continue

        timestamp = getLastAvailableTimestamp (model)

        status = getModelStatus (modelName)
        print ("    · Status: " + str(status))

        if status == None:
            if not checkIfModelFhAvailable (modelName, timestamp, getFullFh(modelName, model["startTime"])):
                print ("    · This run isn't available yet. Looking back another run.")
                timestamp = getLastAvailableTimestamp (model,prev=1)

            addModelToDb (modelName)
            startProcessingModel (modelName, timestamp)
            findModelStepToProcess (modelName)
            processed = True
            break

        elif status == "WAITING":
            print ("    (i) Check if this model needs to be processed.")
            if not modelTimestampMatches (modelName, timestamp):
                print ("    (i) It does -- checking if an update is available.")
                if checkIfModelFhAvailable (modelName, timestamp, getFullFh(modelName, model["startTime"])):
                    startProcessingModel (modelName, timestamp)
                    findModelStepToProcess (modelName)
                    processed = True
                    break

        elif status == "PROCESSING":
            processingModels.append (modelName)

        print ()

    if processed:
        print ("✓ Model processing complete.")
        printLine ()
        print ()
        print ()
        main()

    printLine ()
    print ("No new updates are waiting. Checking models in progress.")
    print ()
    for modelName in processingModels:
        print (modelName + " ----- ")

        processed = findModelStepToProcess (modelName)
        if processed:
            break

    if not processed:
        print ("(i) No models waiting to process.")
        printLine ()
        print ()
        killScript (0)

    if processed:
        print ("✓ Model processing complete.")
        printLine ()
        print ()
        print ()
        main()

if __name__ == "__main__":
    init()