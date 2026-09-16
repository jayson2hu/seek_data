CREATE TABLE content_base_analysis (
	schema_version INTEGER NOT NULL,
	content_id VARCHAR(255) NOT NULL,
	input_snapshot JSON NOT NULL,
	analysis JSON,
	graph_version VARCHAR(255) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	run_id VARCHAR(64) NOT NULL,
	request_id VARCHAR(64) NOT NULL,
	status VARCHAR(32) NOT NULL,
	revision INTEGER NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (content_id),
	CONSTRAINT ck_l1_analysis_schema_version CHECK (schema_version = 1),
	CONSTRAINT ck_l1_analysis_status CHECK (status IN ('WAIT_SCORE', 'FAILED', 'CANCELLED'))
);

CREATE TABLE enrichment_cache (
	content_hash VARCHAR(64) NOT NULL,
	graph_version VARCHAR(255) NOT NULL,
	analysis JSON NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (content_hash, graph_version)
);

CREATE TABLE l1_outbox_events (
	event_id VARCHAR(100) NOT NULL,
	run_id VARCHAR(64) NOT NULL,
	topic VARCHAR(100) NOT NULL,
	aggregate_id VARCHAR(255) NOT NULL,
	payload JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	sent_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (event_id),
	UNIQUE (run_id)
);

CREATE TABLE l1_processing_runs (
	run_id VARCHAR(64) NOT NULL,
	request_id VARCHAR(64) NOT NULL,
	attempt INTEGER NOT NULL,
	content_id VARCHAR(255) NOT NULL,
	graph_version VARCHAR(255) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	input_hash VARCHAR(64) NOT NULL,
	input_snapshot JSON NOT NULL,
	reprocess_key VARCHAR(255),
	status VARCHAR(32) NOT NULL,
	analysis JSON,
	cache_hit INTEGER NOT NULL,
	prompt_tokens INTEGER NOT NULL,
	completion_tokens INTEGER NOT NULL,
	cost_units INTEGER NOT NULL,
	llm_calls INTEGER NOT NULL,
	cost_complete INTEGER NOT NULL,
	traces JSON NOT NULL,
	error TEXT,
	started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (run_id),
	CONSTRAINT uq_l1_run_request_attempt UNIQUE (request_id, attempt),
	CONSTRAINT ck_l1_run_attempt CHECK (attempt >= 1),
	CONSTRAINT ck_l1_run_status CHECK (status IN ('WAIT_SCORE', 'FAILED', 'CANCELLED'))
);

CREATE TABLE l1_schema_migrations (
	version SERIAL NOT NULL,
	PRIMARY KEY (version)
);

CREATE INDEX ix_l1_outbox_pending ON l1_outbox_events (sent_at, created_at);

CREATE INDEX ix_l1_runs_content ON l1_processing_runs (content_id, finished_at);

INSERT INTO l1_schema_migrations (version) VALUES (1);
