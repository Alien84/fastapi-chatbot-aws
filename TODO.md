# Infrastructure Improvement TODO

This document outlines recommended improvements for the FastAPI chatbot infrastructure to achieve production-readiness and scalability for a fitness app.

## 🚨 CRITICAL - Fix Before Production Launch

### Security Issues
- [ ] **Move RDS to private subnets**
  - Files: `infrastructure/modules/vpc.py`, `infrastructure/modules/rds.py`
  - Current: RDS in public subnets (security risk)
  - Target: Move to private subnets with proper security group restrictions
  - Impact: High - Critical security improvement

- [ ] **Add NAT Gateway for private subnet internet access**
  - File: `infrastructure/modules/vpc.py`
  - Current: Private subnets can't reach internet (Lambda functions can't call external APIs)
  - Target: NAT Gateway in each public subnet for high availability
  - Cost: ~$32/month per NAT Gateway
  - Impact: High - Enables Lambda functions to work properly

- [ ] **Enable HTTPS/TLS with ACM certificate**
  - File: `infrastructure/__main__.py`
  - Current: HTTP only (unencrypted traffic)
  - Target: ALB with ACM certificate for HTTPS
  - Impact: High - Data encryption in transit

- [ ] **Restrict SSH access**
  - File: `infrastructure/modules/vpc.py` (web_sg)
  - Current: SSH open to 0.0.0.0/0
  - Target: Remove SSH ingress, use AWS Session Manager only
  - Impact: High - Prevent unauthorized access

