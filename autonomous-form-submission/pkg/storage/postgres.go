package storage

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/lib/pq"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/models"
	"go.uber.org/zap"
)

// PostgresDB handles database operations
type PostgresDB struct {
	db     *sql.DB
	logger *zap.Logger
}

// PostgresConfig contains PostgreSQL configuration
type PostgresConfig struct {
	ConnectionString string
	MaxConnections   int
	Logger           *zap.Logger
}

// NewPostgresDB creates a new PostgreSQL database connection
func NewPostgresDB(config PostgresConfig) (*PostgresDB, error) {
	db, err := sql.Open("postgres", config.ConnectionString)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(config.MaxConnections)
	db.SetMaxIdleConns(config.MaxConnections / 2)
	db.SetConnMaxLifetime(time.Hour)

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	config.Logger.Info("PostgreSQL database connected", 
		zap.Int("max_connections", config.MaxConnections))

	return &PostgresDB{
		db:     db,
		logger: config.Logger,
	}, nil
}

// Domain operations

// CreateDomain creates a new domain record
func (p *PostgresDB) CreateDomain(ctx context.Context, url string) (*models.Domain, error) {
	query := `
		INSERT INTO domains (url, status, created_at, updated_at)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (url) DO NOTHING
		RETURNING id, url, status, created_at, updated_at
	`

	domain := &models.Domain{
		URL:       url,
		Status:    models.DomainStatusPending,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	err := p.db.QueryRowContext(ctx, query, 
		domain.URL, domain.Status, domain.CreatedAt, domain.UpdatedAt,
	).Scan(&domain.ID, &domain.URL, &domain.Status, &domain.CreatedAt, &domain.UpdatedAt)

	if err == sql.ErrNoRows {
		// Domain already exists, fetch it
		return p.GetDomainByURL(ctx, url)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to create domain: %w", err)
	}

	return domain, nil
}

// GetDomainByURL retrieves a domain by URL
func (p *PostgresDB) GetDomainByURL(ctx context.Context, url string) (*models.Domain, error) {
	query := `
		SELECT id, url, status, contact_url, created_at, updated_at, attempts, last_error
		FROM domains WHERE url = $1
	`

	domain := &models.Domain{}
	var contactURL, lastError sql.NullString

	err := p.db.QueryRowContext(ctx, query, url).Scan(
		&domain.ID, &domain.URL, &domain.Status, &contactURL,
		&domain.CreatedAt, &domain.UpdatedAt, &domain.Attempts, &lastError,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get domain: %w", err)
	}

	domain.ContactURL = contactURL.String
	domain.LastError = lastError.String

	return domain, nil
}

// UpdateDomainStatus updates a domain's status
func (p *PostgresDB) UpdateDomainStatus(ctx context.Context, id int64, status models.DomainStatus, contactURL string, err error) error {
	query := `
		UPDATE domains 
		SET status = $1, contact_url = $2, last_error = $3, attempts = attempts + 1, updated_at = $4
		WHERE id = $5
	`

	var errorMsg sql.NullString
	if err != nil {
		errorMsg = sql.NullString{String: err.Error(), Valid: true}
	}

	var contactURLVal sql.NullString
	if contactURL != "" {
		contactURLVal = sql.NullString{String: contactURL, Valid: true}
	}

	_, execErr := p.db.ExecContext(ctx, query, status, contactURLVal, errorMsg, time.Now(), id)
	if execErr != nil {
		return fmt.Errorf("failed to update domain status: %w", execErr)
	}

	return nil
}

// Contact form operations

// SaveContactForm saves a discovered contact form
func (p *PostgresDB) SaveContactForm(ctx context.Context, form *models.ContactForm) error {
	query := `
		INSERT INTO contact_forms (domain_id, url, fields, submit_selector, has_captcha, captcha_type, form_html, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (domain_id) DO UPDATE 
		SET url = $2, fields = $3, submit_selector = $4, has_captcha = $5, captcha_type = $6, form_html = $7
	`

	fieldsJSON, err := json.Marshal(form.Fields)
	if err != nil {
		return fmt.Errorf("failed to marshal fields: %w", err)
	}

	var captchaType sql.NullString
	if form.CaptchaType != "" {
		captchaType = sql.NullString{String: form.CaptchaType, Valid: true}
	}

	_, err = p.db.ExecContext(ctx, query,
		form.DomainID, form.URL, fieldsJSON, form.SubmitSelector,
		form.HasCaptcha, captchaType, form.FormHTML, time.Now(),
	)

	if err != nil {
		return fmt.Errorf("failed to save contact form: %w", err)
	}

	p.logger.Debug("contact form saved", zap.Int64("domain_id", form.DomainID))
	return nil
}

// Submission operations

// CreateSubmission creates a new submission record
func (p *PostgresDB) CreateSubmission(ctx context.Context, submission *models.SubmissionResult) error {
	query := `
		INSERT INTO submissions (
			domain_id, form_url, status, submitted_at, completed_at, duration_ms,
			had_captcha, captcha_solved, captcha_type, captcha_cost, proxy_used,
			error_message, screenshot_path, success_indicator, response_url,
			attempts, template, user_agent
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
		RETURNING id
	`

	var completedAt sql.NullTime
	if submission.CompletedAt != nil {
		completedAt = sql.NullTime{Time: *submission.CompletedAt, Valid: true}
	}

	var captchaType, proxyUsed, errorMsg, screenshotPath, successIndicator, responseURL sql.NullString
	if submission.CaptchaType != "" {
		captchaType = sql.NullString{String: submission.CaptchaType, Valid: true}
	}
	if submission.ProxyUsed != "" {
		proxyUsed = sql.NullString{String: submission.ProxyUsed, Valid: true}
	}
	if submission.ErrorMessage != "" {
		errorMsg = sql.NullString{String: submission.ErrorMessage, Valid: true}
	}
	if submission.ScreenshotPath != "" {
		screenshotPath = sql.NullString{String: submission.ScreenshotPath, Valid: true}
	}
	if submission.SuccessIndicator != "" {
		successIndicator = sql.NullString{String: submission.SuccessIndicator, Valid: true}
	}
	if submission.ResponseURL != "" {
		responseURL = sql.NullString{String: submission.ResponseURL, Valid: true}
	}

	err := p.db.QueryRowContext(ctx, query,
		submission.DomainID, submission.FormURL, submission.Status, submission.SubmittedAt,
		completedAt, submission.Duration, submission.HadCaptcha, submission.CaptchaSolved,
		captchaType, submission.CaptchaCost, proxyUsed, errorMsg, screenshotPath,
		successIndicator, responseURL, submission.Attempts, submission.Template,
		submission.UserAgent,
	).Scan(&submission.ID)

	if err != nil {
		return fmt.Errorf("failed to create submission: %w", err)
	}

	p.logger.Debug("submission created",
		zap.Int64("id", submission.ID),
		zap.String("status", string(submission.Status)),
	)

	return nil
}

// GetSubmissionStats retrieves aggregated submission statistics
func (p *PostgresDB) GetSubmissionStats(ctx context.Context) (*models.SubmissionMetrics, error) {
	query := `SELECT * FROM submission_stats`

	stats := &models.SubmissionMetrics{}

	err := p.db.QueryRowContext(ctx, query).Scan(
		&stats.TotalAttempted,
		&stats.TotalSuccess,
		&stats.TotalFailed,
		&stats.TotalSkipped,
		&stats.CaptchasSolved,
		&stats.SuccessRate,
		&stats.TotalAttempted, // submissions_with_captcha
		&stats.CaptchasSolved,
		&stats.TotalCaptchaCost,
		&stats.AverageDuration,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to get submission stats: %w", err)
	}

	return stats, nil
}

// Proxy performance operations

// UpdateProxyPerformance updates proxy performance metrics
func (p *PostgresDB) UpdateProxyPerformance(ctx context.Context, proxyID string, success bool, responseTimeMS int) error {
	query := `
		INSERT INTO proxy_performance (proxy_id, success_count, failure_count, total_requests, avg_response_time_ms, last_used_at, created_at, updated_at)
		VALUES ($1, $2, $3, 1, $4, $5, $6, $7)
		ON CONFLICT (proxy_id) DO UPDATE 
		SET 
			success_count = proxy_performance.success_count + $2,
			failure_count = proxy_performance.failure_count + $3,
			total_requests = proxy_performance.total_requests + 1,
			avg_response_time_ms = (proxy_performance.avg_response_time_ms * proxy_performance.total_requests + $4) / (proxy_performance.total_requests + 1),
			last_used_at = $5,
			updated_at = $7
	`

	successCount := 0
	failureCount := 0
	if success {
		successCount = 1
	} else {
		failureCount = 1
	}

	now := time.Now()
	_, err := p.db.ExecContext(ctx, query,
		proxyID, successCount, failureCount, responseTimeMS, now, now, now,
	)

	if err != nil {
		return fmt.Errorf("failed to update proxy performance: %w", err)
	}

	return nil
}

// Error logging

// LogError logs an error to the database
func (p *PostgresDB) LogError(ctx context.Context, domainID, submissionID *int64, errorType, errorMsg, stackTrace string, contextData map[string]interface{}) error {
	query := `
		INSERT INTO errors (domain_id, submission_id, error_type, error_message, stack_trace, context, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`

	var domainIDVal, submissionIDVal sql.NullInt64
	if domainID != nil {
		domainIDVal = sql.NullInt64{Int64: *domainID, Valid: true}
	}
	if submissionID != nil {
		submissionIDVal = sql.NullInt64{Int64: *submissionID, Valid: true}
	}

	contextJSON, _ := json.Marshal(contextData)

	_, err := p.db.ExecContext(ctx, query,
		domainIDVal, submissionIDVal, errorType, errorMsg, stackTrace, contextJSON, time.Now(),
	)

	if err != nil {
		p.logger.Error("failed to log error to database", zap.Error(err))
		return fmt.Errorf("failed to log error: %w", err)
	}

	return nil
}

// Close closes the database connection
func (p *PostgresDB) Close() error {
	if err := p.db.Close(); err != nil {
		return fmt.Errorf("failed to close database: %w", err)
	}
	p.logger.Info("PostgreSQL connection closed")
	return nil
}

// Health checks the database connection health
func (p *PostgresDB) Health(ctx context.Context) error {
	if err := p.db.PingContext(ctx); err != nil {
		return fmt.Errorf("database health check failed: %w", err)
	}
	return nil
}
