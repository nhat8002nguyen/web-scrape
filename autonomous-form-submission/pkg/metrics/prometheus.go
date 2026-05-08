package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Metrics holds all Prometheus metrics
type Metrics struct {
	// Discovery metrics
	DiscoveryTasksProcessed prometheus.Counter
	FormsFound              prometheus.Counter
	DiscoveryDuration       prometheus.Histogram
	DiscoveryErrors         *prometheus.CounterVec

	// Submission metrics
	SubmissionsAttempted *prometheus.CounterVec
	SubmissionsSuccessful prometheus.Counter
	SubmissionsFailed *prometheus.CounterVec
	SubmissionsSkipped *prometheus.CounterVec
	SubmissionDuration prometheus.Histogram

	// CAPTCHA metrics
	CaptchaSolves      *prometheus.CounterVec
	CaptchaBudgetSpent prometheus.Gauge
	CaptchaSolveTime   prometheus.Histogram

	// Proxy metrics
	ProxyRequests *prometheus.CounterVec
	ProxyFailures *prometheus.CounterVec
	ProxyLatency  prometheus.Histogram

	// System metrics
	KafkaConsumerLag *prometheus.GaugeVec
	BrowserContexts  prometheus.Gauge
	WorkerStatus     *prometheus.GaugeVec

	// Budget metrics
	TotalCost      prometheus.Gauge
	EstimatedCost  prometheus.Gauge
}

// NewMetrics creates and registers all Prometheus metrics
func NewMetrics() *Metrics {
	return &Metrics{
		// Discovery metrics
		DiscoveryTasksProcessed: promauto.NewCounter(prometheus.CounterOpts{
			Name: "discovery_tasks_processed_total",
			Help: "Total number of discovery tasks processed",
		}),
		FormsFound: promauto.NewCounter(prometheus.CounterOpts{
			Name: "forms_found_total",
			Help: "Total number of contact forms found",
		}),
		DiscoveryDuration: promauto.NewHistogram(prometheus.HistogramOpts{
			Name:    "discovery_duration_seconds",
			Help:    "Time taken for discovery tasks",
			Buckets: prometheus.DefBuckets,
		}),
		DiscoveryErrors: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "discovery_errors_total",
			Help: "Total number of discovery errors by type",
		}, []string{"error_type"}),

		// Submission metrics
		SubmissionsAttempted: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "submissions_attempted_total",
			Help: "Total number of submission attempts",
		}, []string{"status"}),
		SubmissionsSuccessful: promauto.NewCounter(prometheus.CounterOpts{
			Name: "submissions_successful_total",
			Help: "Total number of successful submissions",
		}),
		SubmissionsFailed: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "submissions_failed_total",
			Help: "Total number of failed submissions by reason",
		}, []string{"reason"}),
		SubmissionsSkipped: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "submissions_skipped_total",
			Help: "Total number of skipped submissions by reason",
		}, []string{"reason"}),
		SubmissionDuration: promauto.NewHistogram(prometheus.HistogramOpts{
			Name:    "submission_duration_seconds",
			Help:    "Time taken for form submissions",
			Buckets: []float64{5, 10, 20, 30, 45, 60, 90, 120, 180},
		}),

		// CAPTCHA metrics
		CaptchaSolves: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "captcha_solves_total",
			Help: "Total number of CAPTCHA solve attempts by type and result",
		}, []string{"type", "success"}),
		CaptchaBudgetSpent: promauto.NewGauge(prometheus.GaugeOpts{
			Name: "captcha_budget_spent_usd",
			Help: "Total CAPTCHA budget spent in USD",
		}),
		CaptchaSolveTime: promauto.NewHistogram(prometheus.HistogramOpts{
			Name:    "captcha_solve_time_seconds",
			Help:    "Time taken to solve CAPTCHAs",
			Buckets: []float64{1, 2, 3, 5, 10, 15, 20, 30},
		}),

		// Proxy metrics
		ProxyRequests: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "proxy_requests_total",
			Help: "Total number of requests by proxy and status",
		}, []string{"proxy_id", "status"}),
		ProxyFailures: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "proxy_failures_total",
			Help: "Total number of proxy failures by type",
		}, []string{"proxy_id", "failure_type"}),
		ProxyLatency: promauto.NewHistogram(prometheus.HistogramOpts{
			Name:    "proxy_latency_seconds",
			Help:    "Proxy response time",
			Buckets: []float64{0.1, 0.5, 1, 2, 3, 5, 10},
		}),

		// System metrics
		KafkaConsumerLag: promauto.NewGaugeVec(prometheus.GaugeOpts{
			Name: "kafka_consumer_lag",
			Help: "Kafka consumer lag by topic and partition",
		}, []string{"topic", "partition"}),
		BrowserContexts: promauto.NewGauge(prometheus.GaugeOpts{
			Name: "browser_contexts_active",
			Help: "Number of active browser contexts",
		}),
		WorkerStatus: promauto.NewGaugeVec(prometheus.GaugeOpts{
			Name: "worker_status",
			Help: "Worker status (1=active, 0=idle)",
		}, []string{"worker_id", "type"}),

		// Budget metrics
		TotalCost: promauto.NewGauge(prometheus.GaugeOpts{
			Name: "total_cost_usd",
			Help: "Total cost in USD (CAPTCHA + proxy)",
		}),
		EstimatedCost: promauto.NewGauge(prometheus.GaugeOpts{
			Name: "estimated_total_cost_usd",
			Help: "Estimated total cost to complete all domains",
		}),
	}
}

