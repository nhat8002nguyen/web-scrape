package storage

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// RedisCache handles caching and deduplication
type RedisCache struct {
	client *redis.Client
	ttl    time.Duration
	logger *zap.Logger
}

// RedisConfig contains Redis configuration
type RedisConfig struct {
	Host     string
	Password string
	DB       int
	PoolSize int
	TTLDays  int
	Logger   *zap.Logger
}

// NewRedisCache creates a new Redis cache client
func NewRedisCache(config RedisConfig) (*RedisCache, error) {
	client := redis.NewClient(&redis.Options{
		Addr:     config.Host,
		Password: config.Password,
		DB:       config.DB,
		PoolSize: config.PoolSize,
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	ttl := time.Duration(config.TTLDays) * 24 * time.Hour

	config.Logger.Info("Redis cache connected",
		zap.String("host", config.Host),
		zap.Int("db", config.DB),
		zap.Duration("ttl", ttl),
	)

	return &RedisCache{
		client: client,
		ttl:    ttl,
		logger: config.Logger,
	}, nil
}

// Domain deduplication

// IsDomainProcessed checks if a domain has already been processed
func (r *RedisCache) IsDomainProcessed(ctx context.Context, domain string) (bool, error) {
	key := fmt.Sprintf("domain:processed:%s", domain)
	exists, err := r.client.Exists(ctx, key).Result()
	if err != nil {
		return false, fmt.Errorf("failed to check domain existence: %w", err)
	}
	return exists > 0, nil
}

// MarkDomainProcessed marks a domain as processed
func (r *RedisCache) MarkDomainProcessed(ctx context.Context, domain string) error {
	key := fmt.Sprintf("domain:processed:%s", domain)
	if err := r.client.Set(ctx, key, "1", r.ttl).Err(); err != nil {
		return fmt.Errorf("failed to mark domain as processed: %w", err)
	}
	r.logger.Debug("domain marked as processed", zap.String("domain", domain))
	return nil
}

// Form caching

// GetCachedForm retrieves a cached form for a domain
func (r *RedisCache) GetCachedForm(ctx context.Context, domain string) (interface{}, error) {
	key := fmt.Sprintf("form:cache:%s", domain)
	data, err := r.client.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, nil // Not found
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get cached form: %w", err)
	}

	var form interface{}
	if err := json.Unmarshal(data, &form); err != nil {
		return nil, fmt.Errorf("failed to unmarshal cached form: %w", err)
	}

	r.logger.Debug("form retrieved from cache", zap.String("domain", domain))
	return form, nil
}

// CacheForm stores a form in cache
func (r *RedisCache) CacheForm(ctx context.Context, domain string, form interface{}) error {
	key := fmt.Sprintf("form:cache:%s", domain)
	data, err := json.Marshal(form)
	if err != nil {
		return fmt.Errorf("failed to marshal form: %w", err)
	}

	if err := r.client.Set(ctx, key, data, r.ttl).Err(); err != nil {
		return fmt.Errorf("failed to cache form: %w", err)
	}

	r.logger.Debug("form cached", zap.String("domain", domain))
	return nil
}

// Progress tracking

// GetProgress retrieves progress information
func (r *RedisCache) GetProgress(ctx context.Context) (map[string]int64, error) {
	keys := []string{
		"progress:domains:total",
		"progress:domains:processed",
		"progress:forms:found",
		"progress:submissions:success",
		"progress:submissions:failed",
		"progress:submissions:skipped",
	}

	pipe := r.client.Pipeline()
	cmds := make([]*redis.StringCmd, len(keys))
	for i, key := range keys {
		cmds[i] = pipe.Get(ctx, key)
	}

	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		return nil, fmt.Errorf("failed to get progress: %w", err)
	}

	progress := make(map[string]int64)
	for i, cmd := range cmds {
		val, err := cmd.Int64()
		if err != nil {
			val = 0 // Default to 0 if key doesn't exist or conversion fails
		}
		progress[keys[i]] = val
	}

	return progress, nil
}

// IncrementProgress increments a progress counter
func (r *RedisCache) IncrementProgress(ctx context.Context, key string, delta int64) error {
	fullKey := fmt.Sprintf("progress:%s", key)
	if err := r.client.IncrBy(ctx, fullKey, delta).Err(); err != nil {
		return fmt.Errorf("failed to increment progress: %w", err)
	}
	return nil
}

// SetProgress sets a progress value
func (r *RedisCache) SetProgress(ctx context.Context, key string, value int64) error {
	fullKey := fmt.Sprintf("progress:%s", key)
	if err := r.client.Set(ctx, fullKey, value, 0).Err(); err != nil {
		return fmt.Errorf("failed to set progress: %w", err)
	}
	return nil
}

