<?php

$bands = $_GET['bands'];
$year = $_GET['year'];
$month = $_GET['month'];
$day = $_GET['day'];
$hour = $_GET['hour'];

$fh = $_GET['fh'];

$fhStart = $_GET['fhstart'];
$fhEnd = $_GET['fhend'];
$fhStep = $_GET['fhstep'];

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

if (!isset($_GET['fhstep'])) {
    if (!is_numeric($fh) || strlen($fh) > 4) {
        echo "Invalid fh.";
        exit (1);
    }
} else {
    if (!is_numeric($fhStart)) {
        echo "Invalid fhStart";
        exit (1);
    } 

    if (!is_numeric($fhEnd)) {
        echo "Invalid fhEnd";
        exit (1);
    } 

    if (!is_numeric($fhStep)) {
        echo "Invalid fhStep";
        exit (1);
    } 
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

if (isset($_GET['debug'])) {
    $debug = true;
}

if ((float) $lat > 90 || (float) $lat < -90 || (float) $lng > 180 || (float) $lng < -180 ) {
    echo "Invalid bounds.";
    exit (1);
}
$prefix = "/map/{$model}/{$model}_${year}-{$month}-{$day}_{$hour}z_";
$values = [];
$error = "";
$data = [ "values" => [] ];

if (!isset($_GET['fhstep'])) {
    $filename = $prefix . "t{$fh}.tif";
    $cmd = "gdallocationinfo -valonly {$bands} -wgs84 {$filename} {$lng} {$lat}";
    exec($cmd, $output, $return_var );
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
            "filename" => $filename,
            "bands" => $bands,
            "cmd" => $cmd,
            "output" => $output
        ];
    }
} else {
    for ($fh = intval($fhStart); $fh <= intval($fhEnd); $fh += intval($fhStep)) {
        $output = [];
        $fhStr = strval($fh);
        $filename = $prefix . "t{$fhStr}.tif";
        $cmd = "gdallocationinfo -valonly {$bands} -wgs84 {$filename} {$lng} {$lat}";
        exec($cmd, $output, $return_var );
        if ($return_var > 0) {
            $error = "Get value failed with code " . strval($return_var);
        } else {
            $values = $output;
        }
        $data["values"][$fhStr] = [
            "values" => $values,
            "error" => $error
        ];
    }
}



header('Content-type: application/json');
echo json_encode($data);

?>