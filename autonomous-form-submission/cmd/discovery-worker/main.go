package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/chromedp/chromedp"
	"github.com/nhatnguyen/autonomous-form-submission/config"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/browser"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/kafka"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/metrics"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/models"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/storage"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

type DiscoveryWorker struct {
	config      *config.Config
	db          *storage.PostgresDB
	cache       *storage.RedisCache
	producer    *kafka.Producer
	browserPool *browser.ContextPool
	detector    *browser.FormDetector
	metrics     *metrics.Metrics
	logger      *zap.Logger
}

func main() {
	configPath := flag.String("config", "config/config.yaml", "Path to config file")
	metricsPort := flag.Int("metrics-port", 8080, "Metrics server port (0 to disable)")
	flag.Parse()

	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	logger.Info("Starting discovery worker", zap.String("config", *configPath))

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

	// Initialize Kafka producer
	producer, err := kafka.NewProducer(kafka.ProducerConfig{
		Brokers: cfg.Kafka.Brokers,
		Logger:  logger,
	})
	if err != nil {
		logger.Fatal("Failed to create Kafka producer", zap.Error(err))
	}
	defer producer.Close()

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

	// Create worker
	worker := &DiscoveryWorker{
		config:      cfg,
		db:          db,
		cache:       redisCache,
		producer:    producer,
		browserPool: browserPool,
		detector:    browser.NewFormDetector(),
		metrics:     m,
		logger:      logger,
	}

	// Initialize Kafka consumer
	consumer, err := kafka.NewConsumer(kafka.ConsumerConfig{
		Brokers:       cfg.Kafka.Brokers,
		GroupID:       cfg.Kafka.ConsumerGroup + "-discovery",
		Topics:        []string{cfg.Kafka.Topics.Discovery},
		Handler:       worker.handleDiscoveryTask,
		Logger:        logger,
		RetryAttempts: 3,
		RetryDelay:    5 * time.Second,
	})
	if err != nil {
		logger.Fatal("Failed to create Kafka consumer", zap.Error(err))
	}

	// Start consumer
	ctx := context.Background()
	if err := consumer.Start(ctx); err != nil {
		logger.Fatal("Failed to start consumer", zap.Error(err))
	}

	logger.Info("Discovery worker started, waiting for tasks")

	// Wait for interrupt signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	logger.Info("Shutting down discovery worker")
	consumer.Stop()
}

func (w *DiscoveryWorker) handleDiscoveryTask(ctx context.Context, message []byte) error {
	startTime := time.Now()

	var task models.DiscoveryTask
	if err := kafka.UnmarshalMessage(message, &task); err != nil {
		w.logger.Error("Failed to unmarshal task", zap.Error(err))
		return err
	}

	w.logger.Info("Processing discovery task",
		zap.Int64("domain_id", task.DomainID),
		zap.String("url", task.URL),
	)

	// Create fresh browser context for this task (bypassing pool for now - pool contexts are broken)
	browserCtx, browserCancel := chromedp.NewContext(context.Background())
	// Don't defer cancel - we'll cancel explicitly after browser operations are done

	// Discover contact form
	contactURL, form, err := w.discoverContactForm(browserCtx, task.URL)
	
	// Cancel browser context immediately after browser operations complete
	browserCancel()

	duration := time.Since(startTime).Seconds()
	w.metrics.RecordDiscoveryTask(duration)

	if err != nil {
		w.logger.Error("Discovery failed",
			zap.String("url", task.URL),
			zap.Error(err),
		)
		w.metrics.RecordDiscoveryError("discovery_failed")
		// Use background context for database operations
		dbCtx, dbCancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer dbCancel()
		w.db.UpdateDomainStatus(dbCtx, task.DomainID, models.DomainStatusFailed, "", err)
		return nil // Don't retry
	}

	if form == nil {
		w.logger.Info("No contact form found",
			zap.String("url", task.URL),
		)
		w.metrics.RecordDiscoveryError("no_form_found")
		// Use background context for database operations
		dbCtx, dbCancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer dbCancel()
		w.db.UpdateDomainStatus(dbCtx, task.DomainID, models.DomainStatusNotFound, "", nil)
		return nil
	}

	// Form found!
	w.logger.Info("Contact form found",
		zap.String("url", task.URL),
		zap.String("contact_url", contactURL),
		zap.Int("field_count", len(form.Fields)),
	)

	w.metrics.RecordFormFound()

	// Save form to database (use background context with timeout to avoid Kafka context cancellation)
	dbCtx, dbCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer dbCancel()
	
	form.DomainID = task.DomainID
	form.URL = contactURL
	if err := w.db.SaveContactForm(dbCtx, form); err != nil {
		w.logger.Error("Failed to save form", zap.Error(err))
		return err
	}

	// Cache form
	if err := w.cache.CacheForm(dbCtx, task.URL, form); err != nil {
		w.logger.Warn("Failed to cache form", zap.Error(err))
	}

	// Update domain status
	w.db.UpdateDomainStatus(dbCtx, task.DomainID, models.DomainStatusFound, contactURL, nil)

	// Create submission task
	submissionTask := models.SubmissionTask{
		DomainID:  task.DomainID,
		FormURL:   contactURL,
		Form:      *form,
		Template:  "default",
		Priority:  1,
		CreatedAt: time.Now(),
	}

	// Publish to submission queue
	if err := w.producer.PublishMessage(w.config.Kafka.Topics.Submission, task.URL, submissionTask); err != nil {
		w.logger.Error("Failed to publish submission task", zap.Error(err))
		return err
	}

	// Mark as processed
	w.cache.MarkDomainProcessed(ctx, task.URL)
	w.cache.IncrementProgress(ctx, "domains:processed", 1)
	w.cache.IncrementProgress(ctx, "forms:found", 1)

	return nil
}

