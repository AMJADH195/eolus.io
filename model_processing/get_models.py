import argparse
import calendar
import json
import os
import os.path
import pprint
import subprocess
import sys
import time
import urllib2
from datetime import datetime, timedelta, tzinfo
from shutil import copy

import psycopg2
import requests
from dateutil.parser import parse

model_time = 0      # The time applicable to the model run that will be processed
model_name = ""     # The name of the model that will be processed
last_checked_total_seconds = 0
fatal_error = False
already_failed = False
verbose = False
ignoredb = False
forcemodel = None
conn = None
curr = None
fetch = None

ZERO = timedelta(0)

class UTC(tzinfo):
    def utcoffset(self, dt):
        return ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return ZERO

utc = UTC()

class GdalErrorHandler(object):
    def __init__(self):
        self.err_level=gdal.CE_None
        self.err_no=0
        self.err_msg=''

    def handler(self, err_level, err_no, err_msg):
        self.err_level=err_level
        self.err_no=err_no
        self.err_msg=err_msg

def kill_script (exit_code):
    global curr, conn
    if not ignoredb:
        curr.close ()
        conn.close ()
    sys.exit (exit_code)

def sql_connect():
    print "Connecting to db..."
    return psycopg2.connect (
        host=config["postgres"]["host"],
        port=5432,
        dbname=config["postgres"]["db"],
        user=config["postgres"]["user"],
        sslmode="require")

def log (message, level, model=""):
    global curr, conn
    time = datetime.now(utc)
    print_time = time.strftime ("%Y-%m-%d %H:%M:%S")
    print_str = "[" + level + "] | " + print_time + " | " + model + " | " + message
    print print_str

    if not ignoredb:
        curr.execute ("INSERT INTO logging.processing_logs (timestamp, model, level, message) VALUES (%s, %s, %s, %s)", (str(time), model, level, message ))
        conn.commit ()

        if model:
            curr.execute ("UPDATE logging.model_status SET (log) = (%s) WHERE model = %s", (print_str, model_name))
            conn.commit ()

def check_if_model_needs_update (model_name):
    global curr, models, model_time, last_checked_total_seconds, already_failed
    # First, for each model, check the latest model run that efrom threading import Timern NCEP
    # against the last model run that was retrieved.

    # model run format on NCEP is YYYYMMDDHH
    now = datetime.utcnow().replace(microsecond=0,second=0,minute=0)

    model_timestamp = datetime.fromtimestamp (0)

    fetch = None

    if not ignoredb:
        curr.execute ("SELECT model_timestamp, status FROM logging.model_status WHERE model LIKE '" + model_name + "'")
        fetch = curr.fetchone()
    if fetch:
        model_db_timestamp = fetch[0]
        if model_db_timestamp and fetch[1] != "FAILED":
            model_timestamp = parse(str(model_db_timestamp))
        if fetch[1] == "FAILED":
            already_failed = True
    else:
        model_timestamp = parse('1999-01-01')

    print "Last checked: " + model_timestamp.strftime ("%Y %m %d %HZ")

    model_time = now
    model_time_total_seconds = 0
    model = models[model_name]

    # A list of the possible model run hours, e.g. 0, 6, 12, 18
    # This is so that we only check for the existence of models
    # that would exist in the first place -- instead of checking
    # model run times that are never performed for a model
    model_run_possibilities = []
    i = model["updateOffset"]
    model_run_possibilities.append (model["updateOffset"])
    while i < 24:
        i += model["updateFrequency"]
        if i != 24: 
            model_run_possibilities.append (i)

    last_checked_total_seconds = time.mktime(model_timestamp.timetuple())

    # Look up to 24 hours back in time
    for hour_subtract in range (0, 25):
        model_time = now-timedelta(hours=hour_subtract)
        model_time_total_seconds = time.mktime(model_time.timetuple())

        if model_time_total_seconds <= last_checked_total_seconds:
            print "No new model run has been found."
            break

        model_date = model_time.strftime ("%Y%m%d")
        model_hour = model_time.strftime ("%H")

        # If this hour does not correspond with the hours
        # that the model is run at, skip it
        if int(model_hour) not in model_run_possibilities:
            continue

        print "Checking run for this datetime: " + model_date + " " + model_hour + "Z"
        
        if model["downloadType"] == "GRIBFILTER":
            grib_filename = model["gribFilename"].replace("%D",model_date).replace("%H",model_hour).replace("%T",str(model["endTime"]))
            full_directory = model["baseDirectory"] + model["gribDirectory"].replace("%D", model_date).replace("%H", model_hour)
            url = config["downloadTypes"]["GRIBFILTER"]["connectionProtocol"] + config["downloadTypes"]["GRIBFILTER"]["nomadsBaseUrl"] + full_directory + "/" + grib_filename
        elif model["downloadType"] == "FILESERIES":
            url = model["url"].replace("%D",model_date).replace("%H",model_hour).replace("%T",str(model["endTime"]))
        
        print "Checking URL: " + url

        try:
            ret = urllib2.urlopen(url)

            if ret.code == 200 or ret.code == None:
                print " *** New model run found. ***"
                return True

        except:
            print "Not found."

        # Wait a bit between polling server,
        # per NCEP's usage guidelines.
        time.sleep (config["sleepTime"])

