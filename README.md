# eolus.io
API for retrieving weather model data in JSON format.  Almost all models are North America or USA only.

Live demo, including living API spec / documentation:
http://eolus.io/

## Basic Workflow
A server continually checks NCEP NOMADS for updated model runs using the various shell scripts.  It then downloads all the pertinent GRIB files for the entire length of the model run.  These are converted to a folder of GeoTIFFs with GDAL.

The PHP API uses GDAL to read the model data from the raster cells.

This is not incredibly fast, and I wonder if PostGIS would be a more efficient method -- I will explore this.

## Current Models
Core Implementation = Most basic model data outputs, like temperature, precip, winds.

|Model|Status|Type|Timespan|Interval|Description|
|----|----|----|----|----|----|
| HIRESW-WRF | Core Implementation | Short Range | 0-48hr | 1hr | AWIPS 4.2km CONUS ARW (NCAR Advanced Research WRF)  Currently listed in the API as 'HIRESW' |
| HIRESW-NMMB | NOT IMPLEMENTED YET |     |      |       |                                   |
| HREF-MEAN | Core Implementation | Short Range | 0-36hr | 1hr | Mean-Weighted Ensemble.  Currently listed in the API as 'HREF' |
| HREF-PMMN | NOT IMPLEMENTED YET |   |        |                       |                                   |
| HREF-AVRG | NOT IMPLEMENTED YET |   |        |                       |                                   |
| RAP | WILL NOT BE IMPLEMENTED | | | | |
| HRRR | WILL NOT BE IMPLEMENTED | | | | |
| RTMA | WILL NOT BE IMPLEMENTED | | | | |
| NAM 3km | Core Implementation | Short Range | 0-60hr    | 1hr | CONUS only |
| NAM 12km | Core Implementation | Short-Medium Range | 0-84hr    | 3hr |  |
| SREF | NOT IMPLEMENTED YET |  |  |  |  |
| GFS | Core Implementation | Med-Long Range | 0-240hr | 1hr (3hr after 120) |  |
| 557ww | NOT IMPLEMENTED YET |  |   |   |   |
| NAEFS | NOT IMPLEMENTED YET |  |   |   |   |
| CMC | WILL NOT BE IMPLEMENTED | | | | |
| UKMET | NOT IMPLEMENTED YET | | | | |
| GEFS | NOT IMPLEMENTED YET | | | | |
| ECMWF | NOT IMPLEMENTED YET | | | | |

## Future Plans
 * Explore using PostGIS for raster storage and lookup.
 * Integrations with GeoServer to serve weather models as WMS-T or other time-aware OGC services
 * Implement exporting weather model images from the API
 * Continue to add support for more parameters in the models
 * Continue to add API functionality
 * Continue to add models