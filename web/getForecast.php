<?php

// TODO!
// Include timestamp of model run with all results!

require ("./models.php");   // $models variable is set here
require ("./versions.php"); // $versions variable is set here

// Globals  -----------
$outputFormat = "JSON";
$outputMode = "";
$outputName = "";
$model = "";
$starttime = 0;
$endtime = 240;
$timeInterval = 1;
$version = $versions["alpha-02"];
$error = false;
$modelOutputs = ["ALL"];
$calcStartTime = round (microtime(true) * 1000);

$x = $_GET['x'];
$y = $_GET['y'];

date_default_timezone_set("UTC"); 
$now = time();
$outputData = [];
// ---------------------

// Set output mode (default: MODEL) - 
// either provides a list of models, or outputs the data
if (isset($_GET['ListModels'])) {
    $outputMode = "LISTMODELS";
    $outputFormat = "HTML";
    $outputName = "models";
} else if (isset($_GET['ListVersions'])) {
    $outputMode = "LISTVERSIONS";
    $outputFormat = "HTML";
    $outputName = "versions";
} else {
    // Validate inputs
    if (isset($_GET['GetData'])) {
        $outputMode = "GETDATA";
        $outputNAme = "wxdata";
        if (isset($_GET['model'])) {
            $model = $_GET['model'];
            if (isset ($_GET['v'])) {
                $v = $_GET['v'];
                $version = $versions[$v];
                if (empty($version)) {
                    array_push ($outputData, "ERROR: This API version ({$v}) does not exist.");
                    $error = true;
                }
            }

            if (empty($model)) {
                array_push ($outputData, "ERROR: Model name is required.");
                $error = true;
            }

            if (isset($_GET["outputs"])) {
                $outputs = strtolower($_GET['outputs']);
                if ($outputs != "all") {
                    $modelOutputs = explode (",",$outputs);
                }
            }

            if (isset($_GET["interval"])) {
                $timeInterval = $_GET["interval"];
                if (!ctype_digit($timeInterval)) {
                    array_push ($outputData, "ERROR: Interval must be a whole number.");
                    $error = true;
                } else if ($timeInterval < 1) {
                    array_push ($outputData, "ERROR: Interval must 1 or greater.");
                    $error = true;
                }
            }
            $timeInterval = (int)$timeInterval;
        } else {
            array_push ($outputData, "ERROR: Model parameter is required.");
            $error = true;
        }
    } else {
        require ("./apiSpecs.php");
        exit (0);
    }

    if (empty($x) || empty($y)) {
        array_push ($outputData, "ERROR: x and y coordinates are required.");
        $error = true;
    }
    else if ($x < -180) {
        array_push ($outputData, "ERROR: x must be larger than or equal to -180.");
        $error = true;
    }
    else if ($x > 180) {
        array_push ($outputData, "ERROR: x must be less than or equal to 180.");
        $error = true;
    }
    else if ($y < -90) {
        array_push ($outputData, "ERROR: y must be larger than or equal to -90.");
        $error = true;
    }
    else if ($y > 90) {
        array_push ($outputData, "ERROR: y must be less than or equal to 90.");
        $error = true;
    }
}

// Set output format
if (isset($_GET['f'])) {
    $f = $_GET['f'];
    if ($f == "html") {
        $outputFormat = "HTML";
    } else if ($f == "json") {
        $outputFormat = "JSON";
    } else {
        array_push ($outputData, "ERROR: Unrecognized output format ({$f}).");
        $error = true;
    }
}

if ($outputFormat == "JSON") {
    header('Content-type: application/json');
}

// Run the actual output generator
if ($outputMode == "LISTMODELS") {
    if (!$error) printModelList ();
} else if ($outputMode == "LISTVERSIONS") {
    if (!$error) printVersionList ();  
} else {
    // TODO!  Older versions of this function should have a separate
    // require() based on the supplied version number.
    if (!$error) printForecastData ();
}

// Prints a list of the models and their metadata
function printModelList () {
    global $models, $outputData;
    $outputData = $models;
}

// Prints a list of all versions
function printVersionList () {
    global $versions, $outputData;
    $outputData = $versions;
}