func (w *DiscoveryWorker) discoverContactForm(ctx context.Context, domainURL string) (string, *models.ContactForm, error) {
	// Try direct contact page patterns first
	contactPatterns := w.config.Discovery.ContactPathPatterns

	w.logger.Info("Starting contact form discovery",
		zap.String("domain", domainURL),
		zap.Int("patterns_to_try", len(contactPatterns)),
	)

	for i, pattern := range contactPatterns {
		contactURL := buildContactURL(domainURL, pattern)

		w.logger.Info("Checking contact page pattern",
			zap.Int("attempt", i+1),
			zap.String("pattern", pattern),
			zap.String("url", contactURL),
		)

		form, err := w.checkPageForForm(ctx, contactURL)
		if err != nil {
			w.logger.Warn("Failed to check page",
				zap.String("url", contactURL),
				zap.Error(err),
			)
			continue
		}

		if form != nil {
			w.logger.Info("✓ Contact form found on pattern page",
				zap.String("url", contactURL),
				zap.Int("fields", len(form.Fields)),
				zap.Bool("has_captcha", form.HasCaptcha),
			)
			return contactURL, form, nil
		} else {
			w.logger.Info("✗ No contact form on this page",
				zap.String("url", contactURL),
			)
		}
	}

	// If patterns didn't work, try homepage
	w.logger.Info("Checking homepage for contact form",
		zap.String("url", domainURL),
	)
	
	form, err := w.checkPageForForm(ctx, domainURL)
	if err != nil {
		w.logger.Error("Failed to check homepage",
			zap.String("url", domainURL),
			zap.Error(err),
		)
		return "", nil, err
	}

	if form != nil {
		w.logger.Info("✓ Contact form found on homepage",
			zap.String("url", domainURL),
			zap.Int("fields", len(form.Fields)),
		)
		return domainURL, form, nil
	}

	w.logger.Info("✗ No contact form found anywhere",
		zap.String("domain", domainURL),
		zap.Int("pages_checked", len(contactPatterns)+1),
	)

	return "", nil, nil
}

func (w *DiscoveryWorker) checkPageForForm(ctx context.Context, pageURL string) (*models.ContactForm, error) {
	// Navigate to page - just use a simple sleep to give pages time
	if err := chromedp.Run(ctx,
		chromedp.Navigate(pageURL),
		chromedp.Sleep(5*time.Second), // Wait 5 seconds for page to load
	); err != nil {
		return nil, fmt.Errorf("failed to navigate: %w", err)
	}

	// Detect form
	form, err := w.detector.DetectContactForm(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to detect form: %w", err)
	}

	if form == nil {
		return nil, nil
	}

	// Check for CAPTCHA
	hasCaptcha, captchaType, err := w.detector.DetectCaptcha(ctx)
	if err != nil {
		w.logger.Warn("Failed to detect CAPTCHA", zap.Error(err))
	}

	form.HasCaptcha = hasCaptcha
	form.CaptchaType = captchaType

	return form, nil
}

func buildContactURL(baseURL, pattern string) string {
	parsed, err := url.Parse(baseURL)
	if err != nil {
		return baseURL + pattern
	}

	parsed.Path = pattern
	return parsed.String()
}
