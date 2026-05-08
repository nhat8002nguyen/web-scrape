package captcha

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"go.uber.org/zap"
)

const (
	capSolverAPIURL = "https://api.capsolver.com"
)

// Solver handles CAPTCHA solving with budget tracking
type Solver struct {
	apiKey         string
	budgetLimit    float64
	currentSpend   float64
	solveCount     int64
	skipOnExceeded bool
	timeout        time.Duration
	httpClient     *http.Client
	mu             sync.RWMutex
	logger         *zap.Logger
}

// SolverConfig contains configuration for the CAPTCHA solver
type SolverConfig struct {
	APIKey         string
	BudgetLimitUSD float64
	SkipOnExceeded bool
	TimeoutSeconds int
}

// capSolverRequest represents the API request structure
type capSolverRequest struct {
	ClientKey string                 `json:"clientKey"`
	Task      map[string]interface{} `json:"task"`
}

// capSolverResponse represents the API response structure
type capSolverResponse struct {
	ErrorID          int    `json:"errorId"`
	ErrorCode        string `json:"errorCode,omitempty"`
	ErrorDescription string `json:"errorDescription,omitempty"`
	TaskID           string `json:"taskId,omitempty"`
	Status           string `json:"status,omitempty"`
	Solution         struct {
		GRecaptchaResponse string `json:"gRecaptchaResponse"`
		Token              string `json:"token"`
		UserAgent          string `json:"userAgent,omitempty"`
	} `json:"solution,omitempty"`
}

// SolveResult contains the result of a CAPTCHA solve
type SolveResult struct {
	Token      string
	UserAgent  string
	Cost       float64
	Duration   time.Duration
	SolvedAt   time.Time
	CaptchaType string
}

// NewSolver creates a new CAPTCHA solver with budget tracking
func NewSolver(config SolverConfig, logger *zap.Logger) (*Solver, error) {
	if config.APIKey == "" {
		return nil, fmt.Errorf("CapSolver API key is required")
	}

	timeout := time.Duration(config.TimeoutSeconds) * time.Second
	if timeout == 0 {
		timeout = 30 * time.Second
	}

	solver := &Solver{
		apiKey:         config.APIKey,
		budgetLimit:    config.BudgetLimitUSD,
		currentSpend:   0,
		solveCount:     0,
		skipOnExceeded: config.SkipOnExceeded,
		timeout:        timeout,
		httpClient: &http.Client{
			Timeout: timeout + 10*time.Second,
		},
		logger: logger,
	}

	logger.Info("CAPTCHA solver initialized",
		zap.Float64("budget_limit_usd", config.BudgetLimitUSD),
		zap.Bool("skip_on_exceeded", config.SkipOnExceeded))

	return solver, nil
}

// Solve attempts to solve a CAPTCHA challenge
func (s *Solver) Solve(ctx context.Context, info *CaptchaInfo) (*SolveResult, error) {
	startTime := time.Now()

	// Check if we should skip (budget exceeded)
	if s.skipOnExceeded && !s.CanAfford(info) {
		return nil, fmt.Errorf("budget exceeded: current spend $%.2f, limit $%.2f",
			s.GetCurrentSpend(), s.budgetLimit)
	}

	s.logger.Info("Solving CAPTCHA",
		zap.String("type", string(info.Type)),
		zap.String("url", info.URL),
		zap.Float64("estimated_cost", info.GetCost()))

	// Create task
	taskID, err := s.createTask(ctx, info)
	if err != nil {
		return nil, fmt.Errorf("failed to create task: %w", err)
	}

	// Poll for result
	token, userAgent, err := s.getTaskResult(ctx, taskID)
	if err != nil {
		return nil, fmt.Errorf("failed to get result: %w", err)
	}

	duration := time.Since(startTime)
	cost := info.GetCost()

	// Track spending
	s.AddSpend(cost)

	result := &SolveResult{
		Token:       token,
		UserAgent:   userAgent,
		Cost:        cost,
		Duration:    duration,
		SolvedAt:    time.Now(),
		CaptchaType: string(info.Type),
	}

	s.logger.Info("CAPTCHA solved successfully",
		zap.String("type", string(info.Type)),
		zap.Duration("duration", duration),
		zap.Float64("cost", cost),
		zap.Float64("current_spend", s.GetCurrentSpend()))

	return result, nil
}

