# eolus.io
Automated weather model retrieval and processing using FOSS4G.

More information:
https://medium.com/@potion_cellar/automated-weather-model-processing-with-foss4g-lessons-learned-8aaaeda1e3bc

# What's Here
`./model_processing` contains python code and JSON configuration for grabbing weather model data off the internet (via NCEP NOMADS), processing it, and organizing it on the file system.  This script is designed to be run on a regular basis from, for example, a cron job.

`./web` contains the PHP files which provide some mechanisms for basic model retrieval and viewing the logs / processing status.

The primary config (all the weather models and desired vars/levels) is found at `./model_processing/config.json`.