def find_next_model_to_process ():
    time = datetime.now(utc).replace(microsecond=0)
    global models, config, conn, curr
    for model_name, model in models.items():
        if not model["enabled"]:
            curr.execute ("UPDATE logging.model_status SET (status, end_time, progress) = (%s, %s, %s) WHERE model = %s", ("DISABLED", None, 0, model_name)) 
            conn.commit ()
            continue

        print ""
        print "---------------"
        print "Checking " + model_name + "..."

        if not ignoredb:
            curr.execute ("SELECT * FROM logging.model_status WHERE model LIKE '" + model_name + "'")
            result = curr.fetchone()

        should_update = False

        if result == None:
            should_update = check_if_model_needs_update (model_name)
        elif result[1]  != "PROCESSING":
            if check_if_model_needs_update (model_name):
                should_update = True
            else:
                print "This model is " + result[1] + ", but no new update was found."
        else:
            print "This model is currently " + result[1] + ", skipping."
        
        if should_update:
            if not ignoredb:
                curr.execute ("INSERT INTO logging.model_status (model, status, model_timestamp, warnings, errors, log, start_time, end_time, progress) VALUES (%s, %s, null, 0, 0, null, %s, null, 0) ON CONFLICT (model) DO UPDATE SET (status, model_timestamp, warnings, errors, log, start_time, end_time, progress) = (EXCLUDED.status, EXCLUDED.model_timestamp, EXCLUDED.warnings, EXCLUDED.errors, EXCLUDED.log, EXCLUDED.start_time, EXCLUDED.end_time, EXCLUDED.progress)", (model_name, "PROCESSING", time)) 
                conn.commit ()
            return model_name
        
    return None

def set_model_to_waiting (model_name):
    global curr, conn, fatal_error
    time = datetime.now(utc)
    status = "WAITING"
    if fatal_error:
        status = "FAILED"
    if fatal_error and already_failed:
        status = "FAILED PERMANENTLY"
    if not ignoredb:
        curr.execute ("UPDATE logging.model_status SET (status, end_time, progress) = (%s, %s, %s) WHERE model = %s", (status, time, 100, model_name)) 
        conn.commit ()

def make_grib_filter_url (model_date, model_hour, fmt_timestep):
    global model, config
    grib_filter_filename = model["gribFilename"].replace("%D",model_date).replace("%H",model_hour).replace("%T",fmt_timestep)
    grib_directory = model["gribDirectory"].replace("%D",model_date).replace("%H",model_hour).replace("%T",fmt_timestep)

    extra_params = ""

    if "variables" in model:
        for variable in model["variables"]:
            extra_params += "&var_" + variable + "=on"
    else:
        extra_params += "&all_var=on"
        
    if "levels" in model:
        for level in model["levels"]:
            levelName = level.replace (" ", "_")
            extra_params += "&lev_" + levelName + "=on"
    else:
        extra_params += "&all_lev=on"

    # download every grib file from NOMADS grib filter
    return (config["downloadTypes"]["GRIBFILTER"]["connectionProtocol"] + 
        config["downloadTypes"]["GRIBFILTER"]["gribFilterBaseUrl"] + 
        model["gribFilterName"] +
        config["downloadTypes"]["GRIBFILTER"]["gribFilterExtension"] + 
        "file=" + grib_filter_filename +
        config["downloadTypes"]["GRIBFILTER"]["gribFilterParams"] + 
        extra_params +
        "&leftlon=" + config["bounds"]["left"] +
        "&rightlon=" + config["bounds"]["right"] +
        "&toplat=" + config["bounds"]["top"] +
        "&bottomlat=" + config["bounds"]["bottom"] +
        "&dir=" + grib_directory
    )