// createTask creates a new CAPTCHA solving task
func (s *Solver) createTask(ctx context.Context, info *CaptchaInfo) (string, error) {
	task := make(map[string]interface{})

	switch info.Type {
	case CaptchaTypeReCaptchaV2, CaptchaTypeReCaptchaV2Inv:
		task["type"] = "ReCaptchaV2TaskProxyLess"
		task["websiteURL"] = info.URL
		task["websiteKey"] = info.SiteKey
		if info.IsInvisible() {
			task["isInvisible"] = true
		}

	case CaptchaTypeReCaptchaV3:
		task["type"] = "ReCaptchaV3TaskProxyLess"
		task["websiteURL"] = info.URL
		task["websiteKey"] = info.SiteKey
		task["pageAction"] = "submit"

	case CaptchaTypeHCaptcha:
		task["type"] = "HCaptchaTaskProxyLess"
		task["websiteURL"] = info.URL
		task["websiteKey"] = info.SiteKey

	case CaptchaTypeTurnstile:
		task["type"] = "TurnstileTaskProxyLess"
		task["websiteURL"] = info.URL
		task["websiteKey"] = info.SiteKey

	default:
		return "", fmt.Errorf("unsupported CAPTCHA type: %s", info.Type)
	}

	reqBody := capSolverRequest{
		ClientKey: s.apiKey,
		Task:      task,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", capSolverAPIURL+"/createTask", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response: %w", err)
	}

	var result capSolverResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return "", fmt.Errorf("failed to unmarshal response: %w", err)
	}

	if result.ErrorID != 0 {
		return "", fmt.Errorf("CapSolver API error: %s - %s", result.ErrorCode, result.ErrorDescription)
	}

	if result.TaskID == "" {
		return "", fmt.Errorf("no task ID returned")
	}

	return result.TaskID, nil
}

// getTaskResult polls for the CAPTCHA solving result
func (s *Solver) getTaskResult(ctx context.Context, taskID string) (string, string, error) {
	reqBody := map[string]string{
		"clientKey": s.apiKey,
		"taskId":    taskID,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", "", fmt.Errorf("failed to marshal request: %w", err)
	}

	// Poll for result (max 60 seconds, check every 2 seconds)
	maxAttempts := 30
	for i := 0; i < maxAttempts; i++ {
		select {
		case <-ctx.Done():
			return "", "", ctx.Err()
		case <-time.After(2 * time.Second):
			req, err := http.NewRequestWithContext(ctx, "POST", capSolverAPIURL+"/getTaskResult", bytes.NewBuffer(jsonData))
			if err != nil {
				return "", "", fmt.Errorf("failed to create request: %w", err)
			}

			req.Header.Set("Content-Type", "application/json")

			resp, err := s.httpClient.Do(req)
			if err != nil {
				s.logger.Warn("Failed to get task result, retrying", zap.Error(err))
				continue
			}

			body, err := io.ReadAll(resp.Body)
			resp.Body.Close()
			if err != nil {
				s.logger.Warn("Failed to read response, retrying", zap.Error(err))
				continue
			}

			var result capSolverResponse
			if err := json.Unmarshal(body, &result); err != nil {
				s.logger.Warn("Failed to unmarshal response, retrying", zap.Error(err))
				continue
			}

			if result.ErrorID != 0 {
				return "", "", fmt.Errorf("CapSolver API error: %s - %s", result.ErrorCode, result.ErrorDescription)
			}

			if result.Status == "ready" {
				token := result.Solution.GRecaptchaResponse
				if token == "" {
					token = result.Solution.Token
				}
				return token, result.Solution.UserAgent, nil
			}

			// Status is "processing", continue polling
		}
	}

	return "", "", fmt.Errorf("timeout waiting for CAPTCHA solution")
}

// CanAfford checks if solving this CAPTCHA would exceed the budget
func (s *Solver) CanAfford(info *CaptchaInfo) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	cost := info.GetCost()
	return (s.currentSpend + cost) <= s.budgetLimit
}

// AddSpend adds cost to the current spending
func (s *Solver) AddSpend(cost float64) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.currentSpend += cost
	s.solveCount++

	s.logger.Info("Updated CAPTCHA spending",
		zap.Float64("cost", cost),
		zap.Float64("current_spend", s.currentSpend),
		zap.Float64("budget_limit", s.budgetLimit),
		zap.Int64("solve_count", s.solveCount))
}

// GetCurrentSpend returns the current spending amount
func (s *Solver) GetCurrentSpend() float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.currentSpend
}

// GetSolveCount returns the number of CAPTCHAs solved
func (s *Solver) GetSolveCount() int64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.solveCount
}

// InjectToken injects the CAPTCHA token into the page using JavaScript
func (s *Solver) InjectToken(token string, captchaType CaptchaType) string {
	switch captchaType {
	case CaptchaTypeReCaptchaV2, CaptchaTypeReCaptchaV3:
		return fmt.Sprintf(`
			(function() {
				var textarea = document.getElementById('g-recaptcha-response');
				if (textarea) {
					textarea.innerHTML = '%s';
					textarea.value = '%s';
				}
				
				// Also try data-callback if present
				var recaptchaElement = document.querySelector('[data-callback]');
				if (recaptchaElement) {
					var callback = recaptchaElement.getAttribute('data-callback');
					if (callback && typeof window[callback] === 'function') {
						window[callback]('%s');
					}
				}
			})();
		`, token, token, token)

	case CaptchaTypeHCaptcha:
		return fmt.Sprintf(`
			(function() {
				var textarea = document.querySelector('[name="h-captcha-response"]');
				if (textarea) {
					textarea.innerHTML = '%s';
					textarea.value = '%s';
				}
			})();
		`, token, token)

	case CaptchaTypeTurnstile:
		return fmt.Sprintf(`
			(function() {
				var textarea = document.querySelector('[name="cf-turnstile-response"]');
				if (textarea) {
					textarea.innerHTML = '%s';
					textarea.value = '%s';
				}
			})();
		`, token, token)

	default:
		return ""
	}
}
