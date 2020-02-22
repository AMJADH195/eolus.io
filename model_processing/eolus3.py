import eolus_lib.pg_connection_manager as pg
from eolus_lib.config import config, levelMaps, models
import eolus_lib.http_manager as http_manager
from eolus_lib.logger import log, say_hello, print_line
import eolus_lib.model_tools as model_tools
import eolus_lib.processing as processing

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
    print_line()
    print()

    if not pg.can_do_work():
        log("Another agent is running already. Goodbye.", "DEBUG")
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

    log("No more processing to do. Goodbye.", "DEBUG")
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

                    if timestamp <= prev_timestamp:
                        log("· No newer runs exist.", "INFO", indentLevel=1)
                        break

                    if not model_tools.model_timestamp_matches(model_name, timestamp):
                        log("· Checking if an update is available for " + model_name + ". Looked back " + str(lookback) + " runs",
                            "INFO", indentLevel=1)
                        if model_tools.check_if_model_fh_available(model_name, timestamp, model_fh):
                            if model_name not in processing_pool:
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
