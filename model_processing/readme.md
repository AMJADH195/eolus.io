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