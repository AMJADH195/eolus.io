CREATE TABLE eolus4.run_status
(
    model text COLLATE pg_catalog."default",
    "timestamp" timestamp with time zone,
    status text COLLATE pg_catalog."default"
)
WITH (
    OIDS = FALSE
)
TABLESPACE pg_default;

GRANT INSERT, SELECT, UPDATE, DELETE ON TABLE eolus4.run_status TO eolus;