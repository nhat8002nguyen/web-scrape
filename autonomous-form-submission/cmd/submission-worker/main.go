package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/chromedp/chromedp"
	"github.com/nhatnguyen/autonomous-form-submission/config"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/browser"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/captcha"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/kafka"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/metrics"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/models"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/proxy"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/storage"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
	"net/http"
)

type SubmissionWorker struct {
	config          *config.Config
	db              *storage.PostgresDB
	cache           *storage.RedisCache
	browserPool     *browser.ContextPool
	captchaSolver   *captcha.Solver
	captchaDetector *captcha.Detector
	proxyRotator    *proxy.Rotator
	metrics         *metrics.Metrics
	logger          *zap.Logger
}

func main() {
	configPath := flag.String("config", "config/config.yaml", "Path to config file")
	metricsPort := flag.Int("metrics-port", 0, "Metrics server port (0 to disable)")
	flag.Parse()

	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	logger.Info("Starting submission worker", zap.String("config", *configPath))

	// Load configuration
	cfg, err := config.Load(*configPath)
	if err != nil {
		logger.Fatal("Failed to load config", zap.Error(err))
	}

	// Initialize metrics
	m := metrics.NewMetrics()

	// Start metrics server if port is specified
	if *metricsPort > 0 {
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		go func() {
			logger.Info("Metrics server started", zap.Int("port", *metricsPort))
			if err := http.ListenAndServe(fmt.Sprintf(":%d", *metricsPort), mux); err != nil {
				logger.Warn("Metrics server failed", zap.Error(err))
			}
		}()
	} else {
		logger.Info("Metrics server disabled (no port specified)")
	}

	// Initialize database
	db, err := storage.NewPostgresDB(storage.PostgresConfig{
		ConnectionString: cfg.GetPostgresConnectionString(),
		MaxConnections:   cfg.Postgres.MaxConnections,
		Logger:           logger,
	})
	if err != nil {
		logger.Fatal("Failed to connect to PostgreSQL", zap.Error(err))
	}
	defer db.Close()

	// Initialize Redis
	redisCache, err := storage.NewRedisCache(storage.RedisConfig{
		Host:     cfg.Redis.Host,
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
		PoolSize: cfg.Redis.PoolSize,
		TTLDays:  cfg.Redis.TTLDays,
		Logger:   logger,
	})
	if err != nil {
		logger.Fatal("Failed to connect to Redis", zap.Error(err))
	}
	defer redisCache.Close()

	// Initialize browser pool with idle timeout
	var browserPool *browser.ContextPool
	if cfg.Browser.IdleTimeoutSeconds > 0 {
		browserPool, err = browser.NewContextPoolWithTimeout(
			cfg.Workers.ConcurrentBrowsers,
			cfg.Browser.Headless,
			time.Duration(cfg.Browser.IdleTimeoutSeconds)*time.Second,
			logger,
		)
	} else {
		browserPool, err = browser.NewContextPool(
			cfg.Workers.ConcurrentBrowsers,
			cfg.Browser.Headless,
			logger,
		)
	}
	if err != nil {
		logger.Fatal("Failed to create browser pool", zap.Error(err))
	}
	defer browserPool.Close()

	// Initialize CAPTCHA solver (only if budget > 0)
	var captchaSolver *captcha.Solver
	if cfg.Budget.CaptchaLimitUSD > 0 {
		var err error
		captchaSolver, err = captcha.NewSolver(captcha.SolverConfig{
			APIKey:         cfg.Captcha.APIKey,
			BudgetLimitUSD: cfg.Budget.CaptchaLimitUSD,
			SkipOnExceeded: cfg.Budget.SkipOnBudgetExceeded,
			TimeoutSeconds: cfg.Captcha.TimeoutSeconds,
		}, logger)
		if err != nil {
			logger.Fatal("Failed to create CAPTCHA solver", zap.Error(err))
		}
		logger.Info("CAPTCHA solver enabled", zap.Float64("budget_usd", cfg.Budget.CaptchaLimitUSD))
	} else {
		logger.Info("CAPTCHA solver disabled (budget is $0)")
	}

	// Initialize proxy rotator (stub implementation for budget mode)
	proxyRotator, err := proxy.NewRotator(proxy.RotatorConfig{
		ProxyList:           []string{}, // Will be populated from config or API
		MaxFailures:         cfg.Proxy.MaxFailuresBeforeRemove,
		HealthCheckInterval: time.Duration(cfg.Proxy.HealthCheckIntervalSeconds) * time.Second,
		EnableDirect:        cfg.Proxy.EnableDirect,
		FallbackFreeProxies: cfg.Proxy.FallbackFreeProxies,
		Logger:              logger,
	})
	if err != nil {
		logger.Fatal("Failed to create proxy rotator", zap.Error(err))
	}

	// Create worker
	worker := &SubmissionWorker{
		config:          cfg,
		db:              db,
		cache:           redisCache,
		browserPool:     browserPool,
		captchaSolver:   captchaSolver,
		captchaDetector: captcha.NewDetector(),
		proxyRotator:    proxyRotator,
		metrics:         m,
		logger:          logger,
	}

	// Initialize Kafka consumer
	consumer, err := kafka.NewConsumer(kafka.ConsumerConfig{
		Brokers:       cfg.Kafka.Brokers,
		GroupID:       cfg.Kafka.ConsumerGroup + "-submission",
		Topics:        []string{cfg.Kafka.Topics.Submission},
		Handler:       worker.handleSubmissionTask,
		Logger:        logger,
		RetryAttempts: cfg.Submission.MaxRetries,
		RetryDelay:    time.Duration(cfg.Submission.RetryDelaySeconds) * time.Second,
	})
	if err != nil {
		logger.Fatal("Failed to create Kafka consumer", zap.Error(err))
	}

	// Start consumer
	ctx := context.Background()
	if err := consumer.Start(ctx); err != nil {
		logger.Fatal("Failed to start consumer", zap.Error(err))
	}

	logger.Info("Submission worker started, waiting for tasks")

	// Wait for interrupt signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	logger.Info("Shutting down submission worker")
	consumer.Stop()
}