// Generates the model data for the specified location,
// model, and timespan.
function printForecastData () {
    global $starttime, $endtime, $model, $models, $error, $modelOutputs, $outputData;

    if (isset($_GET['start'])) {
        $starttime = $_GET['start'];
    }

    $endtime = 240;
    if (isset($_GET['end'])) {
        $endtime = $_GET['end'];
    }

    $modelData = $models[$model];

    if (empty($modelData)) {
        array_push ($outputData, "ERROR: Model {$model} does not exist.");
        $error = true;
    }

    if ($starttime > $endtime) {
        array_push ($outputData, "ERROR: Start time cannot be larger than end time.");
        $error = true;
    }

    if ($endtime > 240) {
        array_push ($outputData, "ERROR: End time cannot be larger than 240.");
        $error = true;
    }

    if ($starttime < -120) {
        array_push ($outputData, "ERROR: Start time cannot be less than -120.");
        $error = true;
    }

    
    if (!$error) {

        $modelDataPackage = [];
        
        foreach ($modelData["Model Outputs"] as $outputName => $outputSpecs) {
            // Filter outputs to what was specified in &outputs=
            if ($modelOutputs[0] == "ALL" || in_array($outputName, $modelOutputs)) {
                foreach ($modelData["Model Outputs"][$outputName] as $outputSpec => $outputValue) {
                    if ($outputSpec == "File Prefix") {
                        array_push ($modelDataPackage, retrieveData ($modelData["Folder"], $outputName, $outputValue));
                    }
                }
            }
        }
        packageData ($modelDataPackage);
    }
}

function retrieveData ($folder, $name, $prefix) {
    global $x, $y, $starttime, $endtime, $timeInterval;
    $return = array();
    $fullPrefix = $folder . $prefix;
    $steps = $endtime - $starttime;
    $stepSize = $timeInterval;
    $date = makeDate ($starttime);
    $time = makeTime ($starttime);

    exec ("/wxdata/lookupForecast {$x} {$y} {$fullPrefix} {$date} {$time} {$steps} {$stepSize}",$return);
    array_unshift($return, $name);
    return $return;
}

function packageData ($dataArray) {
    global $outputData, $endtime, $starttime, $timeInterval;
    $steps = ($endtime - $starttime) / $timeInterval;
    $labels = [];
    for ($i = 0; $i < count($dataArray); $i ++) {
        array_push ($labels, $dataArray[$i][0]);
    }
    for ($i = 1; $i <= $steps; $i++) {
        $dataItem = [];
        $currentStep = (($i - 1) * $timeInterval) + $starttime;
        $timestamp = makeDate ($currentStep) . "T" . makeTime ($currentStep) . "0000000Z";
        $dataItem["timestamp"] = $timestamp;
        for ($ii = 0; $ii < count($dataArray); $ii++) {
            $dataItem[$labels[$ii]] = $dataArray[$ii][$i];
        }
        array_push ($outputData, $dataItem);
    }
}

function makeDate ($i) {
    // pretty sure $today is NULL...
    return date('Ymd', strtotime(" +" . $i . " hours"));
}

function makeTime ($i) {
    // pretty sure $today is NULL...
    return date('H', strtotime(" +" . $i . " hours"));
}

$calcEndTime = round (microtime(true) * 1000);
$timeElapsed = ($calcEndTime - $calcStartTime)/1000 . " seconds";

if ($outputFormat == "JSON") {
    if (!$error) {
        if ($outputMode == "GETDATA") {
            echo json_encode ([
                "version" => $version["Name"], 
                "timeElapsed" => $timeElapsed,
                "forecastInterval" => $timeInterval,
                $outputName => $outputData
            ]);
        } else {
            echo json_encode ([
                "version" => $version["Name"], 
                $outputName => $outputData
            ]);
        }
    } else {
        echo json_encode (["errors" => $outputData]);
    }
} else {
    require ("./eolusHeader.php");
    echo "<pre>";
    if ($outputMode == "GETDATA") {
        print_r ([
            "version" => $version["Name"], 
            "timeElapsed" => $timeElapsed,
            "forecastInterval" => $timeInterval,
            $outputName => $outputData
        ]);
    } else {
        print_r ([
                "version" => $version["Name"], 
                $outputName => $outputData
            ]);
    }
    echo "</pre>";
    require ("./eolusFooter.php");
}

?>