# Model Processing Overview

1. Run through the config and see which models are active.
2. Cross-reference that model, and its run times, with the status on Postgres.
3. If the model is not currently processing, and the last processed timestamp is older than the latest available model, begin the process.
4. 

## Where do the models come from?

The models come from NCEP NOMADS folders. Some of them are downloaded directly, while others are retrieved via their GRIB filter (usually models that are prohibitively large, e.g. a few hundred megabytes per timestamp).

## Why are only certain bands of the models retrieved?

Most of the models don't just have "useful" outputs such as surface temperature. Model outputs generally contain all the data used by the model in its calculations, e.g. the state of the atmosphere at a dozen different layers. Most of this is not very useful for general forecasting work, and the model size can be greatly reduced by omitting this data.

# Configuration
The default config is set to download all models, **restricted to an area that encompasses the state of Colorado.**  It also connects to the eolus.io database by default (or it would, if you knew the password).

These values need to be changed to be applicable to your database and geographical area.

# Dependencies
These dependencies are required on the machine that is running `get_models.py`.

 * GDAL/OGR
 * .pgpass file for connecting to your DB
 * Local filesystem access for the user running it
 
 ## Optional, but useful dependencies
 
 * MapServer, for actually making the models available on the web. See `eolus.map`

# Creating the Postgres Tables
See the sql dump for the schemas required for the tables. These need to go into the "logging" namespace.
