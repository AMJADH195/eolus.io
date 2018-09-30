<?php require ("./eolusHeader.php"); ?>

<div class="usage">
This is a private API at the moment.  Data is constrained to the state of Colorado.  API key enforcement will be implemented once this endpoint is consumed by other websites in production.
</div>
<br>
<!--
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
-->
<h3>GetForecast</h3>
<pre class="example">http://eolus.io/getForecast.php?model=gfs&coords=-105,39&bands=1|bandname,2|otherbandname&limit=60</pre>
Returns a time series of raw weather model output data for a lat-lon point.<br>

<table class="paramTable"><tr><td>Parameter</td><td>Description</td><td>Required?</td></tr>

<tr><td>model</td><td>Value must be the name of one of the weather models (see <a href="https://github.com/thurs/eolus.io/wiki">wiki on GitHub</a>).</td><td>Yes</td></tr>

<tr><td>coords</td><td>The WGS84 [longitude,latitude] of the point to retrieve model data for (-180 to 180 and 90 to -90).</td><td>Yes</td></tr>

<tr><td>bands</td><td>The list of bands from the model to retrieve.  Each band is separated by commas, and in the format [band_number|band_name].</td><td>Yes</td></tr>

<tr><td>limit</td><td>The maximum number of timesteps to retrieve.</td><td>No</td></tr>
</table>

<!--
<h3>GetImage</h3>
Coming soon!<br>

<h3>GetGeoLayer</h3>
Coming soon!<br>-->
            <!-- <br><br>Todo: Add API key, add support for specifying which model outputs you want, add support for retrieving a specific API version. -->
<?php require ("./eolusFooter.php"); ?>