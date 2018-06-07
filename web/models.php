<?php

$models = array (
    "GFS" => array (
        "Folder" => "/wxdata/gfs/",

        "Name" => "Global Forecast System",
        "Resolution" => "0.25x0.25deg",
        "Timespan" => "0-240 hours",
        "Forecast Interval" => "Hourly through 120 hours, every 3 hours after",
        "Update Rate" => "Every 6 hours",
        "Agency" => "USA / NOAA / NCEP",
        "Coverage" => "World",
        "eolusVersion" => "0.9",
        "eolusLastUpdated" => "June 6, 2018",
        "Notes" => "Precip rate is currently not working.",

        "Model Outputs" => array (
            "tmp" => array (
                "File Prefix" => "tmp/SurfaceTemp",
                "Name" => "Temperature",
                "Units" => "Celsius",
                "Level" => "Surface"
            ),
            "tcdc" => array (
                "File Prefix" => "tcdc/CloudCover",
                "Name" => "Total Cloud Cover",
                "Units" => "Percent",
                "Level" => "Entire Atmosphere"
            ),
            "snod" => array (
                "File Prefix" => "snod/SnowDepth",
                "Name" => "Snow Depth",
                "Units" => "Meters",
                "Level" => "Surface"
            ),
            /* I BELIEVE THIS IS BROKEN
            "prate" => array (
                "File Prefix" => "prate/PrecipRate",
                "Name" => "Precipitation Rate",
                "Units" => "UNKNOWN TODO",
                "Level" => "Surface"
            ),*/
            "apcp" => array (
                "File Prefix" => "apcp/PrecipAccum",
                "Name" => "Accumulated Precipitation",
                "Units" => "Millimeters (kg/m^2)",
                "Level" => "Surface"
            ),
            "cape" => array (
                "File Prefix" => "cape/CAPE",
                "Name" => "CAPE",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "cin" => array (
                "File Prefix" => "cin/CIN",
                "Name" => "CIN",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "4lftx" => array (
                "File Prefix" => "4lftx/LiftedIndex",
                "Name" => "Four-Layer Lifted Index",
                "Units" => "Kelvin",
                "Level" => "Surface"
            ),
            "gust" => array (
                "File Prefix" => "gust/GustSpeed",
                "Name" => "Gust Speed",
                "Units" => "Meters Per Second",
                "Level" => "Surface"
            ),
            "ugrd" => array (
                "File Prefix" => "ugrd/SurfaceWindU",
                "Name" => "Wind U-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "vgrd" => array (
                "File Prefix" => "vgrd/SurfaceWindV",
                "Name" => "Wind V-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "csnow" => array (
                "File Prefix" => "csnow/CatSnow",
                "Name" => "Categorical Snow",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cicep" => array (
                "File Prefix" => "cicep/CatIcePellets",
                "Name" => "Categorical Ice Pellets",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cfrzr" => array (
                "File Prefix" => "cfrzr/CatFrzRain",
                "Name" => "Categorical Freezing Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "crain" => array (
                "File Prefix" => "crain/CatRain",
                "Name" => "Categorical Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            )
        )
    ),
    "HIRESW" => array (
        "Folder" => "/wxdata/hiresw/",

        "Name" => "HiRes Window AWIPS 4.2km CONUS ARW (NCAR Advanced Research WRF)",
        "Resolution" => "4.2km",
        "Timespan" => "0-48 hours",
        "Forecast Interval" => "1 Hours",
        "Update Rate" => "Every 12 hours",
        "Agency" => "USA / NOAA / NCEP",
        "Coverage" => "CONUS",        
        "eolusVersion" => "",
        "eolusLastUpdated" => "June 6, 2018",
        "Notes" => "",

        "Model Outputs" => array (
            "tmp" => array (
                "File Prefix" => "tmp/SurfaceTemp",
                "Name" => "Temperature",
                "Units" => "Celsius",
                "Level" => "Surface"
            ),
            "tcdc" => array (
                "File Prefix" => "tcdc/CloudCover",
                "Name" => "Total Cloud Cover",
                "Units" => "Percent",
                "Level" => "Entire Atmosphere"
            ),
            "apcp" => array (
                "File Prefix" => "apcp/PrecipAccum",
                "Name" => "Accumulated Precipitation",
                "Units" => "Millimeters (kg/m^2)",
                "Level" => "Surface"
            ),
            "cape" => array (
                "File Prefix" => "cape/CAPE",
                "Name" => "CAPE",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "cin" => array (
                "File Prefix" => "cin/CIN",
                "Name" => "CIN",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "4lftx" => array (
                "File Prefix" => "4lftx/LiftedIndex",
                "Name" => "Four-Layer Lifted Index",
                "Units" => "Kelvin",
                "Level" => "180-0mb Above Ground"
            ),
            "gust" => array (
                "File Prefix" => "gust/GustSpeed",
                "Name" => "Gust Speed",
                "Units" => "Meters Per Second",
                "Level" => "Surface"
            ),
            "ugrd" => array (
                "File Prefix" => "ugrd/SurfaceWindU",
                "Name" => "Wind U-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "vgrd" => array (
                "File Prefix" => "vgrd/SurfaceWindV",
                "Name" => "Wind V-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "csnow" => array (
                "File Prefix" => "csnow/CatSnow",
                "Name" => "Categorical Snow",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cicep" => array (
                "File Prefix" => "cicep/CatIcePellets",
                "Name" => "Categorical Ice Pellets",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cfrzr" => array (
                "File Prefix" => "cfrzr/CatFrzRain",
                "Name" => "Categorical Freezing Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "crain" => array (
                "File Prefix" => "crain/CatRain",
                "Name" => "Categorical Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            )
        )
    ),
    "HREF" => array (
        "Folder" => "/wxdata/href/",

        "Name" => "High Resolution Ensemble Forecast - Mean Weighted",
        "Resolution" => "~3km",
        "Timespan" => "0-36 hours",
        "Forecast Interval" => "1 Hours",
        "Update Rate" => "Every 6 hours",
        "Agency" => "USA / NOAA / NCEP",
        "Coverage" => "CONUS",        
        "eolusVersion" => "",
        "eolusLastUpdated" => "June 6, 2018",
        "Notes" => "",

        "Model Outputs" => array (
            "tmp" => array (
                "File Prefix" => "tmp/SurfaceTemp",
                "Name" => "Temperature",
                "Units" => "Celsius",
                "Level" => "2m Above Ground"
            ),
            "tcdc" => array (
                "File Prefix" => "tcdc/CloudCover",
                "Name" => "Total Cloud Cover",
                "Units" => "Percent",
                "Level" => "Entire Atmosphere"
            ),
            "apcp" => array (
                "File Prefix" => "apcp/PrecipAccum",
                "Name" => "Accumulated Precipitation",
                "Units" => "Millimeters (kg/m^2)",
                "Level" => "Surface"
            ),
            "cape" => array (
                "File Prefix" => "cape/CAPE",
                "Name" => "CAPE",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "cin" => array (
                "File Prefix" => "cin/CIN",
                "Name" => "CIN",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "ugrd" => array (
                "File Prefix" => "ugrd/SurfaceWindU",
                "Name" => "Wind U-Component",
                "Units" => "Meters Per Second",
                "Level" => "925mb"
            ),
            "vgrd" => array (
                "File Prefix" => "vgrd/SurfaceWindV",
                "Name" => "Wind V-Component",
                "Units" => "Meters Per Second",
                "Level" => "925mb"
            ),
            "csnow" => array (
                "File Prefix" => "csnow/CatSnow",
                "Name" => "Categorical Snow",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cicep" => array (
                "File Prefix" => "cicep/CatIcePellets",
                "Name" => "Categorical Ice Pellets",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cfrzr" => array (
                "File Prefix" => "cfrzr/CatFrzRain",
                "Name" => "Categorical Freezing Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "crain" => array (
                "File Prefix" => "crain/CatRain",
                "Name" => "Categorical Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            )
        )
    ),
    "NAM-NEST" => array (
        "Folder" => "/wxdata/namhres/",

        "Name" => "North American Mesoscale Forecast System (CONUS Nest)",
        "Resolution" => "3km",
        "Timespan" => "0-60 hours",
        "Forecast Interval" => "Hourly",
        "Update Rate" => "Every 6 hours",
        "Agency" => "USA / NOAA / NCEP",
        "Coverage" => "CONUS",        
        "eolusVersion" => "",
        "eolusLastUpdated" => "June 6, 2018",
        "Notes" => "",

        "Model Outputs" => array (
            "tmp" => array (
                "File Prefix" => "tmp/SurfaceTemp",
                "Name" => "Temperature",
                "Units" => "Celsius",
                "Level" => "Surface"
            ),
            "tcdc" => array (
                "File Prefix" => "tcdc/CloudCover",
                "Name" => "Total Cloud Cover",
                "Units" => "Percent",
                "Level" => "Entire Atmosphere"
            ),
            "ltng" => array (
                "File Prefix" => "ltng/Lightning",
                "Name" => "Lightning",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "snod" => array (
                "File Prefix" => "snod/SnowDepth",
                "Name" => "Snow Depth",
                "Units" => "Meters",
                "Level" => "Surface"
            ),
            "prate" => array (
                "File Prefix" => "prate/PrecipRate",
                "Name" => "Precipitation Rate",
                "Units" => "UNKNOWN TODO",
                "Level" => "Surface"
            ),
            "apcp" => array (
                "File Prefix" => "apcp/PrecipAccum",
                "Name" => "Accumulated Precipitation",
                "Units" => "Millimeters (kg/m^2)",
                "Level" => "Surface"
            ),
            "cape" => array (
                "File Prefix" => "cape/CAPE",
                "Name" => "CAPE",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "cin" => array (
                "File Prefix" => "cin/CIN",
                "Name" => "CIN",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "4lftx" => array (
                "File Prefix" => "4lftx/LiftedIndex",
                "Name" => "Four-Layer Lifted Index",
                "Units" => "Kelvin",
                "Level" => "180-0mb Above Ground"
            ),
            "gust" => array (
                "File Prefix" => "gust/GustSpeed",
                "Name" => "Gust Speed",
                "Units" => "Meters Per Second",
                "Level" => "Surface"
            ),
            "ugrd" => array (
                "File Prefix" => "ugrd/SurfaceWindU",
                "Name" => "Wind U-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "vgrd" => array (
                "File Prefix" => "vgrd/SurfaceWindV",
                "Name" => "Wind V-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "csnow" => array (
                "File Prefix" => "csnow/CatSnow",
                "Name" => "Categorical Snow",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cicep" => array (
                "File Prefix" => "cicep/CatIcePellets",
                "Name" => "Categorical Ice Pellets",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cfrzr" => array (
                "File Prefix" => "cfrzr/CatFrzRain",
                "Name" => "Categorical Freezing Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "crain" => array (
                "File Prefix" => "crain/CatRain",
                "Name" => "Categorical Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            )
        )
    ),
    "NAM" => array (
        "Folder" => "/wxdata/nam/",

        "Name" => "North American Mesoscale Forecast System",
        "Resolution" => "12km",
        "Timespan" => "0-84 hours",
        "Forecast Interval" => "3 Hours",
        "Update Rate" => "Every 6 hours",
        "Agency" => "USA / NOAA / NCEP",
        "Coverage" => "North America",        
        "eolusVersion" => "",
        "eolusLastUpdated" => "June 6, 2018",
        "Notes" => "",

        "Model Outputs" => array (
            "tmp" => array (
                "File Prefix" => "tmp/SurfaceTemp",
                "Name" => "Temperature",
                "Units" => "Celsius",
                "Level" => "Surface"
            ),
            "tcdc" => array (
                "File Prefix" => "tcdc/CloudCover",
                "Name" => "Total Cloud Cover",
                "Units" => "Percent",
                "Level" => "Entire Atmosphere"
            ),
            "ltng" => array (
                "File Prefix" => "ltng/Lightning",
                "Name" => "Lightning",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "snod" => array (
                "File Prefix" => "snod/SnowDepth",
                "Name" => "Snow Depth",
                "Units" => "Meters",
                "Level" => "Surface"
            ),
            "apcp" => array (
                "File Prefix" => "apcp/PrecipAccum",
                "Name" => "Accumulated Precipitation",
                "Units" => "Millimeters (kg/m^2)",
                "Level" => "Surface"
            ),
            "cape" => array (
                "File Prefix" => "cape/CAPE",
                "Name" => "CAPE",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "cin" => array (
                "File Prefix" => "cin/CIN",
                "Name" => "CIN",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "4lftx" => array (
                "File Prefix" => "4lftx/LiftedIndex",
                "Name" => "Four-Layer Lifted Index",
                "Units" => "Kelvin",
                "Level" => "180-0mb Above Ground"
            ),
            "gust" => array (
                "File Prefix" => "gust/GustSpeed",
                "Name" => "Gust Speed",
                "Units" => "Meters Per Second",
                "Level" => "Surface"
            ),
            "ugrd" => array (
                "File Prefix" => "ugrd/SurfaceWindU",
                "Name" => "Wind U-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "vgrd" => array (
                "File Prefix" => "vgrd/SurfaceWindV",
                "Name" => "Wind V-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "csnow" => array (
                "File Prefix" => "csnow/CatSnow",
                "Name" => "Categorical Snow",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cicep" => array (
                "File Prefix" => "cicep/CatIcePellets",
                "Name" => "Categorical Ice Pellets",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cfrzr" => array (
                "File Prefix" => "cfrzr/CatFrzRain",
                "Name" => "Categorical Freezing Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "crain" => array (
                "File Prefix" => "crain/CatRain",
                "Name" => "Categorical Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            )
        )
    ),
    "SREF" => array (
        "Folder" => "/wxdata/sref/",

        "Name" => "Short-Range Ensemble Forecast (ARW, Control)",
        "Resolution" => "12km",
        "Timespan" => "0-87 hours",
        "Forecast Interval" => "3 Hours",
        "Update Rate" => "Every 6 hours",
        "Agency" => "USA / NOAA / NCEP",
        "Coverage" => "North America",        
        "eolusVersion" => "0.9",
        "eolusLastUpdated" => "June 7, 2018",
        "Notes" => "",

        "Model Outputs" => array (
            "tmp" => array (
                "File Prefix" => "tmp/SurfaceTemp",
                "Name" => "Temperature",
                "Units" => "Celsius",
                "Level" => "Surface"
            ),
            "tcdc" => array (
                "File Prefix" => "tcdc/CloudCover",
                "Name" => "Total Cloud Cover",
                "Units" => "Percent",
                "Level" => "Entire Atmosphere"
            ),
            "apcp" => array (
                "File Prefix" => "apcp/AccumPrecip",
                "Name" => "Accumulated Precipitation",
                "Units" => "Millimeters (kg/m^2)",
                "Level" => "Surface"
            ),
            "vis" => array (
                "File Prefix" => "vis/Visibility",
                "Name" => "Visibility",
                "Units" => "Meters",
                "Level" => "Surface"
            ),
            "rh" => array (
                "File Prefix" => "rh/Humidity",
                "Name" => "Relative Humidity",
                "Units" => "Percent (%)",
                "Level" => "2m Above Ground"
            ),
            "pwat" => array (
                "File Prefix" => "pwat/PWAT",
                "Name" => "Precipitable Water",
                "Units" => "Millimeters (kg/m^2)",
                "Level" => "Entire Atmosphere"
            ),
            "cape" => array (
                "File Prefix" => "cape/CAPE",
                "Name" => "CAPE",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "cin" => array (
                "File Prefix" => "cin/CIN",
                "Name" => "CIN",
                "Units" => "J/kg",
                "Level" => "Surface"
            ),
            "4lftx" => array (
                "File Prefix" => "4lftx/LiftedIndex",
                "Name" => "Four-Layer Lifted Index",
                "Units" => "Kelvin",
                "Level" => "180-0mb Above Ground"
            ),
            "prate" => array (
                "File Prefix" => "prate/PrecipRate",
                "Name" => "Precipitation Rate",
                "Units" => "Millimeters Per Second",
                "Level" => "Surface"
            ),
            "ugrd" => array (
                "File Prefix" => "ugrd/SurfaceWindU",
                "Name" => "Wind U-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "vgrd" => array (
                "File Prefix" => "vgrd/SurfaceWindV",
                "Name" => "Wind V-Component",
                "Units" => "Meters Per Second",
                "Level" => "10m Above Ground"
            ),
            "csnow" => array (
                "File Prefix" => "csnow/CatSnow",
                "Name" => "Categorical Snow",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cicep" => array (
                "File Prefix" => "cicep/CatIcePellets",
                "Name" => "Categorical Ice Pellets",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "cfrzr" => array (
                "File Prefix" => "cfrzr/CatFrzRain",
                "Name" => "Categorical Freezing Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            ),
            "crain" => array (
                "File Prefix" => "crain/CatRain",
                "Name" => "Categorical Rain",
                "Units" => "Boolean",
                "Level" => "Surface"
            )
        )
    )
);

?>