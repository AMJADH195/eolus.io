from eolus_lib.config import config, models, levelMaps
from eolus_lib.logger import log
import eolus_lib.file_tools as file_tools
import eolus_lib.pg_connection_manager as pg

from datetime import datetime, timedelta, tzinfo, time


def make_url(model_name, model_date, model_hour, fh):
    model = models[model_name]
    return model["url"].replace("%D", model_date).replace("%H", model_hour).replace("%T", fh)


def add_model_to_db(model_name):
    try:
        log("✓ Added model to models table.", "INFO",
            indentLevel=1, remote=True, model=model_name)
        pg.ConnectionPool.curr.execute(
            "INSERT INTO eolus3.models (model, status) VALUES (%s, %s)", (model_name, "WAITING"))
        pg.ConnectionPool.conn.commit()
        return True
    except:
        pg.reset()
        log("Couldn't add model to db.", "ERROR", remote=True, model=model_name)
        return False


def get_last_available_timestamp(model, prev=0):
    now = datetime.utcnow()
    start_of_day = now - timedelta(
        hours=now.hour,
        minutes=now.minute,
        seconds=now.second,
        microseconds=now.microsecond
    )
    yesterday_midnight = start_of_day - timedelta(days=1)

    start_of_day_checker = yesterday_midnight + \
        timedelta(hours=model["updateOffset"])

    max_time = now - timedelta(hours=prev*model["updateFrequency"])
    now_not_exceeded = True
    checked_time = start_of_day_checker
    while now_not_exceeded:
        if checked_time + timedelta(hours=(model["updateFrequency"])) > max_time:
            break
        else:
            checked_time = checked_time + \
                timedelta(hours=(model["updateFrequency"]))

    log(f"· Last available timestamp, {str(prev)} runs ago: {str(checked_time)}",
        "DEBUG", indentLevel=1)

    return checked_time


def get_number_of_hours(model_name):
    model = models[model_name]
    fh = model["startTime"]
    i = 0
    while True:
        fh = add_appropriate_fh_step(model_name, fh)
        i += 1

        if fh > model["endTime"]:
            return i


def get_model_status(model_name):
    try:
        pg.ConnectionPool.curr.execute(
            "SELECT status FROM eolus3.models WHERE model LIKE '" + model_name + "'")
        result = pg.ConnectionPool.curr.fetchone()

        return result[0]

    except:
        pg.reset()
        return None


def get_full_fh(model_name, fh):
    model = models[model_name]
    return str(fh).rjust(len(str(model["endTime"])), '0')


def get_level_name_for_level(level_shorthand, name_type):
    return levelMaps[level_shorthand][name_type]


def check_if_model_fh_available(model_name, timestamp, fh):
    url = make_url(model_name, timestamp.strftime(
        "%Y%m%d"), timestamp.strftime("%H"), fh)
    log("· Checking URL: " + url, "DEBUG",
        remote=True, indentLevel=1, model=model_name)

    try:
        ret = requests.head(url, timeout=(30, 120))

        if ret.status_code == 200 or ret.status_code == None:
            log("✓ Found.", "DEBUG", remote=True,
                indentLevel=1, model=model_name)
            return True
        else:
            log("× Not found.", "DEBUG", remote=True,
                indentLevel=1, model=model_name)

    except:
        log("× Not found.", "DEBUG", remote=True,
            indentLevel=1, model=model_name)

    return False


def model_timestamp_matches(model_name, timestamp):
    try:
        pg.ConnectionPool.curr.execute(
            "SELECT timestamp FROM eolus3.models WHERE model = %s", (model_name,))
        model_time = str(curr.fetchone()[0])[0:16]
        t_time = str(timestamp)[0:16]
        return model_time == t_time
    except:
        pg.reset()
        return False


def update_run_status(model_name):
    try:
        pg.ConnectionPool.curr.execute(
            "UPDATE eolus3.run_status SET status = 'COMPLETE' WHERE model = '" + model_name + "'")
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log(f"!!! Could not update run_status!", "ERROR",
            indentLevel=0, remote=True, model=model_name)


def get_base_filename(model_name, timestamp, band):
    date = timestamp.strftime("%Y%m%d")
    time = timestamp.strftime("%HZ")
    file = model_name + "_" + date + "_" + time
    if band is not None:
        return file + "_" + band["shorthand"]
    else:
        return file


def get_model_step_status(tableName, fullFh):
    try:
        pg.ConnectionPool.curr.execute("SELECT status FROM eolus3." +
                                       tableName + " WHERE fh = %s", (fullFh,))
        return pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("Couldn't get status for fh " + fullFh +
            " in table " + tableName, "ERROR", remote=True)


# This iterates a fh by the appropriate step size,
# given the fh. This is for models where the fh step size
# increases after a certain hour.
def add_appropriate_fh_step(model_name, fh):
    model = models[model_name]

    for key in reversed(sorted(model["fhStep"].keys())):

        if fh >= int(key):
            return fh + model["fhStep"][key]

    log("× Couldn't match the appropriate step size.",
        "WARN", indentLevel=1, remote=True, model=model_name)
    return fh
