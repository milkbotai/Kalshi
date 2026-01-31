# Security Audit Checklist

**Document Version:** 1.0
**Last Updated:** 2026-01-29
**Review Frequency:** Quarterly

## Overview

This checklist covers security controls for the Milkbot Weather Trading Platform. Complete all items before production deployment and review quarterly.

---

## 1. Secret Management

### 1.1 API Keys & Credentials
- [ ] Kalshi API keys stored in environment variables only
- [ ] OpenRouter API key stored in environment variables only
- [ ] No secrets in source code (verified with `git secrets --scan`)
- [ ] No secrets in git history (verified with `trufflehog`)
- [ ] `.env` file in `.gitignore`
- [ ] `.env.example` contains only placeholder values
- [ ] Separate API keys for demo vs production environments

### 1.2 Database Credentials
- [ ] Database password is unique and strong (>20 chars)
- [ ] Database user has minimum required permissions
- [ ] No shared database credentials between services
- [ ] Connection strings use SSL (`sslmode=require`)

### 1.3 Key Rotation
- [ ] API key rotation procedure documented
- [ ] Key rotation tested in staging
- [ ] Rotation schedule defined (quarterly recommended)
- [ ] Old keys revoked after rotation

---

## 2. Authentication & Authorization

### 2.1 Service Authentication
- [ ] Analytics API only binds to localhost (127.0.0.1)
- [ ] Dashboard cannot access trading keys
- [ ] No direct public access to trading service
- [ ] Inter-service communication authenticated

### 2.2 External Access
- [ ] NGINX blocks direct IP access
- [ ] Only Cloudflare IPs allowed to connect
- [ ] Rate limiting configured (10 req/sec dashboard, 30 req/sec API)
- [ ] No admin endpoints exposed publicly

---

## 3. Input Validation

### 3.1 API Input Validation
- [ ] All API inputs validated with Pydantic models
- [ ] City codes validated against allowed list
- [ ] Date ranges bounded to prevent DoS
- [ ] Numeric inputs have min/max bounds

### 3.2 SQL Injection Prevention
- [ ] All queries use parameterized statements
- [ ] No string concatenation in SQL queries
- [ ] ORM (SQLAlchemy) used consistently
- [ ] Raw SQL reviewed and approved

### 3.3 XSS Prevention
- [ ] Streamlit auto-escapes output (verified)
- [ ] No `st.markdown(unsafe_allow_html=True)` without sanitization
- [ ] User-provided data never rendered as HTML

---

## 4. Network Security

### 4.1 TLS/SSL Configuration
- [ ] TLS 1.2+ only (no TLS 1.0/1.1)
- [ ] Strong cipher suites configured
- [ ] Cloudflare SSL mode: Full (Strict)
- [ ] Origin certificate installed and valid
- [ ] HSTS enabled with long max-age

### 4.2 Firewall Rules
- [ ] Only ports 80, 443 exposed publicly
- [ ] Database port (5432) blocked from public
- [ ] SSH restricted to known IPs
- [ ] Internal services bound to localhost only

### 4.3 NGINX Security Headers
- [ ] X-Frame-Options: SAMEORIGIN
- [ ] X-Content-Type-Options: nosniff
- [ ] X-XSS-Protection: 1; mode=block
- [ ] Content-Security-Policy configured
- [ ] Referrer-Policy: strict-origin-when-cross-origin

---

## 5. Data Protection

### 5.1 Sensitive Data Handling
- [ ] No PII stored in trading database
- [ ] Order IDs not exposed in public API
- [ ] Intent keys not exposed publicly
- [ ] 60-minute trade delay enforced in all paths

### 5.2 Logging Security
- [ ] Secrets redacted from all logs
- [ ] API keys/tokens never logged
- [ ] Log files have restricted permissions (0640)
- [ ] Log rotation configured

### 5.3 Backup Security
- [ ] Backups encrypted at rest
- [ ] Backup access restricted
- [ ] Restore procedure tested
- [ ] Backup retention policy enforced

---

## 6. Dependency Security

### 6.1 Package Management
- [ ] Dependencies pinned to specific versions
- [ ] `pip-audit` or `safety` scan passed
- [ ] No known vulnerabilities in dependencies
- [ ] Dependency update schedule defined

### 6.2 Container/Runtime Security
- [ ] Python version supported and patched
- [ ] OS packages updated
- [ ] Unnecessary packages removed
- [ ] Non-root user for services

---

## 7. Monitoring & Detection

### 7.1 Security Logging
- [ ] Failed authentication attempts logged
- [ ] API errors logged with context
- [ ] Unusual trading patterns logged
- [ ] Log aggregation configured

### 7.2 Alerting
- [ ] Service downtime alerts configured
- [ ] Error rate spike alerts configured
- [ ] Circuit breaker trigger alerts configured
- [ ] Disk/memory threshold alerts configured

### 7.3 Anomaly Detection
- [ ] Unusual API access patterns monitored
- [ ] Brute force protection enabled (rate limiting)
- [ ] Geographic access anomalies tracked

---

## 8. Incident Response

### 8.1 Preparation
- [ ] Incident response plan documented
- [ ] Contact list for security incidents
- [ ] Kill switch procedure documented and tested
- [ ] Rollback procedure documented and tested

### 8.2 Recovery
- [ ] Backup restore tested within RTO
- [ ] Service restart procedures documented
- [ ] Post-incident review template ready

---

## 9. Code Security

### 9.1 Static Analysis
- [ ] `bandit` security linter passed
- [ ] `mypy` type checking passed
- [ ] No hardcoded credentials in code
- [ ] No debug code in production

### 9.2 Code Review
- [ ] Security-sensitive changes require review
- [ ] API endpoint changes reviewed
- [ ] Database schema changes reviewed
- [ ] Authentication changes reviewed

---

## 10. Compliance

### 10.1 Trading Regulations
- [ ] Demo mode clearly distinguishes from live
- [ ] LIVE mode requires explicit confirmation
- [ ] Trade audit trail maintained
- [ ] All decisions reproducible from stored inputs

### 10.2 Data Retention
- [ ] Retention policy documented
- [ ] Old data purged per policy
- [ ] Audit logs retained as required

---

## Audit Sign-Off

| Section | Auditor | Date | Status |
|---------|---------|------|--------|
| 1. Secret Management | | | |
| 2. Auth & Authorization | | | |
| 3. Input Validation | | | |
| 4. Network Security | | | |
| 5. Data Protection | | | |
| 6. Dependency Security | | | |
| 7. Monitoring & Detection | | | |
| 8. Incident Response | | | |
| 9. Code Security | | | |
| 10. Compliance | | | |

**Overall Status:** [ ] PASS / [ ] FAIL / [ ] NEEDS REMEDIATION

**Next Review Date:** _______________

---

## Automated Security Scans

Run these commands before each release:

```bash
# Check for secrets in code
git secrets --scan

# Check for secrets in git history
trufflehog git file://. --only-verified

# Python security linter
bandit -r src/ -ll

# Dependency vulnerability scan
pip-audit

# Check for common security issues
safety check
```

## References

- OWASP Top 10: https://owasp.org/Top10/
- CWE/SANS Top 25: https://cwe.mitre.org/top25/
- Python Security: https://python-security.readthedocs.io/
