-- Table: logging.run_status

-- DROP TABLE logging.run_status;

CREATE TABLE logging.run_status
(
    model text COLLATE pg_catalog."default",
    result text COLLATE pg_catalog."default",
    model_timestamp timestamp with time zone,
    fh_complete integer,
    time_start timestamp with time zone,
    time_end timestamp with time zone
)
WITH (
    OIDS = FALSE
)
TABLESPACE pg_default;