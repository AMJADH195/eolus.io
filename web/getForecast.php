<?php
require ("./models.php");

// Point this to the location of your credentials
// file (if you want to use one).
require ("../pgcredentials.php");
$modelName = $_GET['model'];
$bandStr = $_GET['bands'];
$coordStr = $_GET['coords'];
header('Content-type: application/json');
$model = array();
$limit = "150";
/*
    --- MAIN ---
*/

verify_params ();

if (!array_key_exists ($modelName,$models)) {
    send_error("This model does not exist.");
}
else {
    $model = $models[$modelName];
    if (!$model["enabled"]) {
        send_error("This model is disabled.");
    }
}

$bands = explode (",",$bandStr);
if (count($bands) < 1) {
    send_error("`bands` parameter must be a comma-delimited list of band numbers.");
}

$coords = explode (",",$coordStr);
if (count($coords) != 2) {
    send_error ("`coords` parameter must be in the format `X,Y`");
}
if (!is_numeric($coords[0])) {
    send_error ("X coordinate is not numeric.");
}
if (!is_numeric($coords[1])) {
    send_error ("Y coordinate is not numeric.");
}

$conn = pg_connect("host={$pghost} port=5432 dbname={$pgdb} user={$pguser} password={$pgpass} sslmode=require");
if (!$conn) {
    send_error ("Could not connect to database.");
}

$result = pg_query($conn, build_query());
if (!$result) {
    send_error ("Could not query the database.");
}



$payload = array ();
while ($row = pg_fetch_assoc($result)) {
    array_push ($payload, $row);
}
send_success (array (
    "modelValid" => "unknown",
    "queryTime" => "unknown",
    "wxdata" => $payload
));


/*
    --- FUNCTIONS ---
*/

function send_response ($response) {
    echo json_encode ($response);
    die();
}

function send_error ($errorMessage) {
    send_response (array (
        "result" => "ERROR",
        "error" => array (
            "message" => $errorMessage
        )
    ));
}

function send_success ($payload) {
    $resp = array (
        "result" => "SUCCESS",
        "response" => $payload
    );
    send_response ($resp);
}

function verify_params () {
    global $modelName, $bandStr, $coordStr, $limit;

    if (empty ($modelName)) {
        send_error ("`model` parameter is required.");
    }
    if (empty ($bandStr)) {
        send_error ("`bands` parameter is required.");
    }
    if (empty ($coordStr)) {
        send_error ("`coords` parameter is required.");
    }

    if (!empty($_GET['limit'])) {
        if (!is_numeric ($_GET['limit'])) {
            send_error ("`limit` parameter must be numeric.");
        }
        $val = intval ($_GET['limit']);
        if ($val < 1 || $val > 400) {
            send_error ("`limit` parameter must be an integer between 1 and 400.");
        }
        $limit = $_GET['limit'];
    }
}

function build_query () {
    global $modelName, $coords, $bands, $limit;

    $query = "WITH pt AS (SELECT ST_SetSRID(ST_Point(";
    $query .= "{$coords[0]},{$coords[1]}";
    $query .= "),4326) geom) ";
    $query .= "SELECT wxmodel.timestamp";

    foreach ($bands as $band) {
        $query .= ", ";
        $bandParts = explode ("|", "$band");
        if (count($bandParts) != 2) {
            send_error ("Band error: All bands must be in format `band number|band name`");
        }
        $bandNumber = $bandParts[0];
        if (!is_numeric ($bandNumber)) {
            send_error ("Band error: all bands must be numeric values.");
        }
        $bandName = $bandParts[1];
        if (strlen ($bandName) > 16 || !ctype_alnum($bandName)) {
            send_error ("Band error: band name is not sensible.");
        }

        $query .= "ST_NearestValue (wxmodel.rast,{$bandNumber},geom) as {$bandName}";
    }

    $query .= " FROM pt p LEFT JOIN rasters.{$modelName} wxmodel ON (ST_Intersects(p.geom, wxmodel.rast))";
    $query .= " WHERE wxmodel.timestamp >= now()::date - interval '3 hours' ORDER BY wxmodel.timestamp LIMIT {$limit}";

    return $query;
}

?>