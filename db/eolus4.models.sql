CREATE TABLE eolus4.models
(
    model text COLLATE pg_catalog."default" NOT NULL,
    "timestamp" timestamp with time zone,
    status text COLLATE pg_catalog."default",
    lastfh text COLLATE pg_catalog."default",
    paused_at timestamp with time zone,
    CONSTRAINT models_pkey PRIMARY KEY (model)
)
WITH (
    OIDS = FALSE
)
TABLESPACE pg_default;

GRANT INSERT, SELECT, UPDATE, DELETE ON TABLE eolus4.models TO eolus;