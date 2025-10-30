# Development Roadmap: i4g Production System

> **Last Updated**: October 30, 2025  
> **Owner**: Jerry Soung  
> **Timeline**: 8 weeks @ 10 hours/week = 80 hours total

---

## Overview

This roadmap outlines the path from prototype to production-ready deployment, prioritized by criticality and dependencies. All tasks are scoped for a single volunteer developer working 10 hours/week with zero budget constraints.

---

## Phase 1: MVP Foundation (Weeks 1-4, 40 hours)

**Goal**: Deploy secure, monitored API to GCP Cloud Run

### Week 1-2: Security & Infrastructure (20 hours)

| Task | Priority | Effort | Owner | Status |
|------|----------|--------|-------|--------|
| Set up GCP project (\`i4g-prod\`) | P0 | 1h | Jerry | ⚪ Not Started |
| Apply for Google for Nonprofits credits | P1 | 1h | Jerry | ⚪ Not Started |
| Implement PII tokenization module | P0 | 6h | Jerry | ⚪ Not Started |
| Add OAuth 2.0 authentication (Google Sign-In) | P0 | 4h | Jerry | ⚪ Not Started |
| Create Firestore security rules | P0 | 2h | Jerry | ⚪ Not Started |
| Set up Secret Manager for credentials | P0 | 1h | Jerry | ⚪ Not Started |
| Write SQLite → Firestore migration script | P0 | 3h | Jerry | ⚪ Not Started |
| Security audit (OWASP Top 10 checklist) | P0 | 2h | Jerry | ⚪ Not Started |

**Deliverables**:
- ✅ PII vault functional with encryption
- ✅ OAuth login working
- ✅ Data migrated to Firestore

---

### Week 3-4: Deployment & Observability (20 hours)

| Task | Priority | Effort | Owner | Status |
|------|----------|--------|-------|--------|
| Dockerize FastAPI application | P0 | 3h | Jerry | ⚪ Not Started |
| Deploy to Cloud Run (staging) | P0 | 2h | Jerry | ⚪ Not Started |
| Implement structured logging (JSON + correlation IDs) | P0 | 3h | Jerry | ⚪ Not Started |
| Add health check endpoints | P0 | 2h | Jerry | ⚪ Not Started |
| Set up CI/CD pipeline (GitHub Actions) | P0 | 4h | Jerry | ⚪ Not Started |
| Configure Cloud Monitoring metrics | P0 | 2h | Jerry | ⚪ Not Started |
| Set up alerts (error rate, latency) | P0 | 2h | Jerry | ⚪ Not Started |
| Update documentation (README, dev_guide) | P1 | 2h | Jerry | ⚪ Not Started |

**Deliverables**:
- ✅ API running on Cloud Run (public URL)
- ✅ CI/CD auto-deploys on \`main\` branch
- ✅ Monitoring dashboard functional

---

## Phase 2: Production Hardening (Weeks 5-6, 20 hours)

### Week 5: Data Compliance & Testing

| Task | Priority | Effort | Owner | Status |
|------|----------|--------|-------|--------|
| Implement data retention policies (TTL) | P0 | 4h | Jerry | ⚪ Not Started |
| Add GDPR data export endpoint | P1 | 3h | Jerry | ⚪ Not Started |
| Write integration tests (upload → classify → review) | P1 | 6h | Jerry | ⚪ Not Started |
| Load testing (20 concurrent users) | P1 | 2h | Jerry | ⚪ Not Started |
| Security penetration testing | P0 | 3h | Jerry | ⚪ Not Started |
| Document compliance procedures | P1 | 2h | Jerry | ⚪ Not Started |

**Deliverables**:
- ✅ Test coverage ≥80%
- ✅ Load test results documented
- ✅ Compliance.md published

---

### Week 6: Analyst Experience

| Task | Priority | Effort | Owner | Status |
|------|----------|--------|-------|--------|
| Update Streamlit dashboard with OAuth | P1 | 4h | Jerry | ⚪ Not Started |
| Add bulk operations (assign, export CSV) | P1 | 3h | Jerry | ⚪ Not Started |
| Mobile-responsive design tweaks | P2 | 2h | Jerry | ⚪ Not Started |
| Create analyst onboarding tutorial | P1 | 3h | Jerry | ⚪ Not Started |
| Performance metrics dashboard | P2 | 3h | Jerry | ⚪ Not Started |
| User feedback form | P2 | 1h | Jerry | ⚪ Not Started |
| Beta testing with 3 analysts | P0 | 4h | Jerry | ⚪ Not Started |

**Deliverables**:
- ✅ Dashboard deployed to production
- ✅ 3 beta analysts onboarded
- ✅ Feedback collected

---

## Phase 3: Launch & Iteration (Weeks 7-8, 20 hours)

### Week 7: Report Generation & LEO Integration

| Task | Priority | Effort | Owner | Status |
|------|----------|--------|-------|--------|
| Add PDF report generation (replace .docx) | P1 | 4h | Jerry | ⚪ Not Started |
| Digital signature support (hash + timestamp) | P2 | 3h | Jerry | ⚪ Not Started |
| Batch report export | P2 | 2h | Jerry | ⚪ Not Started |
| Create LEO download portal | P1 | 4h | Jerry | ⚪ Not Started |
| Write report generation guide | P1 | 2h | Jerry | ⚪ Not Started |
| Test with sample law enforcement partner | P1 | 3h | Jerry | ⚪ Not Started |
| Final security review | P0 | 2h | Jerry | ⚪ Not Started |

**Deliverables**:
- ✅ PDF reports functional
- ✅ LEO portal tested
- ✅ Security sign-off

---

### Week 8: Public Launch

| Task | Priority | Effort | Owner | Status |
|------|----------|--------|-------|--------|
| Final documentation review | P0 | 3h | Jerry | ⚪ Not Started |
| Record demo video (5 min walkthrough) | P1 | 2h | Jerry | ⚪ Not Started |
| Write launch announcement (blog post) | P1 | 2h | Jerry | ⚪ Not Started |
| Prepare pitch deck for university partners | P1 | 3h | Jerry | ⚪ Not Started |
| Deploy to production (switch DNS if needed) | P0 | 2h | Jerry | ⚪ Not Started |
| Monitor launch (first 48 hours) | P0 | 4h | Jerry | ⚪ Not Started |
| Collect feedback & prioritize fixes | P0 | 2h | Jerry | ⚪ Not Started |
| Update roadmap for Phase 4 | P1 | 2h | Jerry | ⚪ Not Started |

**Deliverables**:
- ✅ Production system live
- ✅ Launch announcement published
- ✅ Feedback loop established

---

## Success Metrics

| Metric | Week 4 Target | Week 8 Target | Week 16 Target |
|--------|---------------|---------------|----------------|
| System Uptime | 95%+ | 99%+ | 99.5%+ |
| Active Analysts | 1 (Jerry) | 3 beta testers | 12+ volunteers |
| Cases Processed | 10 test cases | 50 real cases | 200+ cases |
| False Positive Rate | N/A | <20% | <15% |
| Infrastructure Cost | $0 | $0 | $0 |

---

## Contact

**Project Lead**: Jerry Soung (jerry@i4g.org)  
**GitHub**: https://github.com/jsoung/i4g  
**Documentation**: https://github.com/jsoung/i4g/tree/main/docs

---

**Last Updated**: 2025-10-30  
**Next Review**: 2025-11-06 (weekly)
