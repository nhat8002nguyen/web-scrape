package main

import (
	"bufio"
	"context"
	"encoding/csv"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/nhatnguyen/autonomous-form-submission/config"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/kafka"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/models"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/storage"
	"go.uber.org/zap"
)

func main() {
	// Parse command line flags
	configPath := flag.String("config", "config/config.yaml", "Path to config file")
	domainsFile := flag.String("file", "domains.csv", "Path to domains CSV file")
	batchSize := flag.Int("batch", 100, "Batch size for publishing")
	flag.Parse()

	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	logger.Info("Starting domain loader", 
		zap.String("config", *configPath),
		zap.String("domains_file", *domainsFile),
		zap.Int("batch_size", *batchSize),
	)

	// Load configuration
	cfg, err := config.Load(*configPath)
	if err != nil {
		logger.Fatal("Failed to load config", zap.Error(err))
	}

	// Initialize Kafka producer
	producer, err := kafka.NewProducer(kafka.ProducerConfig{
		Brokers: cfg.Kafka.Brokers,
		Logger:  logger,
	})
	if err != nil {
		logger.Fatal("Failed to create Kafka producer", zap.Error(err))
	}
	defer producer.Close()

	// Initialize PostgreSQL
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

	// Load domains from file
	domains, err := loadDomains(*domainsFile)
	if err != nil {
		logger.Fatal("Failed to load domains", zap.Error(err))
	}

	logger.Info("Domains loaded", zap.Int("count", len(domains)))

	// Process domains
	ctx := context.Background()
	totalPublished := 0
	totalSkipped := 0
	startTime := time.Now()

	for i := 0; i < len(domains); i += *batchSize {
		end := i + *batchSize
		if end > len(domains) {
			end = len(domains)
		}

		batch := domains[i:end]
		published, skipped := processBatch(ctx, batch, producer, db, redisCache, cfg, logger)
		
		totalPublished += published
		totalSkipped += skipped

		logger.Info("Batch processed",
			zap.Int("batch", i / *batchSize + 1),
			zap.Int("published", published),
			zap.Int("skipped", skipped),
			zap.Int("total_published", totalPublished),
			zap.Int("total_skipped", totalSkipped),
		)
	}

	duration := time.Since(startTime)
	
	// Update Redis progress
	redisCache.SetProgress(ctx, "domains:total", int64(len(domains)))
	redisCache.SetProgress(ctx, "domains:loaded", int64(totalPublished))

	logger.Info("Domain loading complete",
		zap.Int("total_domains", len(domains)),
		zap.Int("published", totalPublished),
		zap.Int("skipped", totalSkipped),
		zap.Duration("duration", duration),
	)
}

func loadDomains(filePath string) ([]string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()

	domains := make([]string, 0)
	
	// Detect file format
	if strings.HasSuffix(filePath, ".csv") {
		reader := csv.NewReader(file)
		
		// Skip header if exists
		reader.Read()
		
		for {
			record, err := reader.Read()
			if err == io.EOF {
				break
			}
			if err != nil {
				return nil, fmt.Errorf("failed to read CSV: %w", err)
			}
			
			if len(record) > 0 && record[0] != "" {
				domain := strings.TrimSpace(record[0])
				if !strings.HasPrefix(domain, "http") {
					domain = "https://" + domain
				}
				domains = append(domains, domain)
			}
		}
	} else {
		// Plain text file, one domain per line
		scanner := bufio.NewScanner(file)
		for scanner.Scan() {
			domain := strings.TrimSpace(scanner.Text())
			if domain != "" && !strings.HasPrefix(domain, "#") {
				if !strings.HasPrefix(domain, "http") {
					domain = "https://" + domain
				}
				domains = append(domains, domain)
			}
		}
		
		if err := scanner.Err(); err != nil {
			return nil, fmt.Errorf("failed to read file: %w", err)
		}
	}

	return domains, nil
}

func processBatch(
	ctx context.Context,
	domains []string,
	producer *kafka.Producer,
	db *storage.PostgresDB,
	cache *storage.RedisCache,
	cfg *config.Config,
	logger *zap.Logger,
) (int, int) {
	published := 0
	skipped := 0

	for _, domainURL := range domains {
		// Check if already processed (deduplication)
		processed, err := cache.IsDomainProcessed(ctx, domainURL)
		if err != nil {
			logger.Warn("Failed to check domain processed status",
				zap.String("domain", domainURL),
				zap.Error(err),
			)
		}
		
		if processed {
			logger.Debug("Domain already processed, skipping",
				zap.String("domain", domainURL),
			)
			skipped++
			continue
		}

		// Create domain record in database
		domain, err := db.CreateDomain(ctx, domainURL)
		if err != nil {
			logger.Error("Failed to create domain record",
				zap.String("domain", domainURL),
				zap.Error(err),
			)
			skipped++
			continue
		}

		// Create discovery task
		task := models.DiscoveryTask{
			DomainID:  domain.ID,
			URL:       domainURL,
			Depth:     0,
			CreatedAt: time.Now(),
		}

		// Publish to Kafka
		if err := producer.PublishMessage(cfg.Kafka.Topics.Discovery, domainURL, task); err != nil {
			logger.Error("Failed to publish discovery task",
				zap.String("domain", domainURL),
				zap.Error(err),
			)
			skipped++
			continue
		}

		published++
	}

	return published, skipped
}
