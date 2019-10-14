import psycopg2
import urllib3
import requests
import json
import os
import sys
import shutil
import os.path
import argparse
import certifi
from time import sleep
from osgeo import ogr, gdal, osr, gdalconst
from datetime import datetime, timedelta, tzinfo, time

sys.setrecursionlimit (10**8)

conn = None
curr = None
http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=5.0, read=10.0),cert_reqs='CERT_REQUIRED',ca_certs=certifi.where())
pid = str(os.getpid())
agentLogged = False

directory = os.path.dirname(os.path.realpath(__file__)) + "/"
gdal.UseExceptions()

try:
    with open (directory + '/config3.json') as f:
        data = json.load(f)
except:
    print ("Error: Config file does not exist or is corrupt.")
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
    try:
        if agentLogged:
            removeAgent ()

        curr.close()
        conn.close()
    except:
        log ("No connection to close.", "DEBUG")
    sys.exit (exitCode)


def resetPgConnection ():
    conn.cancel ()
    conn.reset ()


def addAgent ():
    global agentLogged
    try:
        curr.execute ("INSERT INTO eolus3.agents (pid, start_time) VALUES (%s, %s)", (pid, datetime.utcnow()))
        conn.commit ()
        agentLogged = True
    except:
        log ("Couldn't add agent.", "ERROR")
        killScript (1)


def removeAgent ():
    log ("Removing agent " + pid, "DEBUG")
    try:
        curr.execute ("DELETE FROM eolus3.agents WHERE pid = %s", (pid,))
        conn.commit ()
        agentLogged = False
    except:
        resetPgConnection ()
        log ("Couldn't add agent.", "ERROR", remote=True)


def getAgentCount ():
    try:
        curr.execute ("SELECT COUNT(*) FROM eolus3.agents")
        conn.commit () 
        result = curr.fetchone()
        return result[0]
    except:
        resetPgConnection ()
        log ("Couldn't get agent count.", "ERROR", remote=True)
        killScript (1)


def log (text, level, indentLevel=0, remote=False, model=''):
    timestamp = datetime.utcnow()
    timeStr = timestamp.strftime("%H:%M:%S")
    indents = ""

    for i in range (0, indentLevel):
        indents += "   "

    print (f"[{level}\t| {timeStr}] {indents}{text}")

    if remote:
        try:
            curr.execute ("INSERT INTO eolus3.log (model, level, timestamp, agent, message) VALUES (%s, %s, %s, %s, %s)", (model, level, timestamp, pid, text))
            conn.commit ()
        except:
            print ("Wasn't logged remotely :(")
            resetPgConnection()


def sqlConnect():
    log ("Connecting to database [" + config["postgres"]["host"] + "]", "INFO") 
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

    clean ()

    try:
        log ("✓ This model is completely finished processing.", "INFO", remote=True, model=modelName)
        curr.execute ("UPDATE eolus3.models SET status = %s WHERE model = %s", ("WAITING", modelName))
        conn.commit ()
        updateRunStatus(modelName)
    except:
        resetPgConnection()
        log ("Couldn't mark model as complete.", "ERROR", remote=True, model=modelName)


def addModelToDb (modelName):
    try:
        log ("✓ Added model to models table.", "INFO", indentLevel=1, remote=True, model=modelName)
        curr.execute ("INSERT INTO eolus3.models (model, status) VALUES (%s, %s)", (modelName, "WAITING"))
        conn.commit ()
    except:
        resetPgConnection()
        log ("Couldn't add model to db.", "ERROR", remote=True, model=modelName)
        killScript (1)


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

    log (f"· Last available timestamp, {str(prev)} runs ago: {str(checkedTime)}", "DEBUG", indentLevel=1)

    return checkedTime


def getNumberOfHours (modelName):
    model = models[modelName]
    fh = model["startTime"]
    i = 0
    while True:
        fh = addAppropriateFhStep (modelName, fh)
        i += 1

        if fh > model["endTime"]:
            return i


