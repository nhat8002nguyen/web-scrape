# Deployment Guide

Complete guide for deploying the autonomous form submission system to AWS.

## Prerequisites

1. **AWS Account** with permissions to create EC2 instances, security groups, and Elastic IPs
2. **AWS CLI** installed and configured (`aws configure`)
3. **Local Tools**: ssh, rsync, bash
4. **API Keys**:
   - CapSolver API key (get from https://capsolver.com)
   - Proxy API key (optional, for Webshare.io or Smartproxy)

## Step 1: Prepare Configuration

1. Copy environment template:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys:
```bash
CAPSOLVER_API_KEY=your_capsolver_api_key_here
PROXY_API_KEY=your_proxy_api_key_here  # Optional
AWS_REGION=us-east-1
```

3. Review and adjust `config/config.yaml` if needed:
   - Budget limits
   - Worker counts
   - CAPTCHA types to solve
   - Form templates

## Step 2: Launch AWS Infrastructure

Run the setup script to create EC2 spot instances:

```bash
cd deployments/aws/scripts
./setup-ec2.sh
```

This will:
- Create a security group with necessary ports
- Generate an SSH key pair (saved as `form-submission-key.pem`)
- Launch 2× t3.medium spot instances
- Allocate an Elastic IP for monitoring access

**Expected Output:**
```
Instance 1 (Data + Discovery):
  Instance ID: i-xxxxx
  Public IP: 1.2.3.4
  SSH: ssh -i form-submission-key.pem ec2-user@1.2.3.4

Instance 2 (Submission + Monitoring):
  Instance ID: i-yyyyy
  Elastic IP: 5.6.7.8
  SSH: ssh -i form-submission-key.pem ec2-user@5.6.7.8
  Prometheus: http://5.6.7.8:9090
```

**Save these IPs:**
```bash
export INSTANCE1_IP=1.2.3.4
export INSTANCE2_IP=5.6.7.8
export KEY_FILE=form-submission-key.pem
```

## Step 3: Install Docker on Instances

Wait 2-3 minutes for instances to fully boot, then install Docker:

```bash
# On Instance 1
ssh -i $KEY_FILE ec2-user@$INSTANCE1_IP < install-docker.sh

# On Instance 2
ssh -i $KEY_FILE ec2-user@$INSTANCE2_IP < install-docker.sh
```

## Step 4: Deploy Services

### Deploy Instance 1 (Data Services + Discovery)

```bash
./deploy-instance1.sh $INSTANCE1_IP $KEY_FILE
```

This deploys:
- Apache Kafka (message queue)
- Redis (caching and deduplication)
- PostgreSQL (results storage)
- 5× Discovery Workers

**Verify deployment:**
```bash
ssh -i $KEY_FILE ec2-user@$INSTANCE1_IP "cd /opt/form-submission && docker-compose -f deployments/docker/docker-compose.instance1.yml ps"
```

### Deploy Instance 2 (Submission Workers + Monitoring)

```bash
./deploy-instance2.sh $INSTANCE2_IP $KEY_FILE $INSTANCE1_IP
```

This deploys:
- 10× Submission Workers
- Prometheus (monitoring)

**Verify deployment:**
```bash
ssh -i $KEY_FILE ec2-user@$INSTANCE2_IP "cd /opt/form-submission && docker-compose -f deployments/docker/docker-compose.instance2.yml ps"
```

## Step 5: Prepare Domain List

Create a CSV file with your 100k domains:

```csv
domain
example.com
company.com
business.org
...
```

**Format requirements:**
- First line: `domain` (header)
- One domain per line
- Optional: include `https://` prefix (will be added if missing)

## Step 6: Start Processing

### Option A: Load Domains Manually

SSH into Instance 1 and run the domain loader:

```bash
ssh -i $KEY_FILE ec2-user@$INSTANCE1_IP

cd /opt/form-submission

# Upload your domains file
# (or use scp: scp -i $KEY_FILE domains.csv ec2-user@$INSTANCE1_IP:/opt/form-submission/)

docker run --rm --network form-submission-network \
  -v /opt/form-submission:/app \
  -v /opt/form-submission/domains.csv:/data/domains.csv \
  form-submission/loader:latest
```

### Option B: Use the Load Script

```bash
# From your local machine
scp -i $KEY_FILE domains.csv ec2-user@$INSTANCE1_IP:/opt/form-submission/
ssh -i $KEY_FILE ec2-user@$INSTANCE1_IP "cd /opt/form-submission && bash scripts/load_domains.sh domains.csv"
```

## Step 7: Monitor Progress

### Access Prometheus Dashboard

Open in browser: `http://$INSTANCE2_IP:9090`

**Key Metrics to Watch:**
- `submissions_successful_total` - Total successful submissions
- `submissions_failed_total` - Failed submissions by reason
- `forms_found_total` - Contact forms discovered
- `captcha_budget_spent_usd` - Current CAPTCHA spend
- `kafka_consumer_lag` - Processing backlog

### Query Examples

**Success rate:**
```promql
rate(submissions_successful_total[5m]) / rate(submissions_attempted_total[5m])
```

**Forms found per hour:**
```promql
increase(forms_found_total[1h])
```

**CAPTCHA costs:**
```promql
captcha_budget_spent_usd
```

### SSH Monitoring

Check system status:
```bash
ssh -i $KEY_FILE ec2-user@$INSTANCE1_IP "bash /opt/form-submission/scripts/health_check.sh"
```

View worker logs:
```bash
# Discovery workers
ssh -i $KEY_FILE ec2-user@$INSTANCE1_IP "cd /opt/form-submission && docker-compose -f deployments/docker/docker-compose.instance1.yml logs -f discovery-worker-1"

# Submission workers
ssh -i $KEY_FILE ec2-user@$INSTANCE2_IP "cd /opt/form-submission && docker-compose -f deployments/docker/docker-compose.instance2.yml logs -f submission-worker-1"
```

## Step 8: Export Results

After processing completes, export results from PostgreSQL:

```bash
ssh -i $KEY_FILE ec2-user@$INSTANCE1_IP

docker exec postgres psql -U formbot -d form_submissions -c "
COPY (
  SELECT 
    d.url as domain,
    s.form_url,
    s.status,
    s.submitted_at,
    s.duration_ms,
    s.had_captcha,
    s.captcha_solved,
    s.captcha_cost,
    s.error_message
  FROM submissions s
  JOIN domains d ON s.domain_id = d.id
  ORDER BY s.submitted_at DESC
) TO STDOUT WITH CSV HEADER
" > /tmp/results.csv
```

Download results:
```bash
scp -i $KEY_FILE ec2-user@$INSTANCE1_IP:/tmp/results.csv ./submission-results.csv
```

## Step 9: Cleanup

When processing is complete, tear down AWS resources:

```bash
cd deployments/aws/scripts
./teardown.sh
```

This will:
- Terminate all EC2 instances
- Release Elastic IPs

**Cost Summary:**
- Running time: ~5-7 days
- 2× t3.medium spot instances: ~$20-25
- CapSolver (25k solves): ~$30
- Proxies: ~$7.50-35
- **Total: $57.50-90**

## Troubleshooting

### Workers not starting

Check Docker logs:
```bash
docker-compose -f deployments/docker/docker-compose.instance1.yml logs
```

Common issues:
- Missing environment variables (check `.env`)
- Kafka not ready (wait 30 seconds after starting)
- Out of memory (reduce worker counts in config)

### High failure rate

Check reasons:
```bash
redis-cli --scan --pattern "error:*"
```

Common causes:
- Invalid domains (typos, non-existent sites)
- CAPTCHA budget exceeded
- Proxy bans (enable direct connection)

### Spot instance interruption

AWS will send a 2-minute warning before interruption. Workers handle graceful shutdown automatically.

To resume:
1. Launch new spot instances with same script
2. Workers will resume from Kafka queue
3. Redis cache persists domain processing state

### Budget exceeded

Check CAPTCHA spend:
```bash
redis-cli GET budget:captcha:spent
```

Adjust budget in `config/config.yaml` and restart workers.

## Performance Tuning

### Increase throughput

1. Scale workers (requires larger instances):
   - Edit `docker-compose` files
   - Add more worker replicas
   - Restart: `docker-compose up -d --scale submission-worker-1=20`

2. Adjust Kafka partitions:
   ```bash
   kafka-topics --alter --topic submission-tasks --partitions 10 --bootstrap-server localhost:9092
   ```

### Reduce costs

1. Use single instance (not recommended for 100k):
   - Combine all services on one t3.medium
   - Reduce worker counts to 3+5

2. Skip all CAPTCHAs:
   - Set `budget.captcha_limit_usd: 0` in config
   - Accept ~40% success rate

3. Use free proxies only:
   - Set `proxy.enable_direct: true`
   - Enable `proxy.fallback_free_proxies: true`

## Security Notes

- SSH key has full access to instances - keep it secure
- PostgreSQL has default credentials - change in production
- Prometheus is publicly accessible - consider restricting IP access
- API keys are in environment variables - use AWS Secrets Manager for production

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Verify connectivity: `scripts/health_check.sh`
3. Review Prometheus metrics
4. Check PostgreSQL error logs table
