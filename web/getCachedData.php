<?php

// TODO!
// Include timestamp of model run with all results!

require ("./models.php");   // $models variable is set here
require ("./versions.php"); // $versions variable is set here

// Globals  -----------
$version = $versions["alpha-02"];
$error = false;
$calcStartTime = round (microtime(true) * 1000);

$location = $_GET['location'];
$model = $_GET['model'];

date_default_timezone_set("UTC"); 
$now = time();
$outputData = [];

$modelData = $models[$model];

if (empty($modelData)) {
    array_push ($outputData, "ERROR: Model {$model} does not exist.");
    $error = true;
}

$rootDir = $modelData["Folder"];

foreach ($modelData["Model Outputs"] as $key => $value) {
    $folder = $rootDir . $key;
    $string = file_get_contents($folder . "/cache.json");
    $json_a = json_decode($string, true);
    $out = $json_a[$location];
    $outputData[$key] = $out;
}
$calcEndTime = round (microtime(true) * 1000);
$timeElapsed = ($calcEndTime - $calcStartTime)/1000 . " seconds";

if (!$error) {
    header('Content-type: application/json');
    echo json_encode ([
        "version" => $version["Name"], 
        "timeElapsed" => $timeElapsed,
        "wxdata" => $outputData
    ]);
}