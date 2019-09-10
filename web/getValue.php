<?php

$band = $_GET['band'];
$year = $_GET['year'];
$month = $_GET['month'];
$day = $_GET['day'];
$fh = $_GET['fh'];
$model = $_GET['model'];
$lat = $_GET['lat'];
$lng = $_GET['lng'];

if (!is_numeric($band) || strlen($band) > 4) {
    echo "Invalid band.";
    exit (1);
}

if (!is_numeric($year) || strlen($year) != 4) {
    echo "Invalid year.";
    exit (1);
}

if (!is_numeric($month) || strlen($month) != 2) {
    echo "Invalid month.";
    exit (1);
}

if (!is_numeric($day) || strlen($day) != 2) {
    echo "Invalid day.";
    exit (1);
}

if (!is_numeric($fh) || strlen($fh) > 4) {
    echo "Invalid fh.";
    exit (1);
}

if (!preg_match('/^[a-zA-Z0-9_]+$/', $model) || strlen($model) < 3) {
    echo "Invalid model.";
    exit (1);
}

if (!is_numeric($lat)) {
    echo "Invalid lat.";
    exit (1);
}

if (!is_numeric($lng)) {
    echo "Invalid lng.";
    exit (1);
}

if ((float) $lat > 90 || (float) $lat < -90 || (float) $lng > 180 || (float) $lng < -180 ) {
    echo "Invalid bounds.";
    exit (1);
}
echo "hi";

?>