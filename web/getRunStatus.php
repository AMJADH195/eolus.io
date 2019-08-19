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
    $runsResult = pg_query($conn, "SELECT * FROM logging.run_status ORDER BY model ASC");
    while ($row = pg_fetch_assoc($runResult)) {
        array_push ($modelStatus, $row);
    }
}

echo json_encode (array(
    "runs" => $modelStatus,
    "error" => $error
));

?>
