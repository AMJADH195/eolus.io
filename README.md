# eolus.io
Automated weather model retrieval and processing using FOSS4G.

Postgres is used for maintaining status / logging, and the model processing script (which should be run by cron) creates flat directories of GeoTIFF files.

The primary use-case of this application is to create a library of weather models as geospatial rasters which can be distributed by an application like MapServer as a WMS. This allows for remote visualization and analysis of weather data in GIS applications and the web.

In the past, this used to have a nifty method of storing the rasters via PostGIS. It was then discovered that some models, with hundreds of bands, are nearly unusable when stored by PostGIS. Back to the flat GeoTIFF files...

# What's Here
`./model_processing` contains python code and JSON configuration for grabbing weather model data off the internet (via NCEP NOMADS), processing it, and organizing it on the file system.  This script is designed to be run on a regular basis from, for example, a cron job.

`./web` contains the PHP files which provide some mechanisms for basic model retrieval and viewing the logs / processing status.

# Available Weather Models
See the wiki on this GitHub page.
