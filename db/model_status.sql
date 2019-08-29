-- Table: logging.model_status

-- DROP TABLE logging.model_status;

CREATE TABLE logging.model_status
(
    model text COLLATE pg_catalog."default" NOT NULL,
    status text COLLATE pg_catalog."default",
    model_timestamp timestamp with time zone,
    warnings integer,
    errors integer,
    log text COLLATE pg_catalog."default",
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    progress double precision,
    CONSTRAINT model_status_pkey PRIMARY KEY (model)
)
WITH (
    OIDS = FALSE
)
TABLESPACE pg_default;