def getModelStatus (modelName):
    try:
        curr.execute ("SELECT status FROM eolus3.models WHERE model LIKE '" + modelName + "'")
        result = curr.fetchone()

        return result[0]

    except:
        resetPgConnection()
        return None


def startProcessingModel (modelName, timestamp):

    model = models[modelName]
    formattedTimestamp = timestamp.strftime('%Y%m%d_%HZ')

    log (f"· Started processing {modelName} | {formattedTimestamp} -- making table(s).", "INFO", indentLevel=1, remote=True, model=modelName)
    
    try:
        curr.execute ("UPDATE eolus3.models SET (status, timestamp) = (%s, %s) WHERE model = %s", ("MAKINGTABLE", timestamp, modelName))
        conn.commit ()
    except:
        resetPgConnection()
        killScript(1)

    modelBandArray = makeModelBandArray (modelName)
    tableName = modelName + "_" + formattedTimestamp

    createBandTable (modelName, tableName)

    try:
        curr.execute ("UPDATE eolus3.models SET (status, timestamp) = (%s, %s) WHERE model = %s", ("PROCESSING", timestamp, modelName))
        conn.commit ()

        curr.execute ("DELETE FROM eolus3.run_status WHERE model = %s AND timestamp = %s", (modelName, timestamp))
        conn.commit ()

        curr.execute ("INSERT INTO eolus3.run_status (model, status, timestamp) VALUES (%s, %s, %s)", (modelName, "PROCESSING", timestamp))
        conn.commit ()
    except:
        resetPgConnection()
        log ("Could not set the model status back to processing! This requires manual intervention.", "ERROR", remote=True)



def getFullFh (modelName, fh):
    model = models[modelName]
    return str(fh).rjust (len(str(model["endTime"])), '0')


def createBandTable (modelName, tableName):
    log (f"· Creating table | {tableName}", "NOTICE", indentLevel=1, remote=True, model=modelName)
    try:
        model = models[modelName]
        curr.execute ("CREATE TABLE eolus3." + tableName + " (fh text, status text, band integer, start_time timestamp with time zone, grib_var text, agent text) WITH ( OIDS = FALSE )")
        conn.commit ()

    except:
        resetPgConnection()
        log ("Could not create table. This will probably need to be manually fixed.", "ERROR", remote=True)
        return

    fh = model["startTime"]
    i = 1

    populated = False

    bands = makeModelBandArray(modelName)
    try:
        while not populated:
            fullFh = getFullFh (modelName, fh)
            if bands == None or len(bands) == 0:
                curr.execute ("INSERT INTO eolus3." + tableName + " (fh, status, band) VALUES (%s, %s, %s)", (fullFh, "WAITING", str(i)))
                conn.commit ()
            else:
                for band in bands:
                    curr.execute ("INSERT INTO eolus3." + tableName + " (fh, status, band, grib_var) VALUES (%s, %s, %s, %s)", (fullFh, "WAITING", str(i), band["shorthand"]))
                    conn.commit ()
            fh = addAppropriateFhStep (modelName, fh)
            i += 1

            if fh > model["endTime"]:
                return
    except:
        resetPgConnection()
        log ("An error occurred while making the table (" + tableName + ").", "ERROR", remote=True, model=modelName)
        return