func (w *SubmissionWorker) handleSubmissionTask(ctx context.Context, message []byte) error {
	startTime := time.Now()

	var task models.SubmissionTask
	if err := kafka.UnmarshalMessage(message, &task); err != nil {
		w.logger.Error("Failed to unmarshal task", zap.Error(err))
		return err
	}

	w.logger.Info("Processing submission task",
		zap.Int64("domain_id", task.DomainID),
		zap.String("form_url", task.FormURL),
	)

	// Check CAPTCHA budget
	if task.Form.HasCaptcha {
		currentSpend := w.captchaSolver.GetCurrentSpend()
		if currentSpend >= w.config.Budget.CaptchaLimitUSD {
			w.logger.Warn("CAPTCHA budget exceeded, skipping",
				zap.Float64("spent", currentSpend),
				zap.Float64("limit", w.config.Budget.CaptchaLimitUSD),
			)
			w.metrics.RecordSubmissionSkipped("budget_exceeded")
			w.cache.IncrementProgress(ctx, "submissions:skipped", 1)
			return nil
		}
	}

	// Acquire browser context
	browserCtx := w.browserPool.Acquire()
	defer w.browserPool.Release(browserCtx)

	// Get proxy
	selectedProxy := w.proxyRotator.GetNext()

	// Perform submission
	result := w.submitForm(browserCtx, task, selectedProxy)

	duration := time.Since(startTime)
	result.Duration = int(duration.Milliseconds())
	result.SubmittedAt = startTime

	// Record metrics
	switch result.Status {
	case models.SubmissionStatusSuccess:
		w.metrics.RecordSubmissionSuccess(duration.Seconds())
		w.cache.IncrementProgress(ctx, "submissions:success", 1)
	case models.SubmissionStatusSkipped:
		w.metrics.RecordSubmissionSkipped(result.ErrorMessage)
		w.cache.IncrementProgress(ctx, "submissions:skipped", 1)
	default:
		w.metrics.RecordSubmissionFailure(result.ErrorMessage, duration.Seconds())
		w.cache.IncrementProgress(ctx, "submissions:failed", 1)
	}

	// Save result to database
	if err := w.db.CreateSubmission(ctx, result); err != nil {
		w.logger.Error("Failed to save submission result", zap.Error(err))
		return err
	}

	w.logger.Info("Submission completed",
		zap.String("status", string(result.Status)),
		zap.Duration("duration", duration),
		zap.Float64("captcha_cost", result.CaptchaCost),
	)

	return nil
}

