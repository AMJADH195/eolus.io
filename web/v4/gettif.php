<?php

$model = $_GET['model'];
$year = $_GET['year'];
$month = $_GET['month'];
$day = $_GET['day'];
$hour = $_GET['hour'];
$param = $_GET['param'];
$level = $_GET['level'];


if (!is_numeric($year) || strlen($year) != 4) {
    $errors[] = "Invalid year.";
}

if (!is_numeric($month) || strlen($month) != 2) {
    $errors[] = "Invalid month.";
}

if (!is_numeric($day) || strlen($day) != 2) {
    $errors[] = "Invalid day.";
}

if (!is_numeric($hour) || strlen($hour) != 2) {
    $errors[] = "Invalid hour.";
}

if (!preg_match('/^[a-zA-Z0-9_]+$/', $model) || strlen($model) < 3) {
    $errors[] = "Invalid model.";
}

if (!preg_match('/^[a-zA-Z0-9_]+$/', $level)) {
    $errors[] = "Invalid level.";
}

if (!preg_match('/^[a-zA-Z0-9_]+$/', $param)) {
    $errors[] = "Invalid param.";
}

$filename = "/map/rawdata/{$model}/{$model}_${year}{$month}{$day}_{$hour}Z_{$param}_{$level}.tif";

if (file_exists ($filename) && count ($errors) == 0) {
    readfile($filename);
    exit (0);
} else {    
    header('Content-type: application/json');
    if (!file_exists ($filename) && count ($errors) == 0) {
        $errors[] = "File does not exist. Check date/time and param/level.";
    }
    echo json_encode([ "errors" => $errors ]);
    exit (1);
}
?>