def findModelStepToProcess(modelName):
    found = False
    model = models[modelName]
    fh = model["startTime"]

    try:
        curr.execute ("SELECT timestamp FROM eolus3.models WHERE model = %s", (modelName,))
        timestamp = curr.fetchone()[0]

        formattedTimestamp = timestamp.strftime('%Y%m%d_%HZ')
        tableName = modelName + "_" + formattedTimestamp

    except:
        resetPgConnection()
        log ("Couldn't get the timetamp for model " + modelName, "ERROR", remote=True)

    try:
        curr.execute ("SELECT fh, grib_var FROM eolus3." + tableName + " WHERE status = 'WAITING' ORDER BY band ASC LIMIT 1")
        res = curr.fetchone()
        if not res or len(res) == 0:
            return False
        fullFh = res[0]
        gribVar = res[1]

    except:
        resetPgConnection()
        log ("Couldn't get the status of a timestep from " + tableName, "ERROR", remote=True)
        return False
        

    band = None

    if not gribVar:
        band = None
    else:
        modelBandArray = makeModelBandArray (modelName)
        for bandItem in modelBandArray:
            if bandItem["shorthand"] == gribVar:
                band = bandItem
                break

    bandStr = ""
    if band:
        bandStr = " AND grib_var = '" + band["shorthand"] + "'"

    bandInfoStr = ""
    if band is not None:
        bandInfoStr = " | Band: " + band["shorthand"]

    try:
        curr.execute ("UPDATE eolus3." + tableName + " SET (status, start_time, agent) = (%s, %s, %s) WHERE fh = %s" + bandStr, ("PROCESSING", datetime.utcnow(), pid, fullFh))
        conn.commit ()
    except:
        resetPgConnection()
        log ("Couldn't set a status to processing in " + tableName, "ERROR", remote=True)

    log ("· Attempting to process fh " + fullFh + bandInfoStr, "INFO", remote=True, indentLevel=1, model=modelName)
    processed = processModelStep (modelName, tableName, fullFh, timestamp, band)

    if processed:
        log ("✓ Done.", "INFO", remote=True, indentLevel=1, model=modelName)
        return True

    else:
        try:
            curr.execute ("UPDATE eolus3." + tableName + " SET (status, start_time) = (%s, %s) WHERE fh = %s" + bandStr, ("WAITING", datetime.utcnow(), fullFh))
            conn.commit ()
        except:
            resetPgConnection()
            log ("Couldn't set a status to back to waiting in " + tableName + "... This will need manual intervention.", "ERROR", remote=True)
        return False


def getModelStepStatus (tableName, fullFh):
    try:
        curr.execute ("SELECT status FROM eolus3." + tableName + " WHERE fh = %s", (fullFh,))
        return curr.fetchone()[0]
    except:
        resetPgConnection()
        log ("Couldn't get status for fh " + fullFh + " in table " + tableName, "ERROR", remote=True)


def getBaseFileName (modelName, timestamp, band):
    date = timestamp.strftime ("%Y%m%d")
    time = timestamp.strftime ("%HZ")
    file = modelName + "_" + date + "_" + time
    if band is not None:
        return file + "_" + band["shorthand"]
    else:
        return file


