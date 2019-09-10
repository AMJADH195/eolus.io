<?php

$bands = $_GET['bands'];
$year = $_GET['year'];
$month = $_GET['month'];
$day = $_GET['day'];
$hour = $_GET['hour'];
$fh = $_GET['fh'];
$model = $_GET['model'];
$lat = $_GET['lat'];
$lng = $_GET['lng'];
$debug = false;

if (!preg_match('/^[0-9,]+$/', $bands)) {
    echo "Invalid bands.";
    exit (1);
} else {
    $bandArr = explode(",", $bands);
    $bandList = join(" -b ", $bandArr);
    $bands = "-b " . $bandList;
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

if (!is_numeric($hour) || strlen($hour) != 2) {
    echo "Invalid hour.";
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

if ($_GET['debug'] == "true") {
    $debug = true;
}

if ((float) $lat > 90 || (float) $lat < -90 || (float) $lng > 180 || (float) $lng < -180 ) {
    echo "Invalid bounds.";
    exit (1);
}
$filename = "/map/{$model}/{$model}_${year}-{$month}-{$day}_{$hour}z_t{$fh}.tif";

exec("gdallocationinfo -valonly {$bands} -wgs84 {$filename} {$lng} {$lat} 2>&1", $output, $return_var );

$values = [];
$error = "";
$debug = "";

if ($return_var > 0) {
    $error = "Get value failed with code " . strval($return_var);
} else {
    $values = $output;
}

$data = [
    "values" => $values,
    "error" => $error
];

if ($debug) {
    $data["debug"] = [
        "Filename: " . $filename,
        "Bands: " . $bands,
        "Cmd: " . $cmd,
        "Output" . implode($output)
    ];
}

header('Content-type: application/json');
echo json_encode($data);

?>