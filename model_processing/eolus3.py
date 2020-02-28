import eolus_lib.pg_connection_manager as pg
from eolus_lib.config import config, levelMaps, models
import eolus_lib.http_manager as http_manager
from eolus_lib.logger import log, say_hello, print_line
import eolus_lib.model_tools as model_tools
import eolus_lib.processing as processing

from datetime import datetime, timedelta
import os
import concurrent.futures
import time
import pytz
from osgeo import gdal
import pprint

agent_logged = False
first_run = True
processing_pool = {}
pp = pprint.PrettyPrinter(indent=4)
utc = pytz.UTC

gdal.UseExceptions()


def kill_me(exit_code):
    if exit_code != 0:
        pg.reset()
        log("Exiting on failure.", "ERROR")

    if agent_logged:
        removed = pg.remove_agent()
        if not removed:
            log("Could not remove agent, trying again.", "ERROR", remote=True)
            try:
                pg.connect()
                pg.remove_agent()
            except:
                os._exit(exit_code)
    try:
        pg.close()
    except:
        log("Couldn't close connection.", "ERROR")
    os._exit(exit_code)


def work_done(future):
    global processing_pool
    log("Thread finished. " + str(future), "DEBUG")
    # pprint.pprint(processing_pool)


def init():
    global agent_logged, processing_pool

    say_hello()
    if not pg.connect():
        kill_me(1)

    log("✓ Connected.", "DEBUG")
    print()

    if not pg.can_do_work():
        log("Another agent is running already. Goodbye.", "NOTICE")
        kill_me(0)

    agent_logged = pg.add_agent()
    if not agent_logged:
        kill_me(1)

    max_threads = config["maxThreads"]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(do_work)
        }

        while futures:
            done, futures = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED)

            for fut in done:
                work_done(fut)

            if len(processing_pool) > 0:
                for i in range(0, max_threads - len(futures)):
                    time.sleep(config["sleepTime"])
                    executr = executor.submit(do_work)
                    futures.add(
                        executr
                    )
                    log("Adding another thread. " + str(executr), "DEBUG")

    log("No more processing to do. Goodbye.", "NOTICE")
    kill_me(0)


def do_work():
    global processing_pool, first_run

    # Check only brand new models, or models that are waiting first
    for model_name, model in models.items():

        # Flag this model as disabled in the DB
        if not model["enabled"]:
            pg.ConnectionPool.curr.execute(
                "UPDATE eolus3.models SET status = %s WHERE model = %s", ("DISABLED", model_name))
            pg.ConnectionPool.conn.commit()
            continue

        status = model_tools.get_model_status(model_name)
        model_fh = model_tools.get_full_fh(model_name, model["startTime"])
        log("Model: " + model_name, "INFO")

        max_lookback = 3
        lookback = 0
        if status == None:
            while lookback < max_lookback:
                timestamp = model_tools.get_last_available_timestamp(
                    model, prev=lookback)
                if model_tools.check_if_model_fh_available(model_name, timestamp, model_fh):
                    if model_name not in processing_pool:

                        log(f"Initializing new run for {model_name} | {timestamp}.",
                            "NOTICE", indentLevel=0, remote=True, model=model_name)
                        processing_pool[model_name] = {
                            'status': 'POPULATING'}
                        processing_pool[model_name] = model_tools.make_band_dict(
                            model_name)
                        model_tools.add_model_to_db(model_name)
                        processing.start(model_name, timestamp)
                        lookback = max_lookback

                    break

                lookback += 1

        elif status == "WAITING" or status == "DISABLED" or (status == "PROCESSING" and first_run):

            log("Status: " + status, "INFO")

            prev_timestamp = model_tools.get_model_timestamp(
                model_name).replace(tzinfo=utc)

            log("Prev timestamp: " + str(prev_timestamp), "INFO")

            max_lookback = 3
            lookback = 0
            while lookback < max_lookback:
                try:
                    timestamp = model_tools.get_last_available_timestamp(
                        model, prev=lookback)

                    if timestamp <= prev_timestamp and not (status == "PROCESSING" and first_run):
                        log("· No newer runs exist.", "INFO", indentLevel=1)
                        break

                    if not model_tools.model_timestamp_matches(model_name, timestamp) or (status == "PROCESSING" and first_run):
                        log("· Checking if an update is available for " + model_name + ". Looked back " + str(lookback) + " runs",
                            "INFO", indentLevel=1)
                        if model_tools.check_if_model_fh_available(model_name, timestamp, model_fh) or (status == "PROCESSING" and first_run):
                            if model_name not in processing_pool:

                                log(f"Initializing new run for {model_name} | {timestamp}.",
                                    "NOTICE", indentLevel=0, remote=True, model=model_name)
                                processing_pool[model_name] = {
                                    'status': 'POPULATING'}
                                processing_pool[model_name] = model_tools.make_band_dict(
                                    model_name)
                                processing.start(model_name, timestamp)
                                lookback = max_lookback

                            break

                    else:
                        log("· Nope.", "INFO", indentLevel=1)
                        break

                    lookback += 1

                except Exception as e:
                    log(repr(e), "ERROR")
                    break

        elif status == "PAUSED":
            try:
                pg.ConnectionPool.curr.execute(
                    "SELECT paused_at FROM eolus3.models WHERE model LIKE '" + model_name + "'")
                paused_at = pg.ConnectionPool.curr.fetchone()[0]

                log(model_name + " is PAUSED.", "NOTICE")

                if abs(datetime.now().replace(tzinfo=utc) - paused_at.replace(tzinfo=utc)) >= timedelta(minutes=config["pausedResumeMinutes"]):

                    log("Attempting to resume.", "INFO")
                    processing_pool[model_name] = {
                        'status': 'POPULATING'}
                    processing_pool[model_name] = model_tools.make_band_dict(
                        model_name)

                    last_fh = 0
                    pg.ConnectionPool.curr.execute(
                        "SELECT lastfh, timestamp FROM eolus3.models WHERE model = %s", (model_name,))
                    result = pg.ConnectionPool.curr.fetchone()
                    last_fh = int(result[0])
                    timestamp = result[1]

                    log("Restarting paused model from fh " + str(last_fh) +
                        " | timestamp: " + str(timestamp), "NOTICE")

                    for step in list(processing_pool[model_name]):
                        step_fh = processing_pool[model_name][step]['fh']
                        if int(step_fh) < last_fh:
                            del processing_pool[model_name][step]

                    processing.start(model_name, timestamp)

                else:
                    log("Not resuming yet until the threshold of " +
                        str(config["pausedResumeMinutes"]) + " minutes is met.", "NOTICE")

            except Exception as e:
                log("Error in pause resumption -- " + repr(e), "ERROR")

    first_run = False
    if len(processing_pool) > 0:
        processed = processing.process(processing_pool)
        return {
            'success': processed
        }

    print()

    return {
        'success': True
    }


if __name__ == "__main__":
    init()