func (w *SubmissionWorker) submitForm(ctx context.Context, task models.SubmissionTask, selectedProxy *proxy.Proxy) *models.SubmissionResult {
	result := &models.SubmissionResult{
		DomainID:  task.DomainID,
		FormURL:   task.FormURL,
		Status:    models.SubmissionStatusProcessing,
		Template:  task.Template,
		UserAgent: w.config.Browser.UserAgent,
	}

	// Navigate to form page
	if err := chromedp.Run(ctx,
		chromedp.Navigate(task.FormURL),
		chromedp.Sleep(2*time.Second),
	); err != nil {
		result.Status = models.SubmissionStatusFailed
		result.ErrorMessage = fmt.Sprintf("navigation failed: %v", err)
		return result
	}

	// Detect CAPTCHA
	captchaInfo, err := w.captchaDetector.Detect(ctx)
	if err != nil {
		w.logger.Warn("CAPTCHA detection failed", zap.Error(err))
	}

	result.HadCaptcha = captchaInfo != nil && captchaInfo.Type != captcha.CaptchaTypeNone

	// Handle CAPTCHA if present
	if result.HadCaptcha {
		result.CaptchaType = string(captchaInfo.Type)

		// Skip if CAPTCHA solver is disabled (budget is $0)
		if w.captchaSolver == nil {
			w.logger.Info("CAPTCHA detected but solver disabled (budget $0), skipping",
				zap.String("type", string(captchaInfo.Type)),
			)
			result.Status = models.SubmissionStatusSkipped
			result.ErrorMessage = fmt.Sprintf("captcha detected (%s) but solver disabled", captchaInfo.Type)
			return result
		}

		// Check if CAPTCHA type is in budget
		if !w.captchaDetector.IsSupported(captchaInfo.Type, w.config.Budget.CaptchaSolveTypes) {
			w.logger.Info("CAPTCHA type not in budget, skipping",
				zap.String("type", string(captchaInfo.Type)),
			)
			result.Status = models.SubmissionStatusSkipped
			result.ErrorMessage = fmt.Sprintf("captcha type %s not in budget", captchaInfo.Type)
			return result
		}

		// Solve CAPTCHA
		solveResult, err := w.captchaSolver.Solve(ctx, captchaInfo)
		if err != nil {
			result.Status = models.SubmissionStatusCaptchaFailed
			result.ErrorMessage = fmt.Sprintf("captcha solve failed: %v", err)
			return result
		}

		result.CaptchaSolved = true
		result.CaptchaCost = solveResult.Cost

		// Inject CAPTCHA token
		injectScript := w.captchaSolver.InjectToken(solveResult.Token, captchaInfo.Type)
		if err := chromedp.Run(ctx, chromedp.Evaluate(injectScript, nil)); err != nil {
			result.Status = models.SubmissionStatusFailed
			result.ErrorMessage = fmt.Sprintf("token injection failed: %v", err)
			return result
		}

		w.logger.Info("CAPTCHA solved",
			zap.String("type", string(captchaInfo.Type)),
			zap.Float64("cost", solveResult.Cost),
		)
	}

	// Fill form fields
	template := w.getTemplate(task.Template)
	if err := w.fillForm(ctx, task.Form, template); err != nil {
		result.Status = models.SubmissionStatusFailed
		result.ErrorMessage = fmt.Sprintf("form filling failed: %v", err)
		return result
	}

	// Submit form
	// Scroll to submit button
	if err := browser.ScrollToElement(ctx, task.Form.SubmitSelector); err != nil {
		w.logger.Warn("Failed to scroll to submit button", zap.Error(err))
	}

	// Simulate human behavior before clicking
	if err := browser.SimulateHumanBehavior(ctx); err != nil {
		w.logger.Warn("Failed to simulate human behavior", zap.Error(err))
	}

	// Click submit and wait
	if err := chromedp.Run(ctx,
		chromedp.Click(task.Form.SubmitSelector),
		chromedp.Sleep(time.Duration(w.config.Submission.VerifySuccessTimeoutSeconds)*time.Second),
	); err != nil {
		result.Status = models.SubmissionStatusFailed
		result.ErrorMessage = fmt.Sprintf("form submission failed: %v", err)
		return result
	}

	// Verify success
	if success, indicator := w.verifySuccess(ctx); success {
		result.Status = models.SubmissionStatusSuccess
		result.SuccessIndicator = indicator
		now := time.Now()
		result.CompletedAt = &now

		// Get response URL
		chromedp.Run(ctx, chromedp.Location(&result.ResponseURL))
	} else {
		result.Status = models.SubmissionStatusFailed
		result.ErrorMessage = "success verification failed"
	}

	return result
}

