# eolus.io
API for retrieving weather model data in JSON format.  Almost all models are North America or USA only.

Live demo, including living API spec / documentation:
http://eolus.io/

## Basic Workflow
A server continually checks NCEP NOMADS for updated model runs using the various shell scripts.  It then downloads all the pertinent GRIB files for the entire length of the model run.  These are converted to a folder of GeoTIFFs with GDAL.

The PHP API uses GDAL to read the model data from the raster cells.

This is not incredibly fast, and I wonder if PostGIS would be a more efficient method -- I will explore this.

## Current Models
Core implementation = Most basic model data outputs, like temperature, precip, winds.

|Model|Status|Type|Resolution|Timespan|Interval|Description|
|----|----|----|----|----|----|----|
| HIRESW-WRF | Core implementation | Mesoscale |4.2km| 0-48hr | 1hr | AWIPS 4.2km CONUS ARW (NCAR Advanced Research WRF).  Currently listed in the API as 'HIRESW' |
| HIRESW-NMMB | Not yet implemented |   |  |      |       |                                   |
| HREF-MEAN | Core implementation | Mesoscale, Ensemble |~3km| 0-36hr | 1hr | Mean-Weighted Ensemble.  Currently listed in the API as 'HREF' |
| HREF-PMMN | Not yet implemented |   | |       |                       |                                   |
| HREF-AVRG | Not yet implemented |   |  |      |                       |                                   |
| NAM 3km | Core implementation | Mesoscale |~3km | 0-60hr    | 1hr | CONUS only |
| NAM 12km | Core implementation | Mesoscale | 12km | 0-84hr    | 3hr | North America  |
| SREF-ARW | Core+ implementation | Mesoscale, Ensemble | 12km | 0-87hr | 3hr  | North America.  ARW Control run. |
| SREF-NMMB | Not yet implemented |  |  |  |  | |
| GFS | Core implementation | Global Numerical | 0.25deg | 0-240hr | 1hr (3hr after 120) |  |
| 557ww | Not yet implemented |  |   |   |   | |
| NAEFS | Full implementation | Global Numerical, Ensemble | 1deg  | 0-240hr | 6hr  | RH, PRES, DPT, TMP, TMAX, TMIN, UGRD, VGRD |
| UKMET | Not yet implemented | | | | | |
| GEFS | Not yet implemented | | | | | |

#### Will Not / No Plans to Implement:
| Model | Reason |
|-------|--------|
| RAP | Included in HREF |
| HRRR | Included in HREF |
| RTMA | NDFD precursor |
| CMC | Not a very good model, included in NAEFS |
| ECMWF | Extremely expensive |

## Future Plans
 * Explore using PostGIS for raster storage and lookup.
 * Integrations with GeoServer to serve weather models as WMS-T or other time-aware OGC services
 * Implement exporting weather model images from the API
 * Continue to add support for more parameters in the models
 * Continue to add API functionality
 * Continue to add models