// RecordDiscoveryTask records a discovery task completion
func (m *Metrics) RecordDiscoveryTask(duration float64) {
	m.DiscoveryTasksProcessed.Inc()
	m.DiscoveryDuration.Observe(duration)
}

// RecordFormFound records a found contact form
func (m *Metrics) RecordFormFound() {
	m.FormsFound.Inc()
}

// RecordDiscoveryError records a discovery error
func (m *Metrics) RecordDiscoveryError(errorType string) {
	m.DiscoveryErrors.WithLabelValues(errorType).Inc()
}

// RecordSubmissionAttempt records a submission attempt
func (m *Metrics) RecordSubmissionAttempt(status string) {
	m.SubmissionsAttempted.WithLabelValues(status).Inc()
}

// RecordSubmissionSuccess records a successful submission
func (m *Metrics) RecordSubmissionSuccess(duration float64) {
	m.SubmissionsSuccessful.Inc()
	m.SubmissionDuration.Observe(duration)
}

// RecordSubmissionFailure records a failed submission
func (m *Metrics) RecordSubmissionFailure(reason string, duration float64) {
	m.SubmissionsFailed.WithLabelValues(reason).Inc()
	m.SubmissionDuration.Observe(duration)
}

// RecordSubmissionSkipped records a skipped submission
func (m *Metrics) RecordSubmissionSkipped(reason string) {
	m.SubmissionsSkipped.WithLabelValues(reason).Inc()
}

// RecordCaptchaSolve records a CAPTCHA solve attempt
func (m *Metrics) RecordCaptchaSolve(captchaType string, success bool, duration float64, cost float64) {
	successStr := "false"
	if success {
		successStr = "true"
	}
	m.CaptchaSolves.WithLabelValues(captchaType, successStr).Inc()
	m.CaptchaSolveTime.Observe(duration)
	
	if success {
		m.CaptchaBudgetSpent.Add(cost)
		m.TotalCost.Add(cost)
	}
}

// RecordProxyRequest records a proxy request
func (m *Metrics) RecordProxyRequest(proxyID string, status string, latency float64) {
	m.ProxyRequests.WithLabelValues(proxyID, status).Inc()
	m.ProxyLatency.Observe(latency)
}

// RecordProxyFailure records a proxy failure
func (m *Metrics) RecordProxyFailure(proxyID string, failureType string) {
	m.ProxyFailures.WithLabelValues(proxyID, failureType).Inc()
}

// SetKafkaConsumerLag sets the Kafka consumer lag
func (m *Metrics) SetKafkaConsumerLag(topic string, partition int32, lag int64) {
	m.KafkaConsumerLag.WithLabelValues(topic, string(rune(partition))).Set(float64(lag))
}

// SetBrowserContexts sets the number of active browser contexts
func (m *Metrics) SetBrowserContexts(count int) {
	m.BrowserContexts.Set(float64(count))
}

// SetWorkerStatus sets the worker status
func (m *Metrics) SetWorkerStatus(workerID string, workerType string, active bool) {
	status := 0.0
	if active {
		status = 1.0
	}
	m.WorkerStatus.WithLabelValues(workerID, workerType).Set(status)
}

// UpdateTotalCost updates the total cost
func (m *Metrics) UpdateTotalCost(captchaCost float64, proxyCost float64) {
	m.TotalCost.Set(captchaCost + proxyCost)
}

// UpdateEstimatedCost updates the estimated total cost
func (m *Metrics) UpdateEstimatedCost(estimate float64) {
	m.EstimatedCost.Set(estimate)
}
