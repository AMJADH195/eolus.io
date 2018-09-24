This script downloads a variety of weather models (if a new update is available) from NCEP NOMADS using their GRIB filter and uploads them to a Postgres, PostGIS database as rasters.

The script works by reading a config JSON containing general configuration options and model-specific information.  The script checks if a newer model is available, compared to the last updated timestamp.  If so, the GRIB2 file is downloaded from NOMADS, warped to EPSG:4326 (using `gdalwarp` -- GeoTIFF format), then dumped as a SQL file (using `raster2pgsql`).  The timestamp of the model is injected into the SQL which is then executed.

# Configuration
The default config is set to download all models, **restricted to an area that encompasses the state of Colorado.**  It also connects to the eolus.io database by default (or it would, if you knew the password).

These values need to be changed to be applicable to your database and geographical area.

# Script Dependencies
These dependencies are required on the machine that is running `get_models.py`.

 * GDAL/OGR
 * PostGIS (raster2pgsql)
 * .pgpass file for connecting to your DB
 * Local filesystem access for the user running it

# Database Dependencies
 * PostGIS

# Creating the PostGIS Tables
Create a table with the exact same name as the model in config.json.

### Columns
| Column Name | Type | Notes |
|-------------|------|-------|
| timestamp | time stamp with time zone | NOT NULL, primary key |
| rast | raster |    |

### Upsert Rule
Create a rule to upsert into the table, as raster2pgsql only creates INSERT statements:

```
CREATE RULE <MODELNAME>_Upsert AS ON INSERT TO <MODELNAME>
  WHERE EXISTS (SELECT 1 from <MODELNAME> M where NEW.timestamp = M.timestamp)
  DO INSTEAD
     UPDATE <MODELNAME> SET rast = NEW.rast WHERE timestamp = NEW.timestamp;
```

# Notes
The script creates a lockfile.  This allows the script to be scheduled to run many times per hour without duplicating efforts.

Currently, this file does not get removed if the script crashes for some reason.  You may need to `rm .get_models_lockfile` if this occurs.

# Sample Query
'''
WITH pt AS (SELECT ST_SetSRID(ST_Point(-105,39.7392),4326) geom)
	SELECT
		wxmodel.timestamp,
		ST_NearestValue (wxmodel.rast, 1, geom) as dunno,
		ST_NearestValue (wxmodel.rast, 2, geom) as dunno2,
		ST_NearestValue (wxmodel.rast, 3, geom) as dunno3,
		ST_NearestValue (wxmodel.rast, 4, geom) as dunno4
	FROM pt p
		LEFT JOIN rasters.gfs wxmodel ON (ST_Intersects(p.geom, wxmodel.rast))
	WHERE wxmodel.timestamp >= now()
'''