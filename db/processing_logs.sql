-- Table: logging.processing_logs

-- DROP TABLE logging.processing_logs;

CREATE TABLE logging.processing_logs
(
    "timestamp" timestamp with time zone NOT NULL,
    model text COLLATE pg_catalog."default",
    level text COLLATE pg_catalog."default" NOT NULL,
    message text COLLATE pg_catalog."default",
    CONSTRAINT processing_logs_pkey PRIMARY KEY ("timestamp")
)
WITH (
    OIDS = FALSE
)
TABLESPACE pg_default;