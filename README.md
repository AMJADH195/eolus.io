# eolus.io
This repository contains a full server-side suite to create an API for retrieving weather model data in JSON format.

Live site:
http://eolus.io/ (CURRENTLY BEING REBUILT)

# What's Here
`./model_processing` contains some python code and configuration for grabbing weather model data off the internet (via NCEP NOMADS), processing it, and uploading it to a PostGIS database.  This script is designed to be run on a regular basis from, for example, a cron job.

`./web` contains the PHP files which provide an API for accessing the weather model data.

# Available Weather Models
See the wiki on this GitHub page.
