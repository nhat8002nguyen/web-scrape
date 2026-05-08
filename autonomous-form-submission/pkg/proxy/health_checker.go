package proxy

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"go.uber.org/zap"
)

// HealthChecker performs health checks on proxies
type HealthChecker struct {
	testURL string
	timeout time.Duration
	logger  *zap.Logger
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(testURL string, timeout time.Duration, logger *zap.Logger) *HealthChecker {
	if testURL == "" {
		testURL = "https://www.google.com"
	}
	if timeout == 0 {
		timeout = 10 * time.Second
	}

	return &HealthChecker{
		testURL: testURL,
		timeout: timeout,
		logger:  logger,
	}
}

// CheckProxy performs a health check on a specific proxy
func (hc *HealthChecker) CheckProxy(ctx context.Context, proxy *Proxy) (bool, int, error) {
	if proxy.Type == ProxyTypeDirect {
		return true, 0, nil
	}

	client, err := (&Rotator{}).GetHTTPClient(proxy)
	if err != nil {
		return false, 0, fmt.Errorf("failed to create HTTP client: %w", err)
	}

	startTime := time.Now()

	req, err := http.NewRequestWithContext(ctx, "GET", hc.testURL, nil)
	if err != nil {
		return false, 0, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := client.Do(req)
	responseTime := int(time.Since(startTime).Milliseconds())

	if err != nil {
		hc.logger.Debug("proxy health check failed",
			zap.String("proxy_id", proxy.ID),
			zap.Error(err),
		)
		return false, responseTime, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		hc.logger.Debug("proxy health check passed",
			zap.String("proxy_id", proxy.ID),
			zap.Int("response_time_ms", responseTime),
		)
		return true, responseTime, nil
	}

	return false, responseTime, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
}

// CheckAllProxies performs health checks on all proxies
func (hc *HealthChecker) CheckAllProxies(ctx context.Context, proxies []*Proxy) map[string]bool {
	results := make(map[string]bool)

	for _, proxy := range proxies {
		healthy, _, err := hc.CheckProxy(ctx, proxy)
		results[proxy.ID] = healthy && err == nil
	}

	return results
}

// GetProxyResponseTime measures the response time of a proxy
func (hc *HealthChecker) GetProxyResponseTime(ctx context.Context, proxy *Proxy) (int, error) {
	_, responseTime, err := hc.CheckProxy(ctx, proxy)
	return responseTime, err
}
