import eolus_lib.pg_connection_manager as pg
from eolus_lib.config import config, layerMaps, models
import eolus_lib.http_manager as http_manager
from eolus_lib.logger import log, say_hello, print_line
import eolus_lib.model_tools as model_tools

import sys
import os
from osgeo import ogr, gdal, osr, gdalconst

agent_logged = False
threads = 0

gdal.UseExceptions()


def kill_me(exit_code):
    if exit_code != 0:
        pg.reset()
        log("Exiting on failure.", "ERROR")

    if agent_logged:
        try:
            pg.remove_agent()
        except:
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


def init():
    say_hello()
    if not pg.connect():
        kill_me(1)

    log("✓ Connected.", "DEBUG")
    print_line()
    print()

    if not pg.can_do_work():
        log("Another agent is running already. Goodbye.", "DEBUG")
        kill_me(0)

    pg.add_agent()
    max_threads = config["maxThreads"]

    more_work_to_do = True
    while (more_work_to_do):
        if threads < max_threads:
            more_work_to_do = do_work()
        else:
            sleep (1000)

    log("No more processing to do. Goodbye.", "DEBUG")
    kill_me(0)


def do_work():
    global threads

    current_processing_pool = {}

    processing_models = []
    processed = False

    # Check only brand new models, or models that are waiting first
    for model_name, model in models.items():
        log("Checking " + model_name, "INFO", indentLevel=0)

        # Flag this model as disabled in the DB
        if not model["enabled"]:
            pg.ConnectionPool.curr.execute(
                "UPDATE eolus3.models SET status = %s WHERE model = %s", ("DISABLED", model_name))
            pg.ConnectionPool.conn.commit()
            log("× Disabled.", "DEBUG", indentLevel=1)
            print()
            continue

        status = model_tools.get_model_status(model_name)
        model_fh = model_tools.get_full_fh(model_name, model["startTime"])

        log("· Status: " + str(status), "INFO", indentLevel=1)

        # turn this into a loop you sociopath
        max_lookback = 2
        lookback = 0
        if status == None:
            while lookback < max_lookback:
                timestamp = model_tools.get_last_available_timestamp(
                    model, prev=lookback)
                if model_tools.check_if_model_fh_available(model_name, timestamp, model_fh):
                    model_tools.add_model_to_db(model_name)
                    if processing.start (model_name, current_processing_pool):
                        processed = processing.next_step(model_name, current_processing_pool)
                    
                    break

                lookback += 1

        elif status == "WAITING" or status == "DISABLED":
            should_process = False
            log("· Checking if this model needs to be processed.",
                "INFO", indentLevel=1)

            max_lookback = 2
            lookback = 0
            while lookback < max_lookback:
                timestamp = model_tools.get_last_available_timestamp(
                    model, prev=lookback)
                if not model_tools.model_timestamp_matches(model_name, timestamp):
                    log("· It does -- checking if an update is available. Looked back " + str(lookback) + " runs",
                        "INFO", indentLevel=1)
                    if model_tools.check_if_model_fh_available(model_name, timestamp, model_fh):
                        if processing.start(model_name, current_processing_pool):
                            processed = processing.next_step(
                                            model_name, current_processing_pool)
                        break
                else:
                    log("· Nope.", "INFO", indentLevel=1)
                    break

                lookback += 1

        elif status == "PROCESSING":
            processed = processing.next_step(
                model_name, current_processing_pool)
            
        

        print()

    return processed


if __name__ == "__main__":
    init()
