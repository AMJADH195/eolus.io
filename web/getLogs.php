<?php
require ("../pgcredentials.php");
header('Content-type: application/json');

$modelStatus = array();
$processingLogs = array();
$error = "";

$conn = pg_connect("host={$pghost} port=5432 dbname={$pgdb} user={$pguser} password={$pgpass} sslmode=require");
if (!$conn) {
    $error = "Could not connect to database.";
} else {
    $modelStatusResult = pg_query($conn, "SELECT * FROM logging.model_status ORDER BY model ASC");
    while ($row = pg_fetch_assoc($modelStatusResult)) {
        array_push ($modelStatus, $row);
    }

    $processingLogsResult = pg_query($conn, "SELECT * FROM logging.processing_logs ORDER BY timestamp DESC LIMIT 1000");
    while ($row = pg_fetch_assoc($processingLogsResult)) {
        array_push ($processingLogs, $row);
    }
}

echo json_encode (array(
    "modelStatus" => $modelStatus,
    "processingLogs" => $processingLogs,
    "error" => $error
));

?>
