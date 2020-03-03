CREATE TABLE eolus4.agents
(
    pid text COLLATE pg_catalog."default",
    start_time timestamp with time zone
)
WITH (
    OIDS = FALSE
)
TABLESPACE pg_default;

GRANT INSERT, SELECT, UPDATE, DELETE ON TABLE eolus4.agents TO eolus;