# Autonomous Form Submission System

A budget-optimized distributed system for autonomous contact form submission at scale, processing 100,000 domains with selective CAPTCHA solving.

## Overview

This system uses Golang, self-hosted Kafka, Redis, PostgreSQL, and Chromedp to automatically discover and submit contact forms across 100k domains. Designed to run on AWS EC2 Spot instances with a total budget of $50-$100.

## Cost Breakdown

- **Total: $57.50-$90** for 100k domain attempts
- AWS (1 week): $20-25 (2× t3.medium Spot instances)
- CapSolver: $30 (25k simple CAPTCHA solves)
- Proxies: $7.50-35 (Webshare.io or Smartproxy)

## Expected Results

- **Success Rate**: 60-70% (60k-70k successful submissions)
- **Processing Time**: 5-7 days
- **Cost per Success**: $0.0008-0.0010

## Architecture

```
┌─────────────────────┐
│  Domain Loader      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Kafka (Discovery)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Discovery Workers   │ → Redis Cache
│      (5x)           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Kafka (Submission)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Submission Workers  │ → CapSolver API
│      (10x)          │ → Proxy Rotator
└──────────┬──────────┘ → PostgreSQL
           │
           ▼
     [Results DB]
```

## Quick Start

### Local Development

```bash
# Initialize dependencies
go mod download

# Start infrastructure
docker-compose -f deployments/docker/docker-compose.instance1.yml up -d

# Option 1: Quick reset and reload test domains (recommended for testing)
./scripts/reset_and_reload_test_domains.sh

# Option 2: Manual steps
# Run domain loader
./scripts/load_domains.sh test-domains.csv config/config.local.yaml

# Run discovery workers (Terminal 1)
go run cmd/discovery-worker/main.go --config config/config.local.yaml

# Run submission workers (Terminal 2)
go run cmd/submission-worker/main.go --config config/config.local.yaml

# Monitor progress continuously (Terminal 3)
./scripts/monitor.sh
```

### Resetting the System

To clear all data and start fresh:

```bash
# Reset everything (PostgreSQL, Redis, Kafka topics)
./scripts/reset.sh config/config.local.yaml

# Or reset and immediately reload test domains
./scripts/reset_and_reload_test_domains.sh
```

### AWS Deployment

```bash
# Setup EC2 spot instances
cd deployments/aws/scripts
./setup-ec2.sh

# Install Docker on instances
./install-docker.sh

# Deploy services
./deploy-instance1.sh  # Kafka, Redis, PostgreSQL, Discovery
./deploy-instance2.sh  # Submission workers, Prometheus

# Upload domains
./load-domains.sh domains.csv

# Monitor progress
open http://<ELASTIC_IP>:9090  # Prometheus
```

## Configuration

Edit `config/config.yaml`:

```yaml
budget:
  captcha_limit_usd: 30
  captcha_solve_types: ["recaptcha_v2_checkbox"]
  skip_on_budget_exceeded: true

proxy:
  provider: "webshare"
  enable_direct: true
  fallback_free_proxies: true

browser:
  headless: true
  idle_timeout_seconds: 300  # Close idle browsers after 5 min (local dev only)
```

### Local Development Settings

For local development, the `config.local.yaml` includes an idle timeout feature that automatically closes browser instances when they're not in use. This prevents resource exhaustion and allows you to open Chrome manually while workers are running.

**Idle Timeout Configuration:**
- `idle_timeout_seconds: 300` - Closes idle browser contexts after 5 minutes
- `idle_timeout_seconds: 0` - Keeps browsers open indefinitely (production default)

When a browser context is closed due to idle timeout, it will be automatically recreated when needed for the next task.

## Domain List Format

CSV file with one domain per line:

```csv
domain
example.com
another-site.com
company.org
```

## Monitoring

### Local Development

```bash
# Check running workers
./scripts/check_workers.sh

# Monitor progress continuously
./scripts/monitor.sh

# List all domains with status
./scripts/list_domains.sh

# Stop all workers
./scripts/stop_workers.sh
```

### Production

- **Prometheus**: http://<instance-ip>:9090
- **Metrics Endpoint**: http://<instance-ip>:8080/metrics

Key metrics:
- `submissions_successful_total` - Total successful submissions
- `captcha_budget_spent_usd` - Current CAPTCHA spend
- `forms_found_total` - Forms discovered

## Cost Control

The system automatically:
- Stops CAPTCHA solving at $30 budget
- Switches to free proxies when paid exhausted
- Alerts on high failure rates
- Estimates completion cost in real-time

## Cleanup

```bash
# Stop all services
./teardown.sh

# Terminate EC2 instances via AWS Console
```

## Project Structure

```
autonomous-form-submission/
├── cmd/                          # Main applications
│   ├── domain-loader/           # Loads domains to Kafka
│   ├── discovery-worker/        # Finds contact forms
│   └── submission-worker/       # Submits forms
├── pkg/                          # Shared packages
│   ├── browser/                 # Chromedp automation
│   ├── captcha/                 # CAPTCHA detection/solving
│   ├── proxy/                   # Proxy rotation
│   ├── kafka/                   # Kafka client
│   ├── storage/                 # Database access
│   ├── models/                  # Data models
│   └── metrics/                 # Prometheus metrics
├── config/                       # Configuration files
├── deployments/                  # Docker & AWS deployment
├── migrations/                   # Database schemas
└── scripts/                      # Utility scripts
```

## Tech Stack

- **Language**: Go 1.21+
- **Browser**: Chromedp (headless Chrome)
- **Message Queue**: Apache Kafka
- **Cache**: Redis
- **Database**: PostgreSQL
- **Monitoring**: Prometheus
- **CAPTCHA**: CapSolver API
- **Proxies**: Webshare.io / Smartproxy

## License

MIT
