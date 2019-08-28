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

# Configuration
By default the configuration is close to what is used in production on eolus.io. Of note, the geopgraphic extent is set to roughly contain the state of Colorado. It also connects to the eolus.io database by default (or it would, if you knew the password).

These values need to be changed to be applicable to your database and geographical area.

# Dependencies
These dependencies are required on the machine that is running `get_models.py`.

 * Python 2
 * GDAL/OGR
 * .pgpass file for connecting to your DB
 * Local filesystem access for the user running it
 
 ## Optional, but useful dependencies
 
 * MapServer, for actually making the models available on the web. See `eolus.map`

# Creating the Postgres Tables
See the sql dump for the schemas required for the tables. These need to go into the "logging" namespace.