// Rate limiting

// CheckRateLimit checks if a domain can be accessed based on rate limit
func (r *RedisCache) CheckRateLimit(ctx context.Context, domain string, maxRequests int, window time.Duration) (bool, error) {
	key := fmt.Sprintf("ratelimit:%s", domain)
	
	count, err := r.client.Incr(ctx, key).Result()
	if err != nil {
		return false, fmt.Errorf("failed to increment rate limit: %w", err)
	}

	if count == 1 {
		// Set expiration on first request
		r.client.Expire(ctx, key, window)
	}

	if count > int64(maxRequests) {
		r.logger.Warn("rate limit exceeded",
			zap.String("domain", domain),
			zap.Int64("count", count),
			zap.Int("max", maxRequests),
		)
		return false, nil
	}

	return true, nil
}

// Budget tracking

// GetCaptchaBudgetSpent retrieves the current CAPTCHA budget spent
func (r *RedisCache) GetCaptchaBudgetSpent(ctx context.Context) (float64, error) {
	key := "budget:captcha:spent"
	val, err := r.client.Get(ctx, key).Float64()
	if err == redis.Nil {
		return 0, nil
	}
	if err != nil {
		return 0, fmt.Errorf("failed to get budget spent: %w", err)
	}
	return val, nil
}

// AddCaptchaBudgetSpent adds to the CAPTCHA budget spent
func (r *RedisCache) AddCaptchaBudgetSpent(ctx context.Context, amount float64) error {
	key := "budget:captcha:spent"
	if err := r.client.IncrByFloat(ctx, key, amount).Err(); err != nil {
		return fmt.Errorf("failed to add budget spent: %w", err)
	}
	return nil
}

// Proxy tracking

// RecordProxyFailure records a proxy failure
func (r *RedisCache) RecordProxyFailure(ctx context.Context, proxyID string) error {
	key := fmt.Sprintf("proxy:failures:%s", proxyID)
	count, err := r.client.Incr(ctx, key).Result()
	if err != nil {
		return fmt.Errorf("failed to record proxy failure: %w", err)
	}

	if count == 1 {
		r.client.Expire(ctx, key, 1*time.Hour)
	}

	return nil
}

// GetProxyFailures retrieves the number of failures for a proxy
func (r *RedisCache) GetProxyFailures(ctx context.Context, proxyID string) (int64, error) {
	key := fmt.Sprintf("proxy:failures:%s", proxyID)
	count, err := r.client.Get(ctx, key).Int64()
	if err == redis.Nil {
		return 0, nil
	}
	if err != nil {
		return 0, fmt.Errorf("failed to get proxy failures: %w", err)
	}
	return count, nil
}

// ResetProxyFailures resets the failure count for a proxy
func (r *RedisCache) ResetProxyFailures(ctx context.Context, proxyID string) error {
	key := fmt.Sprintf("proxy:failures:%s", proxyID)
	if err := r.client.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to reset proxy failures: %w", err)
	}
	return nil
}

// General cache operations

// Set stores a value in cache
func (r *RedisCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal value: %w", err)
	}

	if err := r.client.Set(ctx, key, data, expiration).Err(); err != nil {
		return fmt.Errorf("failed to set cache value: %w", err)
	}

	return nil
}

// Get retrieves a value from cache
func (r *RedisCache) Get(ctx context.Context, key string, dest interface{}) error {
	data, err := r.client.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return fmt.Errorf("key not found: %s", key)
	}
	if err != nil {
		return fmt.Errorf("failed to get cache value: %w", err)
	}

	if err := json.Unmarshal(data, dest); err != nil {
		return fmt.Errorf("failed to unmarshal value: %w", err)
	}

	return nil
}

// Delete removes a value from cache
func (r *RedisCache) Delete(ctx context.Context, key string) error {
	if err := r.client.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to delete cache value: %w", err)
	}
	return nil
}

// Close closes the Redis connection
func (r *RedisCache) Close() error {
	if err := r.client.Close(); err != nil {
		return fmt.Errorf("failed to close Redis connection: %w", err)
	}
	r.logger.Info("Redis connection closed")
	return nil
}

// Flush clears all data (use with caution!)
func (r *RedisCache) Flush(ctx context.Context) error {
	if err := r.client.FlushDB(ctx).Err(); err != nil {
		return fmt.Errorf("failed to flush Redis: %w", err)
	}
	r.logger.Warn("Redis database flushed")
	return nil
}

// Stats retrieves Redis statistics
func (r *RedisCache) Stats(ctx context.Context) (map[string]string, error) {
	info, err := r.client.Info(ctx, "stats").Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get Redis stats: %w", err)
	}

	stats := make(map[string]string)
	stats["info"] = info

	return stats, nil
}
