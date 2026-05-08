package config

import (
	"fmt"
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Kafka      KafkaConfig      `yaml:"kafka"`
	Redis      RedisConfig      `yaml:"redis"`
	Postgres   PostgresConfig   `yaml:"postgres"`
	Captcha    CaptchaConfig    `yaml:"captcha"`
	Proxy      ProxyConfig      `yaml:"proxy"`
	Workers    WorkersConfig    `yaml:"workers"`
	Budget     BudgetConfig     `yaml:"budget"`
	Browser    BrowserConfig    `yaml:"browser"`
	Discovery  DiscoveryConfig  `yaml:"discovery"`
	Submission SubmissionConfig `yaml:"submission"`
	Monitoring MonitoringConfig `yaml:"monitoring"`
	Templates  []Template       `yaml:"templates"`
}

type KafkaConfig struct {
	Brokers        []string          `yaml:"brokers"`
	Topics         TopicsConfig      `yaml:"topics"`
	ConsumerGroup  string            `yaml:"consumer_group"`
	PartitionCount PartitionConfig   `yaml:"partition_count"`
}

type TopicsConfig struct {
	Discovery  string `yaml:"discovery"`
	Submission string `yaml:"submission"`
}

type PartitionConfig struct {
	Discovery  int `yaml:"discovery"`
	Submission int `yaml:"submission"`
}

type RedisConfig struct {
	Host     string `yaml:"host"`
	Password string `yaml:"password"`
	DB       int    `yaml:"db"`
	TTLDays  int    `yaml:"ttl_days"`
	PoolSize int    `yaml:"pool_size"`
}

type PostgresConfig struct {
	Host           string `yaml:"host"`
	Port           int    `yaml:"port"`
	Database       string `yaml:"database"`
	User           string `yaml:"user"`
	Password       string `yaml:"password"`
	MaxConnections int    `yaml:"max_connections"`
}

type CaptchaConfig struct {
	Provider       string `yaml:"provider"`
	APIKey         string `yaml:"api_key"`
	TimeoutSeconds int    `yaml:"timeout_seconds"`
	MaxRetries     int    `yaml:"max_retries"`
	SolveDelayMS   int    `yaml:"solve_delay_ms"`
}

type ProxyConfig struct {
	Provider                   string `yaml:"provider"`
	APIKey                     string `yaml:"api_key"`
	RotationStrategy           string `yaml:"rotation_strategy"`
	FallbackFreeProxies        bool   `yaml:"fallback_free_proxies"`
	EnableDirect               bool   `yaml:"enable_direct"`
	HealthCheckIntervalSeconds int    `yaml:"health_check_interval_seconds"`
	MaxFailuresBeforeRemove    int    `yaml:"max_failures_before_remove"`
}

type WorkersConfig struct {
	DiscoveryCount         int `yaml:"discovery_count"`
	SubmissionCount        int `yaml:"submission_count"`
	ConcurrentBrowsers     int `yaml:"concurrent_browsers"`
	MaxTasksPerWorker      int `yaml:"max_tasks_per_worker"`
	RestartIntervalMinutes int `yaml:"restart_interval_minutes"`
}

type BudgetConfig struct {
	CaptchaLimitUSD        float64  `yaml:"captcha_limit_usd"`
	CaptchaSolveTypes      []string `yaml:"captcha_solve_types"`
	SkipOnBudgetExceeded   bool     `yaml:"skip_on_budget_exceeded"`
	AlertThresholdUSD      float64  `yaml:"alert_threshold_usd"`
}

type BrowserConfig struct {
	Headless               bool   `yaml:"headless"`
	DisableGPU             bool   `yaml:"disable_gpu"`
	WindowSize             string `yaml:"window_size"`
	UserAgent              string `yaml:"user_agent"`
	TimeoutSeconds         int    `yaml:"timeout_seconds"`
	PageLoadTimeoutSeconds int    `yaml:"page_load_timeout_seconds"`
	IdleTimeoutSeconds     int    `yaml:"idle_timeout_seconds"`
}

type DiscoveryConfig struct {
	MaxDepth              int      `yaml:"max_depth"`
	MaxPagesPerDomain     int      `yaml:"max_pages_per_domain"`
	ContactPathPatterns   []string `yaml:"contact_path_patterns"`
}

type SubmissionConfig struct {
	VerifySuccessTimeoutSeconds int  `yaml:"verify_success_timeout_seconds"`
	ScreenshotOnFailure         bool `yaml:"screenshot_on_failure"`
	MaxRetries                  int  `yaml:"max_retries"`
	RetryDelaySeconds           int  `yaml:"retry_delay_seconds"`
}

type MonitoringConfig struct {
	PrometheusPort int    `yaml:"prometheus_port"`
	MetricsPort    int    `yaml:"metrics_port"`
	LogLevel       string `yaml:"log_level"`
}

type Template struct {
	Name       string `yaml:"name"`
	Email      string `yaml:"email"`
	SenderName string `yaml:"sender_name"`
	Company    string `yaml:"company"`
	Phone      string `yaml:"phone"`
	Subject    string `yaml:"subject"`
	Message    string `yaml:"message"`
}

func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	// Expand environment variables
	configStr := os.ExpandEnv(string(data))

	var cfg Config
	if err := yaml.Unmarshal([]byte(configStr), &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	// Validate required fields
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid config: %w", err)
	}

	return &cfg, nil
}

func (c *Config) Validate() error {
	if len(c.Kafka.Brokers) == 0 {
		return fmt.Errorf("kafka brokers not configured")
	}
	if c.Redis.Host == "" {
		return fmt.Errorf("redis host not configured")
	}
	if c.Postgres.Host == "" {
		return fmt.Errorf("postgres host not configured")
	}
	// Only require CAPTCHA API key if budget is set (> 0)
	if c.Budget.CaptchaLimitUSD > 0 {
		if c.Captcha.APIKey == "" || strings.Contains(c.Captcha.APIKey, "${") {
			return fmt.Errorf("captcha API key not configured but budget is set to $%.2f", c.Budget.CaptchaLimitUSD)
		}
	}
	if len(c.Templates) == 0 {
		return fmt.Errorf("no templates configured")
	}
	return nil
}

func (c *Config) GetPostgresConnectionString() string {
	return fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		c.Postgres.Host,
		c.Postgres.Port,
		c.Postgres.User,
		c.Postgres.Password,
		c.Postgres.Database,
	)
}
