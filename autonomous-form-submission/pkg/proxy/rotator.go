package proxy

import (
	"fmt"
	"math/rand"
	"net/http"
	"net/url"
	"sync"
	"time"

	"go.uber.org/zap"
)

// Proxy represents a proxy server
type Proxy struct {
	ID           string
	Host         string
	Port         int
	Username     string
	Password     string
	Type         ProxyType
	Failures     int
	LastUsed     time.Time
	ResponseTime int // milliseconds
	Active       bool
}

// ProxyType represents the type of proxy
type ProxyType string

const (
	ProxyTypeHTTP    ProxyType = "http"
	ProxyTypeSOCKS5  ProxyType = "socks5"
	ProxyTypeDirect  ProxyType = "direct"
)

// Rotator manages a pool of proxies with rotation and health checking
type Rotator struct {
	proxies             []*Proxy
	currentIndex        int
	maxFailures         int
	healthCheckInterval time.Duration
	enableDirect        bool
	mu                  sync.RWMutex
	logger              *zap.Logger
	stopCh              chan struct{}
}

// RotatorConfig contains proxy rotator configuration
type RotatorConfig struct {
	ProxyList            []string // Format: "http://username:password@host:port" or "host:port"
	MaxFailures          int
	HealthCheckInterval  time.Duration
	EnableDirect         bool
	FallbackFreeProxies  bool
	Logger               *zap.Logger
}

// NewRotator creates a new proxy rotator
func NewRotator(config RotatorConfig) (*Rotator, error) {
	if config.MaxFailures == 0 {
		config.MaxFailures = 3
	}
	if config.HealthCheckInterval == 0 {
		config.HealthCheckInterval = 5 * time.Minute
	}

	rotator := &Rotator{
		proxies:             make([]*Proxy, 0),
		currentIndex:        0,
		maxFailures:         config.MaxFailures,
		healthCheckInterval: config.HealthCheckInterval,
		enableDirect:        config.EnableDirect,
		logger:              config.Logger,
		stopCh:              make(chan struct{}),
	}

	// Parse and add proxies
	for _, proxyStr := range config.ProxyList {
		proxy, err := parseProxy(proxyStr)
		if err != nil {
			config.Logger.Warn("failed to parse proxy, skipping",
				zap.String("proxy", proxyStr),
				zap.Error(err),
			)
			continue
		}
		rotator.proxies = append(rotator.proxies, proxy)
	}

	// Add direct connection if enabled
	if config.EnableDirect {
		rotator.proxies = append(rotator.proxies, &Proxy{
			ID:     "direct",
			Type:   ProxyTypeDirect,
			Active: true,
		})
	}

	if len(rotator.proxies) == 0 {
		return nil, fmt.Errorf("no valid proxies configured")
	}

	config.Logger.Info("proxy rotator initialized",
		zap.Int("proxy_count", len(rotator.proxies)),
		zap.Bool("enable_direct", config.EnableDirect),
	)

	// Start health check routine
	go rotator.healthCheckRoutine()

	return rotator, nil
}

// GetNext returns the next proxy in rotation
func (r *Rotator) GetNext() *Proxy {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Try to find an active proxy starting from current index
	attempts := 0
	maxAttempts := len(r.proxies)

	for attempts < maxAttempts {
		proxy := r.proxies[r.currentIndex]
		r.currentIndex = (r.currentIndex + 1) % len(r.proxies)

		if proxy.Active && proxy.Failures < r.maxFailures {
			proxy.LastUsed = time.Now()
			r.logger.Debug("proxy selected",
				zap.String("proxy_id", proxy.ID),
				zap.Int("failures", proxy.Failures),
			)
			return proxy
		}

		attempts++
	}

	// If no active proxy found, try to use direct connection
	if r.enableDirect {
		for _, proxy := range r.proxies {
			if proxy.Type == ProxyTypeDirect {
				r.logger.Warn("all proxies exhausted, using direct connection")
				return proxy
			}
		}
	}

	// Last resort: return first proxy even if it has failures
	r.logger.Warn("no healthy proxies available, returning first proxy")
	return r.proxies[0]
}

// GetStickyProxy returns a specific proxy by ID for sticky sessions
func (r *Rotator) GetStickyProxy(proxyID string) *Proxy {
	r.mu.RLock()
	defer r.mu.RUnlock()

	for _, proxy := range r.proxies {
		if proxy.ID == proxyID {
			return proxy
		}
	}

	return nil
}

// RecordSuccess records a successful proxy usage
func (r *Rotator) RecordSuccess(proxyID string, responseTime int) {
	r.mu.Lock()
	defer r.mu.Unlock()

	for _, proxy := range r.proxies {
		if proxy.ID == proxyID {
			proxy.Failures = 0
			proxy.ResponseTime = responseTime
			proxy.Active = true
			r.logger.Debug("proxy success recorded",
				zap.String("proxy_id", proxyID),
				zap.Int("response_time_ms", responseTime),
			)
			return
		}
	}
}

