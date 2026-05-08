package models

import "time"

type SubmissionStatus string

const (
	SubmissionStatusPending      SubmissionStatus = "pending"
	SubmissionStatusProcessing   SubmissionStatus = "processing"
	SubmissionStatusSuccess      SubmissionStatus = "success"
	SubmissionStatusFailed       SubmissionStatus = "failed"
	SubmissionStatusCaptchaFailed SubmissionStatus = "captcha_failed"
	SubmissionStatusSkipped      SubmissionStatus = "skipped"
)

type SubmissionResult struct {
	ID              int64            `json:"id"`
	DomainID        int64            `json:"domain_id"`
	FormURL         string           `json:"form_url"`
	Status          SubmissionStatus `json:"status"`
	SubmittedAt     time.Time        `json:"submitted_at"`
	CompletedAt     *time.Time       `json:"completed_at,omitempty"`
	Duration        int              `json:"duration_ms"`
	HadCaptcha      bool             `json:"had_captcha"`
	CaptchaSolved   bool             `json:"captcha_solved"`
	CaptchaType     string           `json:"captcha_type,omitempty"`
	CaptchaCost     float64          `json:"captcha_cost"`
	ProxyUsed       string           `json:"proxy_used,omitempty"`
	ErrorMessage    string           `json:"error_message,omitempty"`
	ScreenshotPath  string           `json:"screenshot_path,omitempty"`
	SuccessIndicator string          `json:"success_indicator,omitempty"`
	ResponseURL     string           `json:"response_url,omitempty"`
	Attempts        int              `json:"attempts"`
	Template        string           `json:"template"`
	UserAgent       string           `json:"user_agent"`
}

type SubmissionTask struct {
	DomainID    int64        `json:"domain_id"`
	FormURL     string       `json:"form_url"`
	Form        ContactForm  `json:"form"`
	Template    string       `json:"template"`
	Priority    int          `json:"priority"`
	CreatedAt   time.Time    `json:"created_at"`
}

type SubmissionMetrics struct {
	TotalAttempted   int64   `json:"total_attempted"`
	TotalSuccess     int64   `json:"total_success"`
	TotalFailed      int64   `json:"total_failed"`
	TotalSkipped     int64   `json:"total_skipped"`
	SuccessRate      float64 `json:"success_rate"`
	CaptchasSolved   int64   `json:"captchas_solved"`
	CaptchasFailed   int64   `json:"captchas_failed"`
	TotalCaptchaCost float64 `json:"total_captcha_cost"`
	AverageDuration  int     `json:"average_duration_ms"`
	ProxySuccessRate float64 `json:"proxy_success_rate"`
}
