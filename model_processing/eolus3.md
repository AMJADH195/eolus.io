# eolus3 Model Processing Documentation

## Goal

Download grib2 files provided by NCEP and convert them to a library of TIF files:

 1. Per-band TIF files -- ex: nam3.date.hour.var.level.tif --> nam3.20191030.18z.temp.2m.tif
 2. (Maybe?) Master tif files with all bands

## Processing Flow

Look at models in config3.json:

 1. If disabled, ignore

 2. Check against pg: eolus3.models

 3. If status is WAITING...

    a. Check timestamp, if next timestamp is still in the future then continue to next model check

    b. If new timestamp should be processed, check for the existence of the first fh in that time series

    c. If that exists, set model status to PROCESSING, set timestamp to the new one, and create a new table:

        - MODEL_TIMESTAMP_VAR_LEVEL
        - Columns: fh (int), status (text), band(int), start (timestamp), end (timestamp)

    d. Create the tif file that will hold the bands, and create as many blank bands as will eventually exist

    e. Start processing the first fh

 4. If nothing is WAITING and needs an update, check the PROCESSING models...

    a. Get the timestamp, then look in config for the var/level pairs

    b. Look for a table matching MODEL_TIMESTAMP_VAR_LEVEL (if not using the index/random access, will not have a var_level table)

    c. Look for any fh in there marked as NEW and process it

    d. If done, see if all fh in that table is done and if so delete it

    e. If no more tables for that timestamp and model exist, mark the model as WAITING in eolus3.models

