-- Autonomous Form Submission Database Schema

-- Domains table
CREATE TABLE IF NOT EXISTS domains (
    id BIGSERIAL PRIMARY KEY,
    url VARCHAR(512) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    contact_url VARCHAR(512),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_domains_status ON domains(status);
CREATE INDEX IF NOT EXISTS idx_domains_url ON domains(url);
CREATE INDEX IF NOT EXISTS idx_domains_created_at ON domains(created_at);

-- Contact forms table
CREATE TABLE IF NOT EXISTS contact_forms (
    id BIGSERIAL PRIMARY KEY,
    domain_id BIGINT NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    url VARCHAR(512) NOT NULL,
    fields JSONB NOT NULL,
    submit_selector VARCHAR(512),
    has_captcha BOOLEAN DEFAULT FALSE,
    captcha_type VARCHAR(50),
    form_html TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forms_domain_id ON contact_forms(domain_id);
CREATE INDEX IF NOT EXISTS idx_forms_url ON contact_forms(url);
CREATE INDEX IF NOT EXISTS idx_forms_has_captcha ON contact_forms(has_captcha);

-- Submissions table
CREATE TABLE IF NOT EXISTS submissions (
    id BIGSERIAL PRIMARY KEY,
    domain_id BIGINT NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    form_url VARCHAR(512) NOT NULL,
    status VARCHAR(50) NOT NULL,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INT,
    had_captcha BOOLEAN DEFAULT FALSE,
    captcha_solved BOOLEAN DEFAULT FALSE,
    captcha_type VARCHAR(50),
    captcha_cost DECIMAL(10, 6) DEFAULT 0,
    proxy_used VARCHAR(256),
    error_message TEXT,
    screenshot_path VARCHAR(512),
    success_indicator VARCHAR(512),
    response_url VARCHAR(512),
    attempts INT NOT NULL DEFAULT 1,
    template VARCHAR(100),
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_submissions_domain_id ON submissions(domain_id);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
CREATE INDEX IF NOT EXISTS idx_submissions_submitted_at ON submissions(submitted_at);
CREATE INDEX IF NOT EXISTS idx_submissions_had_captcha ON submissions(had_captcha);

-- Metrics table for aggregated statistics
CREATE TABLE IF NOT EXISTS metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20, 6) NOT NULL,
    labels JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);

-- Errors table for detailed error tracking
CREATE TABLE IF NOT EXISTS errors (
    id BIGSERIAL PRIMARY KEY,
    domain_id BIGINT REFERENCES domains(id) ON DELETE CASCADE,
    submission_id BIGINT REFERENCES submissions(id) ON DELETE CASCADE,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    context JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_errors_domain_id ON errors(domain_id);
CREATE INDEX IF NOT EXISTS idx_errors_submission_id ON errors(submission_id);
CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type);
CREATE INDEX IF NOT EXISTS idx_errors_created_at ON errors(created_at);

-- Proxy performance table
CREATE TABLE IF NOT EXISTS proxy_performance (
    id BIGSERIAL PRIMARY KEY,
    proxy_id VARCHAR(256) NOT NULL UNIQUE,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    total_requests INT DEFAULT 0,
    avg_response_time_ms INT,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proxy_perf_proxy_id ON proxy_performance(proxy_id);
CREATE INDEX IF NOT EXISTS idx_proxy_perf_last_used ON proxy_performance(last_used_at);

-- Create a function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_domains_updated_at BEFORE UPDATE ON domains
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_proxy_performance_updated_at BEFORE UPDATE ON proxy_performance
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for submission statistics
CREATE OR REPLACE VIEW submission_stats AS
SELECT 
    COUNT(*) as total_submissions,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_submissions,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_submissions,
    COUNT(CASE WHEN status = 'skipped' THEN 1 END) as skipped_submissions,
    COUNT(CASE WHEN status = 'captcha_failed' THEN 1 END) as captcha_failed_submissions,
    ROUND(100.0 * COUNT(CASE WHEN status = 'success' THEN 1 END) / NULLIF(COUNT(*), 0), 2) as success_rate,
    COUNT(CASE WHEN had_captcha = true THEN 1 END) as submissions_with_captcha,
    COUNT(CASE WHEN captcha_solved = true THEN 1 END) as captchas_solved,
    SUM(captcha_cost) as total_captcha_cost,
    AVG(duration_ms) as avg_duration_ms,
    MAX(submitted_at) as last_submission_at
FROM submissions;

-- Create view for domain statistics
CREATE OR REPLACE VIEW domain_stats AS
SELECT 
    COUNT(*) as total_domains,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_domains,
    COUNT(CASE WHEN status = 'discovery' THEN 1 END) as discovery_domains,
    COUNT(CASE WHEN status = 'found' THEN 1 END) as found_domains,
    COUNT(CASE WHEN status = 'not_found' THEN 1 END) as not_found_domains,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_domains,
    COUNT(CASE WHEN contact_url IS NOT NULL THEN 1 END) as domains_with_contact_url
FROM domains;

-- Insert initial metrics
INSERT INTO metrics (metric_name, metric_value, labels) VALUES
    ('system_initialized', 1, '{"version": "1.0", "budget_mode": true}');

COMMENT ON TABLE domains IS 'Stores domain information and discovery status';
COMMENT ON TABLE contact_forms IS 'Stores discovered contact forms with field mappings';
COMMENT ON TABLE submissions IS 'Stores submission attempts and results';
COMMENT ON TABLE metrics IS 'Stores time-series metrics for monitoring';
COMMENT ON TABLE errors IS 'Stores detailed error information for debugging';
COMMENT ON TABLE proxy_performance IS 'Tracks proxy performance and reliability';