def make_file_url (model_date, model_hour, fmt_timestep):
    global model
    url = model["url"].replace("%D",model_date).replace("%H",model_hour).replace("%T",fmt_timestep)
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

'''

    -------- MAIN ---------


'''
try:
    from osgeo import gdal, osr
except:
    print "Error: GDAL API is not installed for python."
    sys.exit (1)

directory = os.path.dirname(os.path.realpath(__file__)) + "/"

# GDAL error handling stuff
err=GdalErrorHandler()
handler=err.handler
gdal.PushErrorHandler(handler)
gdal.UseExceptions()

try:
    with open (directory + '/config.json') as f:
        data = json.load(f)
except:
    print "Error: Config file does not exist."
    sys.exit (1)

config = data["config"]
models = data["models"]

parser = argparse.ArgumentParser ()
parser.add_argument ('--ignoredb', action='store_true')
parser.add_argument ('--verbose', action='store_true')
parser.add_argument ('--forcemodel', type=str)
parser.add_argument ('--maxtime', type=int)
args = parser.parse_args ()

if args.maxtime:
    print "Max FH set to " + str (args.maxtime)
    config["maxTime"] = args.maxtime

if args.verbose:
    print "Verbose enabled"
    verbose = True

if args.ignoredb:
    print "Ignore DB enabled"
    ignoredb = True

if args.forcemodel:
    forcemodel = args.forcemodel
    print "Will only process model " + forcemodel

try:
    if not ignoredb:
        conn = sql_connect ()
except psycopg2.Error as e:
    print "Could not connect to database."
    print e
    print e.pgerror
    sys.exit (1)

print "Connected successfully."

if not ignoredb:
    curr = conn.cursor()

if not forcemodel:
    model_name = find_next_model_to_process ()
else:
    model_name = forcemodel
    check_if_model_needs_update(model_name)

if model_name == None:
    print "No updates needed.  Exiting."
    kill_script (0)

print ""
print "==============="

model = models[model_name]
model_hour = model_time.strftime ("%H")
model_date = model_time.strftime ("%Y-%m-%d")

log ("Model processing start: {0} {1}Z".format (model_date, model_hour), "INFO", model_name)
if not ignoredb:
    curr.execute ("UPDATE logging.model_status SET (model_timestamp) = (%s) WHERE model = %s", (model_time, model_name))
    conn.commit ()
    curr.execute ("DELETE FROM logging.run_status WHERE model = %s AND model_timestamp = %s",(model_name, model_time))
    conn.commit ()
    curr.execute ('INSERT INTO logging.run_status (model, result, model_timestamp, fh_complete, time_start) VALUES (%s, %s, %s, 0, %s)', (model_name, "IN PROGRESS", model_time, str(datetime.now(utc))))
    conn.commit ()

working_dir = directory + "/" + config["tempDir"] + model_name + "/"
if not os.path.exists(working_dir):
    os.makedirs(working_dir)

num_warnings = 0
num_errors = 0

# maxTime can be used for debugging purposes to only grab a few model runs per model
model_loop_end_time = model["endTime"] + 1
if config["maxTime"] > 0:
    model_loop_end_time = config["maxTime"] + 1

table_name = model_name + '_' + str(int(calendar.timegm(model_time.utctimetuple())))

