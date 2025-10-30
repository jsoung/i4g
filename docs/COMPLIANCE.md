# Data Compliance & Security Guide

> **Document Owner**: Jerry Soung  
> **Last Updated**: October 30, 2025  
> **Review Cycle**: Quarterly  
> **Version**: 1.0

---

## Executive Summary

This document outlines **i4g's** commitment to protecting personally identifiable information (PII) and complying with applicable data protection regulations. As a volunteer-operated non-profit assisting scam victims, we handle sensitive data including financial records, personal communications, and identity documents.

**Key Principles**:
1. **Privacy by Design**: PII tokenization from the moment of upload
2. **Zero Trust**: No analyst ever sees raw PII
3. **Minimal Retention**: Data deleted within 90 days unless legally required
4. **Transparency**: Victims control their data (export, delete)

---

## Applicable Regulations

### 1. **FERPA** (Family Educational Rights and Privacy Act)
**Applies when**: Partnering with universities (e.g., University of Alabama graduate students as analysts)

**Requirements**:
- Annual FERPA training for all analysts accessing victim data through university accounts
- Parental consent for victims under 18
- No disclosure of educational records without consent

**Implementation**:
- All university-affiliated analysts sign Data Use Agreements (DUA)
- Training materials: https://studentprivacy.ed.gov/training
- Records retention: Follow university policies (typically 5 years)

---

### 2. **GDPR/CCPA** (EU General Data Protection Regulation / California Consumer Privacy Act)
**Applies when**: Victims from EU or California

