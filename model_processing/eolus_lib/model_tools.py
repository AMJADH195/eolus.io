from eolus_lib.config import config, models, levelMaps
from eolus_lib.logger import log
import eolus_lib.file_tools as file_tools
import eolus_lib.pg_connection_manager as pg

from datetime import datetime, timedelta, tzinfo, time


def make_url(modelName, modelDate, modelHour, fh):
    model = models[modelName]
    return model["url"].replace("%D", modelDate).replace("%H", modelHour).replace("%T", fh)


def end_processing(modelName):

    file_tools.clean()

    try:
        log("✓ This model is completely finished processing.",
            "INFO", remote=True, model=modelName)
        pg.ConnectionPool.curr.execute(
            "UPDATE eolus3.models SET status = %s WHERE model = %s", ("WAITING", modelName))
        pg.ConnectionPool.conn.commit()
        update_run_status(modelName)
    except:
        pg.reset()
        log("Couldn't mark model as complete.",
            "ERROR", remote=True, model=modelName)


def add_model_to_db(modelName):
    try:
        log("✓ Added model to models table.", "INFO",
            indentLevel=1, remote=True, model=modelName)
        pg.ConnectionPool.curr.execute(
            "INSERT INTO eolus3.models (model, status) VALUES (%s, %s)", (modelName, "WAITING"))
        pg.ConnectionPool.conn.commit()
        return True
    except:
        pg.reset()
        log("Couldn't add model to db.", "ERROR", remote=True, model=modelName)
        return False


def get_last_available_timestamp(model, prev=0):
    now = datetime.utcnow()
    startOfDay = now - timedelta(
        hours=now.hour,
        minutes=now.minute,
        seconds=now.second,
        microseconds=now.microsecond
    )
    yesterdayMidnight = startOfDay - timedelta(days=1)

    startOfDateChecker = yesterdayMidnight + \
        timedelta(hours=model["updateOffset"])

    maxTime = now - timedelta(hours=prev*model["updateFrequency"])
    nowNotExceeded = True
    checkedTime = startOfDateChecker
    while nowNotExceeded:
        if checkedTime + timedelta(hours=(model["updateFrequency"])) > maxTime:
            break
        else:
            checkedTime = checkedTime + \
                timedelta(hours=(model["updateFrequency"]))

    log(f"· Last available timestamp, {str(prev)} runs ago: {str(checkedTime)}",
        "DEBUG", indentLevel=1)

    return checkedTime


def getNumberOfHours(modelName):
    model = models[modelName]
    fh = model["startTime"]
    i = 0
    while True:
        fh = addAppropriateFhStep(modelName, fh)
        i += 1

        if fh > model["endTime"]:
            return i


def getModelStatus(modelName):
    try:
        curr.execute(
            "SELECT status FROM eolus3.models WHERE model LIKE '" + modelName + "'")
        result = curr.fetchone()

        return result[0]

    except:
        resetPgConnection()
        return None


def getFullFh(modelName, fh):
    model = models[modelName]
    return str(fh).rjust(len(str(model["endTime"])), '0')


def getLevelNameForLevel(levelShorthand, nameType):
    return levelMaps[levelShorthand][nameType]


def checkIfModelFhAvailable(modelName, timestamp, fh):
    model = models[modelName]
    url = makeUrl(modelName, timestamp.strftime(
        "%Y%m%d"), timestamp.strftime("%H"), fh)
    log("· Checking URL: " + url, "DEBUG",
        remote=True, indentLevel=1, model=modelName)

    try:
        ret = requests.head(url, timeout=(30, 120))

        if ret.status_code == 200 or ret.status_code == None:
            log("✓ Found.", "DEBUG", remote=True,
                indentLevel=1, model=modelName)
            return True
        else:
            log("× Not found.", "DEBUG", remote=True,
                indentLevel=1, model=modelName)

    except:
        log("× Not found.", "DEBUG", remote=True, indentLevel=1, model=modelName)

    return False


def modelTimestampMatches(modelName, timestamp):
    try:
        curr.execute(
            "SELECT timestamp FROM eolus3.models WHERE model = %s", (modelName,))
        modelTime = str(curr.fetchone()[0])[0:16]
        tTime = str(timestamp)[0:16]
        return modelTime == tTime
    except:
        resetPgConnection()
        return False


def updateRunStatus(modelName):
    try:
        curr.execute(
            "UPDATE eolus3.run_status SET status = 'COMPLETE' WHERE model = '" + modelName + "'")
        conn.commit()
    except:
        resetPgConnection()
        log(f"!!! Could not update run_status!", "ERROR",
            indentLevel=0, remote=True, model=modelName)


def getBaseFileName(modelName, timestamp, band):
    date = timestamp.strftime("%Y%m%d")
    time = timestamp.strftime("%HZ")
    file = modelName + "_" + date + "_" + time
    if band is not None:
        return file + "_" + band["shorthand"]
    else:
        return file


def getModelStepStatus(tableName, fullFh):
    try:
        curr.execute("SELECT status FROM eolus3." +
                     tableName + " WHERE fh = %s", (fullFh,))
        return curr.fetchone()[0]
    except:
        resetPgConnection()
        log("Couldn't get status for fh " + fullFh +
            " in table " + tableName, "ERROR", remote=True)


# This iterates a fh by the appropriate step size,
# given the fh. This is for models where the fh step size
# increases after a certain hour.
def addAppropriateFhStep(modelName, fh):
    model = models[modelName]

    for key in reversed(sorted(model["fhStep"].keys())):

        if fh >= int(key):
            return fh + model["fhStep"][key]

    log("× Couldn't match the appropriate step size.",
        "WARN", indentLevel=1, remote=True, model=modelName)
    return fh