for model_timestep in range (model["startTime"], model_loop_end_time):
    fmt_timestep = str(model_timestep).rjust (len(str(model["endTime"])), '0')
    url = ""
    # for gdalwarp -te extent clip parameter
    extent = ""

    if model["downloadType"] == "GRIBFILTER":
        url = make_grib_filter_url (model_date.replace("-", ""), model_hour, fmt_timestep)
    elif model["downloadType"] == "FILESERIES":
        url = make_file_url (model_date.replace("-", ""), model_hour, fmt_timestep)
        # for gdalwarp -te extent clip parameter
        extent = "-te " + " ".join (normalize_extents())
    
    print "---------------"
    log ("Downloading grib file for timestep {0}/{1}.".format (fmt_timestep, str(model_loop_end_time - 1)), "INFO", model_name)

    try:
        grib_file = requests.get(url, timeout=60)
        if grib_file.status_code != 200:
            log ("Grib retrieval for timestamp {0} failed with code {1}".format (str(fmt_timestep), grib_file.status_code), "INFO", model_name)
            raise Exception ("This file does not exist on the remote server.")

    except Exception as e:
        log ("Could not download grib file ({0}).  Skipping...".format (e), "WARN", model_name)
        num_warnings += 1
        print "---------------"
        print ""
        # Wait a bit between polling server,
        # per NCEP's usage guidelines.
        time.sleep (config["sleepTime"])
        continue

    filename = ""
    
    try:
        filename = working_dir + model_name + "_" + model_date + "_" + model_hour + "Z_f" + fmt_timestep

        with open (filename + "." + model["filetype"], 'wb') as outfile:
            outfile.write (grib_file.content)

    except:
        log ("Could not write grib file ({0}).".format (filename), "ERROR", model_name)
        num_errors += 1
        print "---------------"
        print ""
        # Wait a bit between polling server,
        # per NCEP's usage guidelines.
        time.sleep (config["sleepTime"])
        continue

    log ("The grib file was downloaded successfully.", "INFO", model_name)

    warp_file_type = model["filetype"]

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
        warp_file_type = "tif"

        try:

            # Open the grib file and read the bands and SRS
            grib_file = gdal.Open (filename + "." + model["filetype"])
            grib_srs = osr.SpatialReference()
            grib_srs.ImportFromWkt (grib_file.GetProjection())
            geo_transform = grib_file.GetGeoTransform()
            width = grib_file.RasterXSize
            height = grib_file.RasterYSize
            num_src_bands = grib_file.RasterCount

            print " ---> Creating new raster in memory."
            # Create an in-memory raster that we will write the desired bands to as we find them
            new_raster = gdal.GetDriverByName('MEM').Create('', width, height, 0, gdal.GDT_Float64)
            print " ---> Created, setting transform "
            new_raster.SetGeoTransform (list(geo_transform))
            print " ---> Done, start processing each band"

            # For each band in the list, search through the bands of the raster for the match
            # if not found, print a warning and write an empty band
            for extract_band in model["extractBandsByMetadata"]:
                extract_band_element = extract_band["gribVar"]
                extract_band_name = extract_band["gribLevel"]
                matched = False

                print " ---> Extracting band " + extract_band_element
                for i in range (1, num_src_bands):
                    band = None
                    band_metadata = None
                    try:
                        band = grib_file.GetRasterBand(i)
                        band_metadata = band.GetMetadata()
                    except:
                        print " ---> Couldn't read band :( "
                        continue
                    if (band_metadata["GRIB_ELEMENT"] == extract_band_element and
                        band_metadata["GRIB_SHORT_NAME"] == extract_band_name):

                        # WE COULD JUST DO A BREAK HERE BUT -- this warning might be useful
                        # so we're going to iterate the whole thing, even if a match is found
                        # just to alert the user that they might not be getting the expected band
                        if matched:
                            num_warnings += 1
                            print " !!! WARNING : The same variable (" + extract_band_element + " @ " + extract_band_name + ") has already been found in the GRIB bands.  They probably have different GRIB_FORECAST_SECONDS values."
                        else:
                            matched = True
                            band_data = None
                            data_type = None
                            try: 
                                print " ---> Reading band data "
                                band_data = band.ReadAsArray()
                                data_type = band.DataType
                            except:
                                print " ---> Issue with the band, creating blank instead"
                                new_raster.AddBand(gdal.GDT_Float64)
                            
                            if band_data is not None:
                                new_band = new_raster.GetRasterBand (new_raster.RasterCount)
                                new_raster.AddBand(data_type)
                                new_band = new_raster.GetRasterBand (new_raster.RasterCount)
                                new_band.WriteArray (band_data)
                                new_band.FlushCache()
                if not matched:
                    num_warnings += 1
                    print " !!! WARNING: This run is missing a desired band: " + extract_band_element + " @ " + extract_band_name
                    # Add an empty band to not upset the sacred order of raster bands
                    # Careful with the type!  Tif driver gets angry if the types are different across bands
                    new_raster.AddBand(gdal.GDT_Float64)

            new_raster.SetProjection (grib_srs.ExportToWkt())
            out_raster = gdal.GetDriverByName('GTiff').CreateCopy (filename + "_temp.tif", new_raster, 0)

            log ("New raster created.", "INFO", model_name)

            # This is important, or else gdalwarp
            # can't read the raster and you get an empty raster in the end
            del new_raster
            del out_raster
            
        except:
            log ("Could not create new geotiff raster.", "ERROR", model_name)
            fatal_error = True
            num_errors += 1
            print "---------------"

    # This could be replaced with gdal library commands but
    # I'm lazy and the documentation is much nicer for the shell commands
    # than it is for the API :)
    
    log ("Beginning gdalwarp.", "INFO", model_name)

    try:
        if "extractBandsByMetadata" not in model:
            filenames = filename + "." + warp_file_type + " " + filename + ".tif"
        else:
            filenames = filename + "_temp.tif " + filename + ".tif"

        widthStr = ""
        if model["imageWidth"]:
            print "Setting image width from config."
            widthStr = " -ts " + str(model["imageWidth"])

        quietStr = " -q"
        if verbose:
            quietStr = ""

        warp = 'gdalwarp ' + filenames + quietStr + ' -t_srs EPSG:4326 ' + extent + ' -multi --config CENTER_LONG 0 -r ' + config["resampling"] + widthStr + ' -overwrite -co "TILED=YES" -co "COMPRESS=LZW"'
        if verbose:
            print warp
        os.system (warp)
    
    except:
        log ("Could not translate the new raster.", "ERROR", model_name)
        fatal_error = True
        num_errors += 1
        print "---------------"
        print ""
        continue

    log ("Copy file over to mapfile directory.", "INFO", model_name)

    try:
        directory = config["mapfileDir"] + "/" + model_name + "/"
        if not os.path.exists(directory):
            os.makedirs(directory)

        infile = filename + ".tif"
        outfile = directory + model_name + "_" + str(model_date) + "_" + str(model_hour) + "z_t" + str(model_timestep) + ".tif"

        log ("Infile: " + infile, "INFO", model_name)
        log ("Outfile: " + outfile, "INFO", model_name)

        copy (infile, outfile)

    except:
        log ("Could not copy the new raster.", "ERROR", model_name)
        fatal_error = True
        num_errors += 1
        print "---------------"
        print ""
        continue
    
    log ("Cleaning up temporary files.", "INFO", model_name)
    
    if not config["debug"]:
        for a_file in os.listdir(working_dir):
            file_path = os.path.join(working_dir, a_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(e)
    else:
        print "Skipped (DEBUG)"

    try:
        if not ignoredb:
            curr.execute ("UPDATE logging.model_status SET (progress) = (%s) WHERE model = %s", (str((float(model_timestep)/float(model_loop_end_time - 1))*100), model_name))
            conn.commit ()
            curr.execute ('UPDATE logging.run_status SET (fh_complete) = (%s) WHERE model = %s AND model_timestamp = %s', (model_timestep, model_name, model_time))
            conn.commit ()
    except:
        log ("Could not update model status.", "WARN", model_name)
        num_warnings += 1

    log ("Run {0} completed, moving to next timestamp.".format(fmt_timestep),"INFO", model_name)
    print "---------------"
    print ""
    time.sleep (config["sleepTime"])

print "============================="
print ""
finish_time = datetime.utcnow().strftime ("%Y-%m-%d %H:%M:%S+00")

if not ignoredb:
    curr.execute ("UPDATE logging.model_status SET (end_time, warnings, errors) = (%s, %s, %s) WHERE model = %s", (str(finish_time), num_warnings, num_errors, model_name))
    conn.commit ()

status = "COMPLETE"
if fatal_error:
    status = "FAILED"
if fatal_error and already_failed:
    status = "PERMANENTLY FAILED"

if not ignoredb:
    curr.execute ('UPDATE logging.run_status SET (time_end, result) = (%s, %s) WHERE model = %s AND model_timestamp = %s', (str(finish_time), status, model_name, model_time))
    conn.commit ()

set_model_to_waiting (model_name)
log ("Model processing completed successfully.".format(fmt_timestep),"INFO", model_name)


if not ignoredb:
    log ("Cleaning up the logs...", "INFO")
    curr.execute ("DELETE FROM logging.processing_logs WHERE timestamp < now() - interval '" + str(config["retentionDays"]) + " days'")
    conn.commit ()
    curr.execute ("DELETE FROM logging.run_status WHERE model_timestamp < now() - interval '" + str(config["retentionDays"]) + " days'")
    conn.commit ()

os.system ('find /map/*/* -mtime +' + str(config["retentionDays"]) + ' -exec rm {} \;')
kill_script (0)
