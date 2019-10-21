<?php

$lat = $_GET['lat'];
$lng = $_GET['lng'];
$debug = false;

if (!is_numeric($lat)) {
    echo "Invalid lat.";
    exit (1);
}

if (!is_numeric($lng)) {
    echo "Invalid lng.";
    exit (1);
}

if (isset($_GET['debug'])) {
    $debug = true;
}

if ((float) $lat > 90 || (float) $lat < -90 || (float) $lng > 180 || (float) $lng < -180 ) {
    echo "Invalid bounds.";
    exit (1);
}
$dem = "/map/wx_2p5_dem.tiff";
$elev = "";
$error = "";

$cmd = "gdallocationinfo -valonly -wgs84 {$dem} {$lng} {$lat}";
exec($cmd, $output, $return_var );
if ($return_var > 0) {
    $error = "Get value failed with code " . strval($return_var);
} else {
    $elev = $output;
}
$data = [
    "elevation" => $elev,
    "error" => $error
];

header('Content-type: application/json');
echo json_encode($data);

?>