# Model Processing Overview
 1. Run through the config and see which models are active.
 2. Cross-reference that model, and its run times, with the status on Postgres.
 3. If the model is not currently processing, and the last processed timestamp is older than the latest available model, begin the process.

### Download type: GRIBFILTER
 1. GRIBFILTER models are retrieved from the NOMADS GRIB filter, which allows the grib to be clipped and only specific bands extracted as opposed to downloading the entire weather model. There are pros and cons to this, with the pros already being mentioned. The cons is that their filter can sometimes be slow or down, and that it is a little buggy at times (some bands are not retrievable). This approach is generally used for models that are prohibitively difficult to process such as the NAM-NEST.
 2. The script determines which calls to make from the GRIB filter based on the config.
 3. The model timestamp and FH are passed to the filter in the filename of the grib2 to retrieve.

### Download type: FILESERIES
 1. FILESERIES models are downloaded straight from the NOMADS repository. The entire model run is downloaded.
 2. The url of the model that is downloaded, per timestep, follows the same syntax as the GRIBFILTER.

### Timestamp / Filename Variables
Using these variables in the url definition, the model processing script can retrieve all the necessary files for an entire model run.

 * `%D` - The date of the model run (e.g. 20190821)
 * `%H` - The hour of the model run (e.g. 12)
 * `%T` - The forecast hour (e.g. 34)

These are all you need as NCEP uses a very consistent naming scheme.

## Why are only certain bands of the models retrieved?

Most of the models don't just have "useful" outputs such as surface temperature. Model outputs generally contain all the data used by the model in its calculations, e.g. the state of the atmosphere at a dozen different layers. Most of this is not very useful for general forecasting work, and the model size can be greatly reduced by omitting this data.

### GRIB Filter
The GRIB filter, as mentioned above, can be used to only retrieve certain bands (variables and levels) for a model. However, this function is not available or somewhat broken for some models.

### Extract Bands By Metadata
After a model file is downloaded, if `extractBandsByMetadata` is set, the processing script will create a new blank GeoTIFF and copy over bands from the model file one-by-one, provided their variable name and level match any of the entries in the array.

This is used to further slim down final model outputs to only the desired variables.

The `gribVar` pertains to the `GRIB_ELEMENT` as reported by GDAL. the `gribLevel` pertains to `GRIB_SHORT_NAME`. Yes, GDAL reporting on GRIB metadata leaves something to be desired.

# Python Libs Required

 * psycopg2
 * python-dateutil
 * requests
 * osgeo (gdal, osr) (`pip install GDAL`)

# Configuration
By default the configuration is close to what is used in production on eolus.io. Of note, the geopgraphic extent is set to roughly contain the state of Colorado. It also connects to the eolus.io database by default (or it would, if you knew the password).

These values need to be changed to be applicable to your database and geographical area.

## config

### postgres
The host, db, and user settings are used to connect to postgres. You will need a `.pgpass` file or environment variable to pass the correct password to the script.

### bounds
The lat/lon of the processing extent. This is a little strange as you'll notice values less than 0 are actually higher than 180. I believe this was done due to some issues with the GRIB filter (this is used for both the GRIB filter and for the `gdalwarp` processing extent). It might work with normal lat/lon coordinates now.

### tempDir
The location on the filesystem where temporary files will be kept, such as download grib files.

### mapfileDir
This is where the final model output is stored. `mapfileDir/<model name>/<model name>_<model timestamp>_<forecast hour>.tif`

### logFile
This is the name of the file that logs will be written to. The script also logs to the db.

### debug
Setting this to `true` causes the script to not write to db, for development purposes.

### resampling
The resample type when using `gdalwarp`.

### sleepTime
The seconds to sleep between polling for model timestamps. NCEP requests that this is done to prevent strain on their servers.

### maxTime
Hard cutoff for forecast hour, so that the entire model run isn't processed (for dev purposes).

### Retention Days
Number of days to keep models and runs on the filesystem / in the db before deleting them.

### downloadTypes
This right now just contains some common url prefixes for GRIBFILTER download types.

## models
This is the bread and butter of the script. Each entry in this section of the config defines a model that will be processed by the script. The key is the model name.

### enabled
Whether the model will be processed or not. Disabled models will update the db to mention that they are disabled.

### updateFrequency
How often (in hours) a new model run is available.

### updateOffset
The offset from 00Z the model runs are available. This is usually zero, but some models (like the SREF) run at 03Z, 09Z, 15Z, etc.

### startTime
The starting forecast hour. Usually 0, but some models start at 1.

### endTime
The ending forecast hour. Note, the number of digits of this number influence the actual value of each forecast hour. If the endtime is 192, for instance, the model will process forecast hours such as "002" and "036".

### downloadType
The download type, either GRIBFILTER or FILESERIES.

### gribFilterName
(GRIBFILTER only) the name of the filter.

### gribDirectory
(GRIBFILTER only) the directory of the model in the filter.

### baseDirectory
(GRIBFILTER only) the actual base directory the files are downloaded from

### gribFilename
(GRIBFILTER only) the filename to be downloaded.

### variables
(GRIBFILTER only) the variables to enable in the gribfilter.

### filetype
The type of file that will be downloaded. Usually grib2.

### url
(FILESERIES only) The full url to download the model from.

### extractBandsByMetadata
See the section for that earlier in the documentation.

### imageWidth
The width of the output GeoTIFF, in pixels. Not required.

# Script Flags
All of these overwrite the setting in the config, if it exists.

 * `--ignoredb` Don't make any database calls (for dev purposes)
 * `--forcemodel` Force run a model, ignore its enabled status (for dev purposes)
 * `--maxtime` Hard cutoff for forecast hour, so that the entire model run isn't processed (for dev purposes)
 * `--verbose` Disabled quiet mode for external calls (such as `gdalwarp`)

# Creating the Postgres Tables
See the sql dump for the schemas required for the tables. These need to go into the "logging" namespace.
