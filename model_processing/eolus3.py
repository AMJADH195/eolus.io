import psycopg2
import urllib3
import requests
import json
import os
import sys
import os.path
import argparse
from osgeo import gdal, osr
from datetime import datetime, timedelta, tzinfo, time

conn = None
curr = None

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
    print ("Connecting to db...")
    return psycopg2.connect (
        host=config["postgres"]["host"],
        port=5432,
        dbname=config["postgres"]["db"],
        user=config["postgres"]["user"],
        sslmode="require")

def makeUrl (modelName, modelDate, modelHour, fh):
    model = models[modelName]
    return model["url"].replace("%D",modelDate).replace("%H",modelHour).replace("%T", fh)

def endModelProcessing (modelName):
    print ("This model is completely finished processing.")
    curr.execute ("UPDATE eolus3.models SET (status) = (%s) WHERE model = %s", ("WAITING", modelName))
    conn.commit ()

def addModelToDb (modelName):
    curr.execute ("INSERT INTO eolus3.models (model, status) VALUES (%s, %s)", (modelName, "WAITING"))
    conn.commit ()

def getLastAvailableTimestamp (model):
    now = datetime.utcnow()
    startOfDay = now - datetime.timedelta(
        hours=now.hour, 
        minutes=now.minute, 
        seconds=now.second, 
        microseconds=now.microsecond
    )
    yesterdayMidnight = startOfDay - timedelta(days=1)

    startOfDateChecker = yesterdayMidnight + timedelta(hours=model["updateOffset"])

    nowNotExceeded = True
    checkedTime = startOfDateChecker
    while nowNotExceeded:
        if checkedTime + timedelta(hours=(model["updateFrequency"])) > datetime.utcnow():
            break
        else:
            checkedTime = checkedTime + timedelta(hours=(model["updateFrequency"]))

    print ("Last available timestamp: %s", (checkedTime))

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

    print ("Processing " + modelName + " | " + formattedTimestamp)
    
    curr.execute ("UPDATE eolus3.models SET (status, timestamp) = (%s, %s) WHERE model = %s", ("PROCESSING", timestamp, modelName))
    conn.commit ()

    modelBandArray = makeModelBandArray (modelName)
    tableName = modelName + "_" + formattedTimestamp

    if len(modelBandArray) == 0:
        print ("Processing index-less model.")
        createBandTable (modelName, tableName)
    else:
        for band in modelBandArray:
            createBandTable (modelName, tableName + "_" + band.shorthand)


def getFullFh (modelName, fh):
    model = models[modelName]
    return str(fh).rjust (len(str(model["endTime"])), '0')


def createBandTable (modelName, tableName):
    model = models[modelName]
    curr.execute ("CREATE TABLE eolus3.%s (fh text, status text, band integer, start_time timestamp with time zone, end_time timestamp with time zone) WITH ( OIDS = FALSE )", (tableName))
    conn.commit ()

    fh = model["startTime"]
    i = 1

    populated = False

    while not populated:
        fullFh = getFullFh (modelName, fh)
        curr.execute ("INSERT INTO eolus3.%s (fh, status, band) VALUES (%s, %s, %s)", (tableName, fullFh, "WAITING", str(i)))
        conn.commit ()
        fh = addAppropriateFhStep (modelName, fh)
        i += 1

        if fh > model["endTime"]:
            return


def findModelStepToProcess(modelName, timestamp):
    found = False
    model = models[modelName]
    fh = model["startTime"]

    while not found:
        fullFh = getFullFh (modelName, fh)
        modelBandArray = makeModelBandArray (modelName)
        tableName = modelName + "_" + fullFh

        # If empty model band array, just check the only existing table
        if len(modelBandArray) == 0:
            status = getModelStepStatus (tableName, fullFh)
            if status == "WAITING":
                processModelStep (modelName, tableName, fullFh, None)
                found = True

        else:
            for band in modelBandArray:
                status = getModelStepStatus (tableName + "_" + band.shorthand, fullFh)
                if status == "WAITING":
                    processModelStep (modelName, tableName, fullFh, band)
                    found = True

        fh = addAppropriateFhStep (modelName, fh)

        if fh > model["endTime"]:
            found = True
            print ("Somehow, we couldn't find a step to start processing in any the model subtables.")


def getModelStepStatus (tableName, fullFh):
    curr.execute ("SELECT status FROM eolus3.%s WHERE fh = '%s'", (tableName, fullFh))
    return curr.fetchone()[0]


def processModelStep (modelName, tableName, fullFh, band):
    #delete the table if all steps are done

    #end processing entirely if no more tables
    #endModelProcessing
    sys.exit(1)
    

# This iterates a fh by the appropriate step size,
# given the fh. This is for models where the fh step size
# increases after a certain hour.
def addAppropriateFhStep (modelName, fh):
    model = models[modelName]

    for breakMin, stepSize in reversed(model["fhStep"].items()):
        if fh >= int(breakMin):
            return fh + stepSize

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


def main():

    # Figure out which model to process
    time = datetime.now(utc).replace(microsecond=0)
    processed = False

    # Check only brand new models, or models that are waiting first
    for modelName, model in models.items():
        print ("Checking " + modelName)
        timestamp = getLastAvailableTimestamp (model)

        # Flag this model as disabled in the DB
        if not model["enabled"]:
            curr.execute ("UPDATE eolus3.models SET (status) = (%s) WHERE model = %s", ("DISABLED", modelName))
            conn.commit ()
            continue

        status = getModelStatus (modelName)
        print ("Status: " + status)

        if status == None:
            addModelToDb (modelName)
            startProcessingModel (modelName, timestamp)
            findModelStepToProcess (modelName, timestamp)
            processed = True
            break

        elif status == "WAITING":
            if (modelHasUpdateAvailable (modelName, timestamp)):
                startProcessingModel (modelName, timestamp)
                findModelStepToProcess (modelName, timestamp)
                processed = True
                break

    if processed:
        print ("Model processing complete.")
        killScript (0)

    for modelName, model in models.items():
        if not model["enabled"]:
            continue

        status = getModelStatus (modelName)

        if status == "PROCESSING":
            findModelStepToProcess (modelName, timestamp)
            processed = True

    if not processed:
        print ("No models ready to process.")
        killScript (0)

    if processed:
        print ("Model processing complete.")
        killScript (0)

if __name__ == "__main__":
    main()