def downloadBand (modelName, timestamp, fh, band, tableName):
    model = models[modelName]

    try:
        curr.execute ("SELECT band FROM eolus3." + tableName + " WHERE fh = %s", (fh,))
        bandNumber = curr.fetchone()[0]
    except:
        resetPgConnection()
        log ("Couldn't get the next band to process, fh " + fh + ", table " + tableName, "ERROR", remote=True, indentLevel=2, model=modelName)
        return False

    url = makeUrl (modelName, timestamp.strftime("%Y%m%d"), timestamp.strftime("%H"), fh)

    fileName = getBaseFileName (modelName, timestamp, band)
    targetDir = config["mapfileDir"] + "/" + modelName + "/" 
    downloadFileName = config["tempDir"] + "/" + fileName + "_t" + fh  + "." + model["filetype"]
    targetFileName = targetDir + fileName + ".tif"

    try:
        response = requests.head(url)
        if response.status_code != 200 or response.status_code == None or response == None:
            log (f"· This index file is not ready yet. " + url, "WARN", remote=True, indentLevel=2, model=modelName)
            return False

        contentLength = str(response.headers["Content-Length"])
    except:
        log (f"· Couldn't get header of " + url, "ERROR", remote=True, indentLevel=2, model=modelName)
        return False

    byteRange = getByteRange (band, url + ".idx", contentLength)

    if not byteRange or byteRange == None:
        log (f"· Band {band['shorthand']} doesn't exist for fh {fh}.", "WARN", remote=True, indentLevel=2, model=modelName)
        try:
            curr.execute ("DELETE FROM eolus3." + tableName + " WHERE fh = %s AND grib_var = %s", (fh,band["shorthand"]))
            conn.commit()
        except:
            resetPgConnection()
            log ("Couldn't delete an unusable band from the table. " + fh + ", table " + tableName, "ERROR", remote=True, indentLevel=2, model=modelName)
        return False


    log (f"↓ Downloading band {band['shorthand']} for fh {fh}.", "NOTICE", indentLevel=2, remote=True, model=modelName)
    try:
        response = http.request('GET',url,
            headers={
                'Range': 'bytes=' + byteRange
            },
            retries=5)

        f = open(downloadFileName, 'wb')
        f.write (response.data)
        f.close ()
    except:
        log ("Couldn't read the band -- the request likely timed out. " + fh + ", table " + tableName, "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    log (f"✓ Downloaded band {band['shorthand']} for fh {fh}.", "NOTICE", indentLevel=2, remote=True, model=modelName)

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    epsg4326 = osr.SpatialReference()
    epsg4326.ImportFromEPSG(4326)

    log ("· Warping downloaded data.", "NOTICE", indentLevel=2, remote=True, model=modelName)
    try:
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
        gribFile = None
    except:
        log ("Warping failed -- " + downloadFileName, "ERROR", remote=True)
        return False

    # check to see if the working raster exists
    if not os.path.exists(targetFileName):
        log (f"· Creating output master TIF | {targetFileName}", "NOTICE", indentLevel=2, remote=True, model=modelName)
        try:
            os.makedirs (targetDir)
        except:
            log ("· Directory already exists.", "INFO", indentLevel=2, remote=True, model=modelName)

        numBands = getNumberOfHours (modelName)

        try:
            gribFile = gdal.Open (downloadFileName + ".tif")
            geoTransform = gribFile.GetGeoTransform()
            width = gribFile.RasterXSize
            height = gribFile.RasterYSize

            newRaster = gdal.GetDriverByName('MEM').Create('', width, height, numBands, gdal.GDT_Float64)
            newRaster.SetProjection (gribFile.GetProjection())
            newRaster.SetGeoTransform (list(geoTransform))
            gdal.GetDriverByName('GTiff').CreateCopy (targetFileName, newRaster, 0)
            log ("✓ Output master TIF created.", "NOTICE", indentLevel=2, remote=True, model=modelName)
        except:
            log ("Couldn't create the new TIF.", "ERROR", indentLevel=2, remote=True, model=modelName)
            return False

    log (f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh} | bandNumber: {str(bandNumber)}", "NOTICE", indentLevel=2, remote=True, model=modelName)

    try:
        # Copy the downloaded band to this temp file
        gribFile = gdal.Open (downloadFileName + ".tif")
        data = gribFile.GetRasterBand(1).ReadAsArray()

        tif = gdal.Open (targetFileName, gdalconst.GA_Update)
        tif.GetRasterBand(bandNumber).WriteArray(data)
        tif.FlushCache()
        gribFile = None
        tif = None
        log (f"✓ Data written to the GTiff | band: {band['shorthand']} | fh: {fh}.", "NOTICE", indentLevel=2, remote=True, model=modelName)
    except:
        log (f"Couldn't write band to TIF | band: {band['shorthand']} | fh: {fh}.", "ERROR", indentLevel=2, remote=True, model=modelName)
        return False
    
    try:
        os.remove(downloadFileName)
        os.remove(downloadFileName + ".tif")
    except:
        log (f"× Could not delete a temp file ({downloadFileName}).", "WARN", indentLevel=2, remote=True, model=modelName)
    
    try:
        curr.execute ("DELETE FROM eolus3." + tableName + " WHERE fh = %s AND grib_var = %s", (fh,band["shorthand"]))
        conn.commit()
    except:
        resetPgConnection()
        log ("Couldn't update the DB that this band was processed.", "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    return True


'''
    Copied a bit from https://github.com/cacraig/grib-inventory/ - thanks!
'''
def getByteRange (band, idxFile, contentLength):
    log (f"· Searching for band defs in index file {idxFile}", "DEBUG", indentLevel=2, remote=True)
    try:
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
            time = parts[5]

            if found:
                endByte = parts[1]
                break

            if varName == varNameToFind and level == levelToFind:
                if "timeRange" in band["band"].keys():
                    rangeVal = time.split (" ", 1)[0]
                    ranges = rangeVal.split("-")
                    if (int(ranges[1]) - int(ranges[0])) != band["band"]["timeRange"]:
                        continue
                    
                log ("✓ Found.", "DEBUG", indentLevel=2, remote=False)
                found = True
                startByte = parts[1]
                continue

        if found:
            if endByte == None:
                endByte = contentLength

            log (f"· Bytes {startByte} to {endByte}", "DEBUG", indentLevel=2)
            if startByte == endByte:
                return None

            return startByte + "-" + endByte
        else:
            log (f"· Couldn't find band def in index file.", "WARN", indentLevel=2, remote=True)
        return None

    except:
        log (f"Band def retrieval failed.", "ERROR", indentLevel=2, remote=True)
        return None


def downloadFullFile (modelName, timestamp, fh, tableName):
    model = models[modelName]
    try:
        curr.execute ("SELECT band FROM eolus3." + tableName + " WHERE fh = %s", (fh,))
        bandNumber = curr.fetchone()[0]
    except:
        resetPgConnection()
        log ("Couldn't get the next fh to process, fh " + fh + ", table " + tableName, "ERROR", remote=True, indentLevel=2, model=modelName)
        return False

    url = makeUrl (modelName, timestamp.strftime("%Y%m%d"), timestamp.strftime("%H"), fh)

    fileName = getBaseFileName (modelName, timestamp, None)
    targetDir = config["mapfileDir"] + "/" + modelName + "/" 
    downloadFileName = config["tempDir"] + "/" + fileName + "_t" + fh  + "." + model["filetype"]

    log (f"↓ Downloading fh {fh}.", "NOTICE", indentLevel=2, remote=True, model=modelName)
    try:
        response = http.request('GET',url,retries=5)

        f = open(downloadFileName, 'wb')
        f.write (response.data)
        f.close ()
        log (f"✓ Downloaded band fh {fh}.", "NOTICE", indentLevel=2, remote=True, model=modelName)
    except:
        log ("Couldn't read the fh -- the request likely timed out. " + fh + ", table " + tableName, "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    try:
        epsg4326 = osr.SpatialReference()
        epsg4326.ImportFromEPSG(4326)

        log ("· Warping downloaded data.", "NOTICE", indentLevel=2, remote=True, model=modelName)
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
        gribFile = None

    except:
        log ("Warping failed -- " + downloadFileName, "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    numBands = getNumberOfHours (modelName)

    bands = makeModelBandArray(modelName, force=True)
    if bands == None:
        try:
            os.makedirs (targetDir)
        except:
            log ("· Directory already exists.", "INFO", indentLevel=2, remote=True, model=modelName)

        targetFileName = targetDir + getBaseFileName (modelName, timestamp, None) + "_t" + fh + ".tif"
        log ("· Copying to " + targetFileName, "NOTICE", indentLevel=2, remote=True, model=modelName)

        try:
            shutil.copyfile (downloadFileName + ".tif", targetFileName)
        except:
            log ("Couldn't copy.","ERROR", indentLevel=2, remote=True, model=modelName)
            return False

    else:
        log (f"· Extracting bands for fh {fh}.", "INFO", indentLevel=2, remote=True, model=modelName)

        for band in bands:
            targetFileName = targetDir + getBaseFileName (modelName, timestamp, band) + ".tif"
            if not os.path.exists(targetFileName):
                log (f"· Creating output master TIF with {str(numBands) } bands | {targetFileName}", "NOTICE", indentLevel=2, remote=True, model=modelName)
                try:
                    os.makedirs (targetDir)
                except:
                    log ("· Directory already exists.", "INFO", indentLevel=2, remote=True, model=modelName)

                try:
                    gribFile = gdal.Open (downloadFileName + ".tif")
                    geoTransform = gribFile.GetGeoTransform()
                    width = gribFile.RasterXSize
                    height = gribFile.RasterYSize

                    newRaster = gdal.GetDriverByName('MEM').Create('', width, height, numBands, gdal.GDT_Float64)
                    newRaster.SetProjection (gribFile.GetProjection())
                    newRaster.SetGeoTransform (list(geoTransform))
                    gdal.GetDriverByName('GTiff').CreateCopy (targetFileName, newRaster, 0)
                    gribFile = None
                    newRaster = None
                    log ("✓ Output master TIF created.", "NOTICE", indentLevel=2, remote=True, model=modelName)
                except:
                    log ("Couldn't create the new TIF.", "ERROR", indentLevel=2, remote=True, model=modelName)
                    return False

            log (f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh}", "NOTICE", indentLevel=2, remote=True, model=modelName)
            # Copy the downloaded band to this temp file
            try:
                gribFile = gdal.Open (downloadFileName + ".tif")
                gribNumBands = gribFile.RasterCount
                bandLevel = getLevelNameForLevel(band["band"]["level"], "gribName")
                tif = gdal.Open (targetFileName, gdalconst.GA_Update)
                for i in range (1, gribNumBands):
                    try:
                        fileBand = gribFile.GetRasterBand(i)
                        metadata = fileBand.GetMetadata()
                        if metadata["GRIB_ELEMENT"].lower() == band["band"]["var"].lower() and metadata["GRIB_SHORT_NAME"].lower() == bandLevel.lower():
                            log ("· Band " +  band["band"]["var"] + " found.", "DEBUG", indentLevel=2)
                            data = fileBand.ReadAsArray()
                            tif.GetRasterBand(bandNumber).WriteArray(data)
                            break

                    except:
                        log (f"× Couldn't read GTiff band: #{str(i)} | fh: {fh}", "WARN", indentLevel=2, remote=True, model=modelName)

                tif.FlushCache()
                gribFile = None
                tif = None
            except:
                log ("Couldn't write bands to the tiff. " + fh + ", table " + tableName, "ERROR", indentLevel=2, remote=True, model=modelName)
                return False

    try:
        os.remove(downloadFileName)
        os.remove(downloadFileName + ".tif")
    except:
        log (f"× Could not delete a temp file ({downloadFileName}).", "WARN", indentLevel=2, remote=True, model=modelName)

    try:
        curr.execute ("DELETE FROM eolus3." + tableName + " WHERE fh = %s", (fh,))
        conn.commit()
    except:
        resetPgConnection()
        log ("Couldn't update the DB that this band was processed.", "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    return True


def processModelStep (modelName, tableName, fullFh, timestamp, band):
    model = models[modelName]
    processed = False

    bandStr = ""
    if band:
        bandStr = " AND grib_var = '" + band["shorthand"] + "'"

    try:
        curr.execute ("SELECT band FROM eolus3." + tableName + " WHERE fh = '" + fullFh + "' " + bandStr)
        bandNumber = curr.fetchone()[0]
    except:
        resetPgConnection()
        log ("× Some other agent finished the model.", "NOTICE", indentLevel=1, remote=True, model=modelName)
        killScript(0)

    fileExists = checkIfModelFhAvailable (modelName, timestamp, fullFh)

    if fileExists:
        log ("· Start processing fh " + fullFh + ".", "INFO",remote=True, model=modelName, indentLevel=1)
        if band is None:
            try:
                success = downloadFullFile (modelName, timestamp, fullFh, tableName)
                if not success:
                    return False
            except:
                return False
        else:
            try:
                success = downloadBand (modelName, timestamp, fullFh, band, tableName)
                if not success:
                    return False
            except:
                return False
    
        processed = True

    #delete the table if all steps are done
    try:
        curr.execute ("SELECT COUNT(*) FROM eolus3." + tableName + " WHERE status != 'DONE'")
        numBandsRemaining = curr.fetchone()[0]
    except:
        resetPgConnection()
        log ("Couldn't get remaining count from table " + tableName + ".", "ERROR", indentLevel=1, remote=True, model=modelName)
        killScript(1)

    log ("· There are " + str(numBandsRemaining) + " remaining bands to process.", "DEBUG", indentLevel=1)

    if numBandsRemaining == 0:
        log ("· Deleting table " + tableName + ".", "NOTICE", indentLevel=1, remote=True, model=modelName)
        try:
            curr.execute ("DROP TABLE eolus3." + tableName)
            conn.commit ()
        except:
            resetPgConnection()
            log ("Couldn't remove the table " + tableName + ".", "ERROR", indentLevel=1, remote=True, model=modelName)
            killScript(1)

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

    log ("× Couldn't match the appropriate step size.", "WARN", indentLevel=1, remote=True, model=modelName)
    return fh


def makeModelBandArray (modelName, force=False):
    model = models[modelName]
    if not "bands" in model.keys():
        return None

    modelBandArray = []
    if model["index"] or force:
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
    log ("· Checking URL: " + url, "DEBUG", remote=True, indentLevel=1, model=modelName)

    try:
        ret = requests.head(url)

        if ret.status_code == 200 or ret.status_code == None:
            log (" ✓ Found.", "DEBUG", remote=True, indentLevel=1, model=modelName)
            return True
        else:
            log ("× Not found.", "DEBUG", remote=True, indentLevel=1, model=modelName)

    except:
        log ("× Not found.", "DEBUG", remote=True, indentLevel=1, model=modelName)
    
    return False


def modelTimestampMatches (modelName, timestamp):
    try:
        curr.execute ("SELECT timestamp FROM eolus3.models WHERE model = %s", (modelName,))
        modelTime = str(curr.fetchone()[0])[0:16]
        tTime = str(timestamp)[0:16]
        return modelTime == tTime
    except:
        resetPgConnection()
        return False


def updateRunStatus (modelName):
    try:
        curr.execute ("UPDATE eolus3.run_status SET status = 'COMPLETE' WHERE model = '" + modelName + "'")
        conn.commit ()
    except:
        resetPgConnection()
        log (f"!!! Could not update run_status!", "ERROR", indentLevel=0, remote=True, model=modelName)


def clean ():
    retentionDays = str(config["retentionDays"])
    log (f"· Deleting rasters from {config['mapfileDir']} older than {retentionDays} days.", "DEBUG", indentLevel=0)
    try:
        os.system (f'find {config["mapFileDir"]}/*/* -mtime +' + retentionDays + ' -exec rm {} \;')
        os.system (f'find {config["tempDir"]}/*/* -mtime +' + retentionDays + ' -exec rm {} \;')
    except:
        log (f"· Couldn't delete old rasters from {config['mapfileDir']}.", "WARN", indentLevel=0, remote=True)

    log (f"· Cleaning logs older than {retentionDays} days.", "DEBUG", indentLevel=0)
    try:
        curr.execute ("DELETE FROM eolus3.log WHERE timestamp < now() - interval '" + retentionDays + " days'")
        conn.commit ()
        curr.execute ("DELETE FROM eolus3.run_status WHERE timestamp < now() - interval '" + retentionDays + " days'")
        conn.commit ()
    except:
        resetPgConnection()
        log (f"· Couldn't delete old logs.", "WARN", indentLevel=0, remote=True)


def init():
    global conn, curr

    # It's THAT kind of script :)
    print ('''
    ╔══════════════════════════════╗
    ║ ░█▀▀ █▀█ █░░ █░░█ █▀▀ █▀▀█░░ ║
    ║  █▀▀ █░█ █░░ █░░█ ▀▀█ ░░▀▄░  ║
    ║  ▀▀▀ ▀▀▀ ▀▀▀ ░▀▀▀ ▀▀▀ █▄▄█   ║
    ╚══════════════════════════════╝
    ''')

    try:
        conn = sqlConnect ()
        curr = conn.cursor()
    except psycopg2.Error as e:
        log ("× Could not connect to database.", "ERROR", indentLevel=1)
        print (str(e))
        print (str(e.pgerror))
        sys.exit (1)

    log ("✓ Connected.", "DEBUG", indentLevel=1)
    printLine()
    print ()

    agents = getAgentCount ()
    if agents < config["maxAgents"]:
        addAgent ()
        try:
            main ()
        except:
            killScript (1)
    else:
        print ("Too many agents already processing.")


def main():

    processingModels = []
    processed = False
    # Check only brand new models, or models that are waiting first
    for modelName, model in models.items():
        log ("Checking " + modelName, "INFO", indentLevel=0)
        # Flag this model as disabled in the DB
        if not model["enabled"]:
            curr.execute ("UPDATE eolus3.models SET status = %s WHERE model = %s", ("DISABLED", modelName))
            conn.commit ()
            log ("× Disabled.", "DEBUG", indentLevel=1)
            print ()
            continue

        timestamp = getLastAvailableTimestamp (model)

        status = getModelStatus (modelName)
        log ("· Status: " + str(status), "INFO", indentLevel=1)

        if status == None:
            if not checkIfModelFhAvailable (modelName, timestamp, getFullFh(modelName, model["startTime"])):
                log ("· This run isn't available yet. Looking back another run.", "INFO", indentLevel=1)
                timestamp = getLastAvailableTimestamp (model,prev=1)
                if not checkIfModelFhAvailable (modelName, timestamp, getFullFh(modelName, model["startTime"])):
                    log ("· This run isn't available yet. Looking back another run.", "INFO", indentLevel=1)
                    timestamp = getLastAvailableTimestamp (model,prev=2)

            addModelToDb (modelName)
            startProcessingModel (modelName, timestamp)
            findModelStepToProcess (modelName)
            processed = True
            break

        # Turn the look behind into a loop, you sociopath
        elif status == "WAITING" or status == "DISABLED":
            shouldProcess = False
            log ("· Checking if this model needs to be processed.", "INFO", indentLevel=1)
            if not modelTimestampMatches (modelName, timestamp):
                log ("· It does -- checking if an update is available.", "INFO", indentLevel=1)
                if checkIfModelFhAvailable (modelName, timestamp, getFullFh(modelName, model["startTime"])):
                    shouldProcess = True
                else:
                    log ("· This run isn't available yet. Looking back another run.", "INFO", indentLevel=1)
                    timestamp = getLastAvailableTimestamp (model,prev=1)
                    if not modelTimestampMatches (modelName, timestamp):
                        if checkIfModelFhAvailable (modelName, timestamp, getFullFh(modelName, model["startTime"])):
                            shouldProcess = True
                        else:
                            log ("· This run isn't available yet. Looking back another run.", "INFO", indentLevel=1)
                            timestamp = getLastAvailableTimestamp (model,prev=2)
                            if not modelTimestampMatches (modelName, timestamp):
                                if checkIfModelFhAvailable (modelName, timestamp, getFullFh(modelName, model["startTime"])):
                                    shouldProcess = True

            else:
                log ("· Nope.", "INFO", indentLevel=1)

            if shouldProcess:
                startProcessingModel (modelName, timestamp)
                findModelStepToProcess (modelName)
                processed = True
                break

        elif status == "PROCESSING":
            processingModels.append (modelName)

        elif status == "MAKINGTABLE":
            log ("Another agent is starting processing for this model", "INFO", indentLevel=1)

        print ()

    if processed:
        log ("✓ Model processing complete.", "NOTICE", indentLevel=0, remote=True, model=modelName)
        printLine ()
        print ()
        print ()
        sleep (1)
        main()

    printLine ()
    log ("No new updates are waiting. Checking models in progress.", "INFO", indentLevel=0)
    print ()
    for modelName in processingModels:
        print (modelName + " ----- ")

        processed = findModelStepToProcess (modelName)
        if processed:
            break

    if not processed:
        log ("No models waiting to process.", "INFO", indentLevel=0)
        printLine ()
        print ()
        killScript (0)

    if processed:
        log ("✓ Model processing complete.", "NOTICE", indentLevel=0, remote=True, model=modelName)
        printLine ()
        print ()
        print ()
        sleep (1)
        main()

if __name__ == "__main__":
    init()