func (w *SubmissionWorker) fillForm(ctx context.Context, form models.ContactForm, template config.Template) error {
	for _, field := range form.Fields {
		var value string

		// Map field to template value
		fieldLower := strings.ToLower(field.Name + field.Placeholder + field.Label)

		if strings.Contains(fieldLower, "email") {
			value = template.Email
		} else if strings.Contains(fieldLower, "name") && !strings.Contains(fieldLower, "company") {
			value = template.SenderName
		} else if strings.Contains(fieldLower, "company") || strings.Contains(fieldLower, "organization") {
			value = template.Company
		} else if strings.Contains(fieldLower, "phone") || strings.Contains(fieldLower, "tel") {
			value = template.Phone
		} else if strings.Contains(fieldLower, "subject") {
			value = template.Subject
		} else if strings.Contains(fieldLower, "message") || field.Type == "textarea" {
			value = template.Message
		}

		if value == "" {
			continue
		}

		// Fill field with human-like typing
		if err := browser.TypeLikeHuman(ctx, field.Selector, value); err != nil {
			w.logger.Warn("Failed to fill field",
				zap.String("selector", field.Selector),
				zap.Error(err),
			)
			continue
		}

		w.logger.Debug("Field filled", zap.String("selector", field.Selector))
	}

	return nil
}

func (w *SubmissionWorker) verifySuccess(ctx context.Context) (bool, string) {
	// Check for success indicators
	successKeywords := []string{
		"thank you",
		"thanks",
		"message sent",
		"successfully sent",
		"received your message",
		"we'll get back",
		"confirmation",
	}

	var pageText string
	chromedp.Run(ctx, chromedp.Text("body", &pageText))

	pageTextLower := strings.ToLower(pageText)

	for _, keyword := range successKeywords {
		if strings.Contains(pageTextLower, keyword) {
			w.logger.Info("Success indicator found", zap.String("keyword", keyword))
			return true, keyword
		}
	}

	// Check for URL change (redirect to success page)
	var currentURL string
	chromedp.Run(ctx, chromedp.Location(&currentURL))

	if strings.Contains(strings.ToLower(currentURL), "success") ||
		strings.Contains(strings.ToLower(currentURL), "thank") ||
		strings.Contains(strings.ToLower(currentURL), "confirmation") {
		return true, "url_redirect"
	}

	return false, ""
}

func (w *SubmissionWorker) getTemplate(name string) config.Template {
	for _, template := range w.config.Templates {
		if template.Name == name {
			return template
		}
	}

	// Return default if not found
	if len(w.config.Templates) > 0 {
		return w.config.Templates[0]
	}

	return config.Template{}
}