// RecordFailure records a proxy failure
func (r *Rotator) RecordFailure(proxyID string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	for _, proxy := range r.proxies {
		if proxy.ID == proxyID {
			proxy.Failures++
			
			if proxy.Failures >= r.maxFailures {
				proxy.Active = false
				r.logger.Warn("proxy deactivated due to failures",
					zap.String("proxy_id", proxyID),
					zap.Int("failures", proxy.Failures),
				)
			} else {
				r.logger.Debug("proxy failure recorded",
					zap.String("proxy_id", proxyID),
					zap.Int("failures", proxy.Failures),
				)
			}
			return
		}
	}
}

// GetHTTPClient returns an HTTP client configured with the proxy
func (r *Rotator) GetHTTPClient(proxy *Proxy) (*http.Client, error) {
	if proxy.Type == ProxyTypeDirect {
		return &http.Client{
			Timeout: 30 * time.Second,
		}, nil
	}

	proxyURL, err := url.Parse(proxy.GetURL())
	if err != nil {
		return nil, fmt.Errorf("failed to parse proxy URL: %w", err)
	}

	transport := &http.Transport{
		Proxy: http.ProxyURL(proxyURL),
	}

	return &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second,
	}, nil
}

// GetURL returns the proxy URL string
func (p *Proxy) GetURL() string {
	if p.Type == ProxyTypeDirect {
		return ""
	}

	if p.Username != "" && p.Password != "" {
		return fmt.Sprintf("%s://%s:%s@%s:%d", p.Type, p.Username, p.Password, p.Host, p.Port)
	}
	return fmt.Sprintf("%s://%s:%d", p.Type, p.Host, p.Port)
}

// healthCheckRoutine periodically checks proxy health
func (r *Rotator) healthCheckRoutine() {
	ticker := time.NewTicker(r.healthCheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			r.performHealthChecks()
		case <-r.stopCh:
			return
		}
	}
}

func (r *Rotator) performHealthChecks() {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.logger.Info("performing proxy health checks")

	for _, proxy := range r.proxies {
		if proxy.Type == ProxyTypeDirect {
			continue
		}

		// Reset failures for inactive proxies to give them another chance
		if !proxy.Active && proxy.Failures >= r.maxFailures {
			proxy.Failures = 0
			proxy.Active = true
			r.logger.Info("proxy reactivated for health check",
				zap.String("proxy_id", proxy.ID),
			)
		}
	}
}

// GetStats returns proxy statistics
func (r *Rotator) GetStats() map[string]interface{} {
	r.mu.RLock()
	defer r.mu.RUnlock()

	activeCount := 0
	totalFailures := 0

	for _, proxy := range r.proxies {
		if proxy.Active {
			activeCount++
		}
		totalFailures += proxy.Failures
	}

	return map[string]interface{}{
		"total_proxies":  len(r.proxies),
		"active_proxies": activeCount,
		"total_failures": totalFailures,
	}
}

// Stop stops the proxy rotator
func (r *Rotator) Stop() {
	close(r.stopCh)
	r.logger.Info("proxy rotator stopped")
}

// parseProxy parses a proxy string into a Proxy struct
func parseProxy(proxyStr string) (*Proxy, error) {
	proxyURL, err := url.Parse(proxyStr)
	if err != nil {
		return nil, fmt.Errorf("failed to parse proxy URL: %w", err)
	}

	proxy := &Proxy{
		ID:     generateProxyID(),
		Host:   proxyURL.Hostname(),
		Active: true,
	}

	// Parse port
	if proxyURL.Port() != "" {
		fmt.Sscanf(proxyURL.Port(), "%d", &proxy.Port)
	}

	// Parse authentication
	if proxyURL.User != nil {
		proxy.Username = proxyURL.User.Username()
		proxy.Password, _ = proxyURL.User.Password()
	}

	// Determine proxy type
	switch proxyURL.Scheme {
	case "http", "https":
		proxy.Type = ProxyTypeHTTP
	case "socks5":
		proxy.Type = ProxyTypeSOCKS5
	default:
		proxy.Type = ProxyTypeHTTP
	}

	return proxy, nil
}

func generateProxyID() string {
	return fmt.Sprintf("proxy-%d-%d", time.Now().UnixNano(), rand.Intn(10000))
}

// AddFreeProxies adds free proxies from a list
func (r *Rotator) AddFreeProxies(proxyList []string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	for _, proxyStr := range proxyList {
		proxy, err := parseProxy(proxyStr)
		if err != nil {
			r.logger.Warn("failed to parse free proxy",
				zap.String("proxy", proxyStr),
				zap.Error(err),
			)
			continue
		}
		
		r.proxies = append(r.proxies, proxy)
		r.logger.Debug("free proxy added", zap.String("proxy_id", proxy.ID))
	}

	r.logger.Info("free proxies added", zap.Int("count", len(proxyList)))
}

// RemoveProxy removes a proxy by ID
func (r *Rotator) RemoveProxy(proxyID string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	for i, proxy := range r.proxies {
		if proxy.ID == proxyID {
			r.proxies = append(r.proxies[:i], r.proxies[i+1:]...)
			r.logger.Info("proxy removed", zap.String("proxy_id", proxyID))
			return
		}
	}
}
