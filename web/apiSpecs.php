<?php require ("./eolusHeader.php"); ?>
<!--
<div class="usage">
Please constrain requests to only the time intervals and model outputs that you need.  At some point API keys will be required to utilize the API. <br>
Excessive usage, DDOS, and abuse of the API will be monitored.  eolus.io is hosted in the cloud.  All data is from the public domain.<br>
<b>Data is currently limited to the lat/lon extents of Colorado.  Coverage will be expanded to the full model extents after successful verification and testing of the API.</b>
</div>
<br>
<h3><a href='/?ListModels'>ListModels</a></h3>
<pre class="example">http://eolus.io/?ListModels</pre>
Emits a list of all possible weather models, their outputs, and related metadata.<br>

<table class="paramTable"><tr><td>Parameter</td><td>Description</td><td>Required?</td></tr>
<tr><td>f</td><td>The desired output format, either 'json' or 'html.'  Defaults to html.</td><td>No</td></tr></table>

<h3><a href='/?ListVersions'>ListVersions</a></h3>
<pre class="example">http://eolus.io/?ListVersions</pre>
Lists all the API versions that can be used for GetData, GetImage, and GetGeoLayer requests.<br>
<table class="paramTable"><tr><td>Parameter</td><td>Description</td><td>Required?</td></tr>
<tr><td>f</td><td>The desired output format, either 'json' or 'html.'  Defaults to html.</td><td>No</td></tr></table>

<h3>GetData</h3>
<pre class="example">http://eolus.io/?GetData&model=GFS&x=-105&y=39&end=24&outputs=tmp</pre>
Returns a time series of raw weather model output data for a lat-lon point.<br>

<table class="paramTable"><tr><td>Parameter</td><td>Description</td><td>Required?</td></tr>

<tr><td>model</td><td>Value must be the name of one of the weather models (see ListModels).</td><td>Yes</td></tr>

<tr><td>x</td><td>The WGS84 longitude of the point to retrieve model data for (-180 to 180).  Note the coverage of many models is not global.</td><td>Yes</td></tr>

<tr><td>y</td><td>The WGS84 latitude of the point to retrieve model data for (-90 to 90).  Note the coverage of many models is not global.</td><td>Yes</td></tr>

<tr><td>start</td><td>The number of hours before/after the current time to start retrieving model data.  Default is 0 (present).  Past model data only goes back about 48 hours before being deleted.</td><td>No</td></tr>

<tr><td>end</td><td>The number of hours before/after the current time to stop retrieving model data.  Default is 240 (10 days).  Must be larger than start.  Note that most models only run to a certain number of hours.</td><td>No</td></tr>

<tr><td>f</td><td>The desired output format, either 'json' or 'html.'  Defaults to json.</td><td>No</td></tr>

<tr><td>outputs</td><td>Comma-delimited model parameter outputs to include (see 'ListModels').  For example, "tmp,tcdc,snod" -- defaults to "all."</td><td>No</td></tr>

<tr><td>interval</td><td>The number of hours between forecasts.  Must be an integer.  Defaults to 1.  Warning: This will have unintended consequences for models that don't have hourly forecasts -- if the final time interval does not align with the interval of model forecasts, no data will be returned.</td><td>No</td></tr>

<tr><td>v</td><td>The API version to use.  Defaults to the latest version.</td><td>No</td></tr>

</table>


<h3>GetImage</h3>
Coming soon!<br>

<h3>GetGeoLayer</h3>
Coming soon!<br>-->
            <!-- <br><br>Todo: Add API key, add support for specifying which model outputs you want, add support for retrieving a specific API version. -->
<?php require ("./eolusFooter.php"); ?>