**Key Rights**:
- **Right to Access**: Export all data in JSON format (\`/api/cases/{case_id}/export\`)
- **Right to Deletion**: Immediate hard delete (\`/api/cases/{case_id}\` DELETE)
- **Right to Rectification**: Analysts can update PII via token references
- **Data Portability**: Machine-readable exports

---

### 3. **State Data Breach Laws**
**Applies**: All 50 US states require breach notification

**Timeline**:
- **Discovery to Assessment**: 24 hours
- **Notification to Victims**: 72 hours (most states)
- **Notification to Regulators**: Varies (CA: immediate if >500 residents)

**Thresholds**:
- Any breach of unencrypted PII = mandatory notification
- Encrypted data breach = case-by-case assessment

---

## PII Handling Procedures

### Data Classification

| Level | Examples | Encryption | Access |
|-------|----------|------------|--------|
| **Critical** | SSN, bank accounts, passwords | AES-256-GCM | PII vault only |
| **High** | Full name, address, phone | AES-256-GCM | Tokenized in API |
| **Medium** | Scammer info, dates, amounts | TLS in transit | All analysts |
| **Low** | Case status, timestamps | TLS in transit | Public (anonymized) |

---

### Tokenization Workflow

**Example**:
- **Raw Input**: "My SSN is 123-45-6789 and I lost $5,000"
- **Stored in DB**: "My SSN is <PII:SSN:7a8f2e> and I lost $5,000"
- **Analyst View**: "My SSN is ███████ and I lost $5,000"
- **LEO Report**: "My SSN is 123-45-6789 and I lost $5,000" (with victim consent)

---

## Data Retention Policy

### Timelines

| Data Type | Retention Period | Rationale | Deletion Method |
|-----------|------------------|-----------|-----------------|
| **Active Cases** | Until resolution + 30 days | Ongoing investigation | Soft delete (archive flag) |
| **Resolved Cases** | 90 days post-resolution | Follow-up questions | Hard delete from Firestore |
| **PII Vault** | Matches case retention | Compliance | \`delete()\` + crypto shred key |
| **Audit Logs** | 1 year | Security investigations | Cloud Logging TTL |
| **Analytics (anonymized)** | Indefinite | Research | No PII present |

---

## Security Controls

### Encryption

| Component | Method | Key Management |
|-----------|--------|----------------|
| **Data at Rest** | AES-256-GCM | Google Secret Manager |
| **Data in Transit** | TLS 1.3 | Cloud Run auto-managed |
| **PII Vault** | Fernet (symmetric) | Rotated monthly |
| **Backups** | CMEK (Customer-Managed) | Separate GCP project |

### Access Controls

**Role-Based Permissions**:
```yaml
roles:
  victim:
    - view_own_case
    - update_own_case
    - delete_own_case
  
  analyst:
    - view_assigned_cases
    - update_case_status
    - add_notes
  
  admin:
    - view_all_cases
    - manage_analysts
    - access_audit_logs
  
  leo: # Law Enforcement Officer
    - download_reports (with subpoena)
```

---

## Incident Response Plan

### Phase 1: Detection (< 1 hour)

**Triggers**:
- Anomaly detection alert (e.g., 100+ PII vault queries in 1 minute)
- Failed login attempts (>10 per hour)
- Unauthorized access logs
- User report of suspicious activity

**Actions**:
1. Page on-call admin (Jerry)
2. Review Cloud Logging for correlation IDs
3. Check \`/api/health\` endpoint status
4. Review Firestore audit logs

---

### Phase 2: Containment (< 4 hours)

**Steps**:
1. **Isolate affected systems**:
   ```bash
   gcloud run services update i4g-api --no-traffic
   ```

2. **Revoke compromised credentials**:
   ```bash
   gcloud secrets versions disable TOKEN_ENCRYPTION_KEY --secret=pii-vault-key
   ```

3. **Preserve evidence**:
   - Export Cloud Logging: \`gcloud logging read "timestamp>=2025-10-30T00:00:00Z" --format=json > incident.log\`
   - Snapshot Firestore: Automated daily backups
   - Download Docker image: \`gcloud container images describe gcr.io/i4g-prod/api:latest\`

4. **Notify stakeholders**:
   - Email to \`security@i4g.org\`
   - SMS to admin on-call
   - Log in incident tracker (GitHub Issues with \`security\` label)

---

### Phase 3: Investigation (< 24 hours)

**Questions**:
- Was PII accessed? (Check \`/pii_vault\` read logs)
- Who was affected? (Cross-reference \`case_id\` with victim emails)
- How was the breach achieved? (Review authentication logs)

**Tools**:
- **Cloud Logging**: Search by \`severity>=ERROR\`
- **Firestore Audits**: \`gcloud firestore operations list\`
- **Network Logs**: VPC flow logs (if applicable)

---

### Phase 4: Notification (< 72 hours)

**Legal Requirements**:
- **GDPR**: 72 hours to notify supervisory authority
- **CCPA**: "Without unreasonable delay"
- **State laws**: Varies (most 30-90 days)

**Victim Notification Template**:
```
Subject: Important Security Notice About Your i4g Case

Dear [Victim Name],

We are writing to inform you that on [Date], we detected unauthorized access to 
our systems. This incident may have affected your personal information submitted 
to i4g on [Case Creation Date].

WHAT HAPPENED:
[Brief description of breach]

INFORMATION POTENTIALLY ACCESSED:
- Full name
- Email address
- [Other fields specific to case]

NOTE: Financial account details (e.g., bank account numbers) were NOT exposed 
due to our PII tokenization system.

WHAT WE'RE DOING:
1. We immediately isolated affected systems
2. We are cooperating with law enforcement
3. We have enhanced security monitoring

WHAT YOU SHOULD DO:
1. Monitor your financial statements for suspicious activity
2. Consider placing a fraud alert on your credit report (https://www.ftc.gov/faq)
3. Report suspicious activity to local law enforcement

CONTACT US:
Email: security@i4g.org
Phone: [Number]

We sincerely apologize for this incident and are committed to protecting your data.

Sincerely,
Jerry Soung
i4g Project Lead
```

---

### Phase 5: Recovery (< 1 week)

**Actions**:
1. Patch vulnerabilities identified in investigation
2. Rotate all secrets (API keys, encryption keys, service account keys)
3. Deploy patched version to production
4. Monitor for 48 hours continuously
5. Update security documentation

---

## Audit & Compliance Monitoring

### Quarterly Audits

**Checklist**:
- [ ] Review all analyst access logs (spot check 10% of sessions)
- [ ] Test data export functionality (GDPR compliance)
- [ ] Validate PII tokenization accuracy (sample 20 random cases)
- [ ] Penetration testing (OWASP Top 10)
- [ ] Update this compliance document with any regulatory changes

---

## Third-Party Data Sharing

**Policy**: i4g does NOT share victim data with third parties except:

1. **Law Enforcement**: With valid subpoena or court order
   - Process: LEO submits request to \`legal@i4g.org\`
   - Verification: Check badge number, court docs
   - Delivery: Encrypted email or secure portal

2. **University Researchers**: Anonymized data only (no PII)
   - Approval: IRB (Institutional Review Board) required
   - Format: Aggregated statistics, no case-level detail

3. **Victim's Consent**: Explicit opt-in for sharing with financial institutions

---

## Training Requirements

### For All Analysts

**Onboarding (3 hours)**:
1. Data handling policies (this document)
2. Recognizing PII (quiz: 80% passing score)
3. Secure communication practices (encrypted email, 2FA)
4. Incident reporting procedures

**Annual Refresher (1 hour)**:
- Policy updates
- Case studies from security incidents (anonymized)
- Q&A session

**Certification**:
- Sign acknowledgment form: "I have read and understand the i4g Data Compliance Guide"
- Certificate stored in Firestore: \`/analysts/{uid}/certifications\`

---

## Contact Information

**Data Protection Officer**: Jerry Soung  
**Email**: dpo@i4g.org  
**Phone**: [To be added]  

**Report Security Issues**: security@i4g.org (PGP key available)  
**Legal Inquiries**: legal@i4g.org

---

## Appendix A: PII Detection Patterns

```python
PII_PATTERNS = {
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
    "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "address": r"\b\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b",
    "dob": r"\b\d{1,2}/\d{1,2}/\d{4}\b",
}
```

---

**Document Version History**:
- **v1.0** (2025-10-30): Initial draft by Jerry Soung
- **Next Review**: 2026-01-30 (quarterly)

---

**Legal Disclaimer**: This document provides guidance based on current understanding 
of applicable laws. It is not legal advice. Consult a licensed attorney for specific 
compliance questions.