- [ ] **Fix Lambda VPC configuration**
  - File: `infrastructure/modules/lambda_functions.py`
  - Current: VPC configuration commented out (can't access RDS securely)
  - Target: Enable VPC configuration with private subnets
  - Impact: High - Secure database access from Lambda

- [ ] **Fix hardcoded AWS account ID**
  - Files: `infrastructure/modules/lambda_functions.py`, `infrastructure/modules/secrets.py`
  - Current: Hardcoded `555576841436` in IAM policies
  - Target: Use dynamic `aws.get_caller_identity().account_id`
  - Impact: Medium - Prevents cross-account issues

### Database Reliability
- [ ] **Enable RDS automated backups**
  - File: `infrastructure/modules/rds.py`
  - Current: `backup_retention_period=0` (no backups)
  - Target: Set to 7 days minimum (30 days for prod)
  - Cost: Minimal (within free tier for 7 days)
  - Impact: High - Data protection

- [ ] **Enable RDS Multi-AZ deployment**
  - File: `infrastructure/modules/rds.py`
  - Current: `multi_az=False`
  - Target: `multi_az=True` for prod/staging
  - Cost: ~2x RDS instance cost
  - Impact: High - High availability, automatic failover

- [ ] **Upgrade RDS instance size**
  - File: `infrastructure/modules/rds.py`
  - Current: db.t3.micro (1GB RAM, shared CPU)
  - Target: db.t3.small minimum (2GB RAM) for staging/prod
  - Cost: ~$30/month (db.t3.small) vs ~$15/month (db.t3.micro)
  - Impact: Medium - Better performance, more connections

### Monitoring & Alerting
- [ ] **Connect CloudWatch alarms to SNS**
  - File: `infrastructure/__main__.py`
  - Current: `alarm_actions` commented out (no notifications!)
  - Target: Enable SNS notifications for all critical alarms
  - Impact: High - Get notified of issues

- [ ] **Verify SNS email subscription**
  - Current: Email endpoint may not be confirmed
  - Target: Confirm subscription for alerts
  - Impact: High - Ensure alerts are received

---

## 🔥 HIGH PRIORITY - First Month

### Performance & Scalability
- [ ] **Add RDS Proxy for connection pooling**
  - New file: `infrastructure/modules/rds_proxy.py`
  - Current: Each request creates new DB connection (hits limits at ~100 users)
  - Target: RDS Proxy with connection pooling
  - Cost: ~$15/month
  - Impact: High - Support 500+ concurrent users

- [ ] **Add ElastiCache Redis cluster**
  - New file: `infrastructure/modules/elasticache.py`
  - Purpose: Session storage, query caching, rate limiting
  - Target: cache.t3.micro (2 nodes, Multi-AZ)
  - Cost: ~$25/month
  - Impact: Medium - Reduce database load by 50-70%

- [ ] **Implement connection pooling in FastAPI**
  - File: `app/main.py`
  - Current: SQLAlchemy creates new connections per request
  - Target: Use connection pool with max 20 connections
  - Impact: High - Better resource utilization

### Security Enhancements
- [ ] **Add WAF to Application Load Balancer**
  - File: `infrastructure/__main__.py` (autoscaling section)
  - Purpose: Protect against OWASP top 10 (SQL injection, XSS, etc.)
  - Target: AWS WAF with managed rule groups
  - Cost: ~$5/month + $1 per million requests
  - Impact: High - Application security

- [ ] **Add API Gateway throttling/rate limiting**
  - File: `infrastructure/modules/lambda_api_gateway.py`
  - Current: No rate limiting
  - Target: 1000 requests/second per API key, burst 2000
  - Impact: Medium - Prevent abuse

- [ ] **Implement secrets rotation**
  - File: `infrastructure/modules/secrets.py`
  - Current: Database password never rotates
  - Target: AWS Secrets Manager with 90-day rotation
  - Cost: ~$0.80/month per secret
  - Impact: Medium - Security best practice

### Deployment Improvements
- [ ] **Add health check grace period to user_data**
  - File: `infrastructure/user_data.sh`
  - Current: 15-minute ECR image wait can delay deployments
  - Target: Reduce to 5 minutes with better polling
  - Impact: Medium - Faster deployments

- [ ] **Implement blue-green deployment strategy**
  - Files: GitHub Actions workflows
  - Current: Direct replacement (potential downtime)
  - Target: Create new ASG, test, then switch ALB target group
  - Impact: Medium - Zero-downtime deployments

---

## 📊 MEDIUM PRIORITY - 2-3 Months

### Observability
- [ ] **Enable AWS X-Ray distributed tracing**
  - Files: `app/main.py`, `lambda_functions/*/handler.py`
  - Purpose: Debug performance issues across services
  - Cost: $5 per million traces
  - Impact: Medium - Better debugging

- [ ] **Enable RDS Performance Insights**
  - File: `infrastructure/modules/rds.py`
  - Purpose: Identify slow queries
  - Cost: Free for 7 days retention
  - Impact: Medium - Database optimization

- [ ] **Create CloudWatch Insights queries**
  - New file: `infrastructure/modules/cloudwatch_insights.py`
  - Purpose: Saved queries for common issues
  - Examples: Error rates, slow endpoints, user activity
  - Impact: Low - Easier troubleshooting

- [ ] **Add custom CloudWatch metrics**
  - File: `app/main.py`
  - Metrics: Chat response time, message processing time, user engagement
  - Impact: Medium - Business intelligence

### Database Optimization
- [ ] **Add RDS read replicas**
  - File: `infrastructure/modules/rds.py`
  - Purpose: Offload read queries (analytics, reporting)
  - Target: 1-2 read replicas in different AZs
  - Cost: ~$30/month per replica
  - Impact: Medium - Scale reads independently

- [ ] **Implement database migration automation**
  - Files: `app/alembic/`, GitHub Actions
  - Current: Manual schema changes
  - Target: Alembic migrations in CI/CD pipeline
  - Impact: Medium - Safer schema changes

- [ ] **Optimize database indexes**
  - File: `app/models.py` or migration scripts
  - Purpose: Faster queries on common patterns
  - Target: Index on user_id, created_at, message_type
  - Impact: High - 10-100x query speedup

### Application Architecture
- [ ] **Add CDN (CloudFront) for static assets**
  - New file: `infrastructure/modules/cloudfront.py`
  - Purpose: Faster content delivery, reduce server load
  - Cost: $0.085 per GB (first 10TB)
  - Impact: Medium - Better user experience

- [ ] **Implement async message processing with SQS**
  - New file: `infrastructure/modules/sqs.py`
  - Current: Direct Lambda invocation (tight coupling)
  - Target: FastAPI → SQS → Lambda (decoupled)
  - Cost: Free tier covers 1M requests/month
  - Impact: Medium - Better reliability

- [ ] **Add request/response caching**
  - File: `app/main.py`
  - Purpose: Cache common queries (workout plans, meal templates)
  - Target: Redis with 5-minute TTL
  - Impact: Medium - Reduce database load

---

## 🔮 FUTURE ENHANCEMENTS - 6+ Months

### Advanced Scalability
- [ ] **Migrate to Aurora Serverless v2**
  - File: `infrastructure/modules/rds.py`
  - Purpose: Auto-scaling database (0.5-16 ACUs)
  - Cost: $0.12 per ACU-hour (~$90-$500/month)
  - Impact: High - True auto-scaling
  - Best for: >1000 active users

- [ ] **Consider ECS Fargate instead of EC2**
  - Major refactor: Replace `infrastructure/__main__.py` EC2/ASG sections
  - Purpose: Serverless containers (no server management)
  - Cost: ~$30/month per task (2 tasks = $60)
  - Impact: High - Better scaling, no maintenance
  - Best for: >5000 users or microservices

- [ ] **Add DynamoDB for user preferences**
  - New file: `infrastructure/modules/dynamodb.py`
  - Purpose: Fast reads for user settings, preferences
  - Cost: On-demand pricing (~$1.25 per million writes)
  - Impact: Medium - Faster user data access
  - Best for: Read-heavy user data

### Microservices Architecture
- [ ] **Split into microservices**
  - Services: Chat, Workout, Nutrition, User, Analytics
  - Files: Separate Lambda functions or ECS services
  - Purpose: Independent scaling and deployment
  - Impact: High - Better scalability
  - Best for: >10K users, complex features

- [ ] **Implement API Gateway WebSocket**
  - New file: `infrastructure/modules/websocket_api.py`
  - Purpose: Real-time chat, live workout tracking
  - Cost: $1 per million messages
  - Impact: Medium - Real-time features
  - Best for: Live coaching, group workouts

- [ ] **Add EventBridge for event-driven architecture**
  - New file: `infrastructure/modules/eventbridge.py`
  - Purpose: Decouple services (user signup → send welcome email)
  - Cost: Free for 14M events/month
  - Impact: Medium - Loosely coupled services

### Machine Learning Integration
- [ ] **Add SageMaker for workout recommendations**
  - New file: `infrastructure/modules/sagemaker.py`
  - Purpose: Personalized workout plans based on history
  - Cost: Varies ($0.05-$0.20 per inference)
  - Impact: High - Differentiation feature
  - Best for: AI-powered fitness coaching

- [ ] **Implement Comprehend for sentiment analysis**
  - File: `lambda_functions/message_processor/handler.py`
  - Current: Basic sentiment via Comprehend
  - Target: Train custom model on fitness feedback
  - Impact: Medium - Better user insights

### Multi-Region / Global
- [ ] **Aurora Global Database**
  - File: `infrastructure/modules/rds.py`
  - Purpose: Multi-region read replicas, disaster recovery
  - Cost: ~2x Aurora cost
  - Impact: High - Global performance, DR
  - Best for: International users

- [ ] **CloudFront with edge Lambda**
  - File: `infrastructure/modules/cloudfront.py`
  - Purpose: Process requests at edge locations
  - Cost: Lambda@Edge pricing
  - Impact: Medium - Lowest latency globally
  - Best for: Global user base

### Advanced Monitoring
- [ ] **Integrate with Datadog or New Relic**
  - Files: `app/main.py`, Dockerfile
  - Purpose: Advanced APM, better visualization
  - Cost: ~$15-$31 per host/month
  - Impact: Medium - Professional monitoring
  - Best for: Production apps with budget

- [ ] **Set up PagerDuty for incident management**
  - Integration with SNS
  - Purpose: On-call rotation, escalation
  - Cost: $19-$41 per user/month
  - Impact: Low - Enterprise alerting
  - Best for: Team environments

---

## 💰 COST OPTIMIZATION

### Immediate Savings
- [ ] **Review CloudWatch log retention**
  - File: `infrastructure/__main__.py`
  - Current: 30 days for all logs
  - Target: 7 days for debug logs, 90 days for access logs
  - Savings: ~$10-20/month

- [ ] **Implement ECR image cleanup**
  - File: `infrastructure/modules/lambda_functions.py`
  - Current: Delete after 1 day (too aggressive)
  - Target: Keep last 10 images OR 30 days
  - Impact: Better rollback capability

- [ ] **Use Spot Instances for dev environment**
  - File: `Pulumi.dev.yaml`
  - Purpose: 60-90% cost savings for non-critical workloads
  - Savings: ~$15-20/month for dev
  - Risk: Medium - Instances can be terminated

### Long-term Optimization
- [ ] **Purchase Reserved Instances (1-year)**
  - Purpose: 30-40% discount for predictable workload
  - Target: Prod RDS, prod EC2/Fargate
  - Savings: ~$100-200/month
  - Best for: After stable traffic pattern established

- [ ] **Implement AWS Budgets and Cost Alerts**
  - File: `infrastructure/modules/budgets.py`
  - Purpose: Get notified when costs exceed thresholds
  - Cost: Free for 2 budgets
  - Impact: High - Prevent surprise bills

---

## 📋 TESTING & QUALITY

### Testing Improvements
- [ ] **Add infrastructure tests with pytest**
  - Directory: `tests/infrastructure/`
  - Current: Basic tests exist
  - Target: 80% coverage of Pulumi modules
  - Impact: High - Catch errors before deployment

- [ ] **Implement end-to-end smoke tests**
  - File: `tests/e2e/test_smoke.py`
  - Purpose: Verify deployment success
  - Target: Run in CI/CD after each deployment
  - Impact: High - Catch deployment issues

- [ ] **Add load testing with Locust**
  - New directory: `tests/load/`
  - Purpose: Validate performance under load
  - Target: 100 users, 1000 requests/minute
  - Impact: Medium - Know your limits

### CI/CD Enhancements
- [ ] **Add Pulumi preview in PR comments**
  - File: `.github/workflows/ci.yml`
  - Purpose: See infrastructure changes before merge
  - Impact: Medium - Better code review

- [ ] **Implement automatic rollback on health check failure**
  - File: `.github/workflows/cd_with_docker.yml`
  - Current: Manual rollback required
  - Target: Automatic revert to last known good state
  - Impact: High - Faster recovery

- [ ] **Add staging approval gate**
  - File: `.github/workflows/cd_with_docker.yml`
  - Purpose: Manual approval before prod deployment
  - Impact: Medium - Prevent accidental deployments

---

## 📚 DOCUMENTATION

- [ ] **Document disaster recovery procedures**
  - File: `docs/DISASTER_RECOVERY.md`
  - Include: RDS restore, EC2 replacement, rollback procedures

- [ ] **Create architecture diagrams**
  - File: `docs/ARCHITECTURE.md`
  - Tools: Draw.io, Lucidchart, or CloudCraft
  - Include: Current state, target state, data flow

- [ ] **Document scaling thresholds**
  - File: `docs/SCALING.md`
  - Include: When to scale up, cost implications, migration paths

- [ ] **Create runbook for common issues**
  - File: `docs/RUNBOOK.md`
  - Include: High CPU, database connections, deployment failures

---

## 🎯 QUICK WINS (Do This Week)

1. **Enable RDS backups** (5 minutes)
2. **Connect CloudWatch alarms to SNS** (10 minutes)
3. **Restrict SSH security group** (5 minutes)
4. **Fix hardcoded account ID** (10 minutes)
5. **Upgrade RDS to db.t3.small** (15 minutes + downtime)

**Total time**: ~1 hour
**Impact**: Production-ready security and reliability
**Cost**: +$15/month

---

## 📊 PROGRESS TRACKING

### Sprint 1 (Week 1-2): Security & Reliability
- [ ] All CRITICAL items completed
- [ ] RDS in private subnets
- [ ] HTTPS enabled
- [ ] Monitoring alerts working

### Sprint 2 (Week 3-4): Performance
- [ ] RDS Proxy implemented
- [ ] Redis caching layer added
- [ ] Connection pooling in app

### Sprint 3 (Month 2): Scalability
- [ ] WAF enabled
- [ ] CDN configured
- [ ] Read replicas added

### Sprint 4 (Month 3+): Advanced Features
- [ ] X-Ray tracing
- [ ] Blue-green deployments
- [ ] Database optimization

---

## 🔗 RELATED DOCUMENTS

- [CLAUDE.md](./CLAUDE.md) - Project overview and development guide
- [DEPLOYMENT_MODES.md](./infrastructure/DEPLOYMENT_MODES.md) - Deployment stage documentation
- [CHANGES_SUMMARY.md](./infrastructure/CHANGES_SUMMARY.md) - Recent changes log

---

## ❓ DECISION LOG

Track key architectural decisions here:

### Decision 1: NAT Gateway Strategy
- **Date**: TBD
- **Question**: Single NAT Gateway (cheaper) vs Multi-AZ NAT Gateways (HA)?
- **Decision**:
- **Rationale**:

### Decision 2: Caching Strategy
- **Date**: TBD
- **Question**: Redis vs Memcached? Self-managed vs ElastiCache?
- **Decision**:
- **Rationale**:

### Decision 3: Database Migration Path
- **Date**: TBD
- **Question**: Keep PostgreSQL RDS vs migrate to Aurora?
- **Decision**:
- **Rationale**:

---

**Last Updated**: 2025-12-24
**Owner**: alien110
**Status**: Planning Phase