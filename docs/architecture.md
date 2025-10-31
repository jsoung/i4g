# i4g System Architecture

> **Document Version**: 1.0
> **Last Updated**: October 30, 2025
> **Audience**: Engineers, technical stakeholders, university partners

---

## Executive Summary

**i4g** is a cloud-native, AI-powered platform that helps scam victims document fraud and generate law enforcement reports. The system uses a **privacy-by-design** architecture where personally identifiable information (PII) is tokenized immediately upon upload and stored separately from case data.

**Key Design Principles**:
1. **Zero Trust**: No analyst ever sees raw PII
2. **Serverless**: Zero budget constraint drives Cloud Run deployment
3. **Scalability**: Handles 20 concurrent users on GCP free tier
4. **Security**: AES-256-GCM encryption, OAuth 2.0, Firestore rules

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      User Layer                          │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │  Victim  │      │ Analyst  │      │   LEO    │        │
│  └────┬─────┘      └────┬─────┘      └────┬─────┘        │
└───────┼─────────────────┼─────────────────┼──────────────┘
        │                 │                 │
        │ HTTPS           │ HTTPS           │ HTTPS
        │                 │                 │
┌───────┼─────────────────┼─────────────────┼──────────────┐
│       │     GCP Cloud Run (us-central1)   │              │
│  ┌────▼─────────────────▼─────────────────▼────┐         │
│  │         Load Balancer (HTTPS)               │         │
│  └──┬─────────────────────┬────────────────────┘         │
│     │                     │                              │
│  ┌──▼─────────┐      ┌────▼──────────┐                   │
│  │  FastAPI   │      │  Streamlit    │                   │
│  │  Backend   │      │  Dashboard    │                   │
│  └──┬─────────┘      └────┬──────────┘                   │
└─────┼────────────────────┼───────────────────────────────┘
      │                    │
      │   Firestore API    │
      │                    │
┌─────▼────────────────────▼───────────────────────────────┐
│                  Data Layer (GCP)                        │
│  ┌──────────────┐  ┌────────────┐  ┌───────────┐         │
│  │  Firestore   │  │   Cloud    │  │  Secret   │         │
│  │   (NoSQL)    │  │  Storage   │  │  Manager  │         │
│  └──────┬───────┘  └────────────┘  └───────────┘         │
└─────────┼────────────────────────────────────────────────┘
          │
          │ HTTP (localhost:11434)
          │
┌─────────▼────────────────────────────────────────────────┐
│               External Services                          │
│  ┌──────────────┐    ┌────────────┐                      │
│  │    Ollama    │    │  SendGrid  │                      │
│  │  LLM Server  │    │   Email    │                      │
│  └──────────────┘    └────────────┘                      │
└──────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. **FastAPI Backend**

**Responsibilities**:
- REST API endpoints for case management
- PII tokenization and encryption
- LLM-powered scam classification
- Authentication (OAuth 2.0 JWT validation)
- Firestore CRUD operations

**Technology Stack**:
- Python 3.11
- FastAPI 0.104+ (async/await support)
- LangChain 0.2+ (RAG pipeline)
- google-cloud-firestore (database client)
- google-cloud-storage (file uploads)
- cryptography (AES-256-GCM encryption)

**Key Endpoints**:
- `POST /api/cases` - Submit new case
- `GET /api/cases` - List assigned cases
- `GET /api/cases/{id}` - Get case details (PII masked)
- `PATCH /api/cases/{id}` - Update case status
- `POST /api/cases/{id}/approve` - Generate LEO report
- `GET /api/health` - Health check

---

### 2. **Streamlit Dashboard**

**Responsibilities**:
- Analyst login (OAuth 2.0 flow)
- Case list view with filters
- Case detail view with evidence thumbnails
- PII masking display (███████)
- Bulk operations (assign, export CSV)

**Technology Stack**:
- Python 3.11
- Streamlit 1.28+
- Custom CSS for PII redaction
- Google OAuth 2.0 client library

**Key Features**:
- Session state management (JWT storage)
- Responsive design (works on tablets)
- Real-time updates via Firestore listeners

---

### 3. **Firestore Database**

**Collections**:

```
/cases
  └─ {case_id}
      ├─ created_at: timestamp
      ├─ victim_email: string
      ├─ title: string
      ├─ description: string (tokenized: <PII:SSN:7a8f2e>)
      ├─ classification: {type, confidence}
      ├─ status: "pending_review" | "in_progress" | "resolved"
      ├─ assigned_to: analyst_uid
      ├─ evidence_files: [gs://urls]
      └─ notes: [{author, text, timestamp}]

/pii_vault
  └─ {token_id}
      ├─ case_id: string
      ├─ pii_type: "ssn" | "email" | "phone" | "credit_card"
      ├─ encrypted_value: bytes (AES-256-GCM)
      ├─ encryption_key_version: string
      └─ created_at: timestamp

/analysts
  └─ {uid}
      ├─ email: string
      ├─ full_name: string
      ├─ role: "analyst" | "admin"
      ├─ approved: boolean
      ├─ ferpa_certified: boolean
      └─ last_login: timestamp
```

**Security Rules**:
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Analysts can only read assigned cases
    match /cases/{case_id} {
      allow read: if request.auth != null &&
                     resource.data.assigned_to == request.auth.uid;
    }

    // PII vault locked to backend service account
    match /pii_vault/{token} {
      allow read, write: if request.auth.token.email == 'i4g-backend@i4g-prod.iam.gserviceaccount.com';
    }
  }
}
```

---

### 4. **Ollama LLM Server**

**Responsibilities**:
- Local LLM inference (no API costs)
- Scam classification (romance, crypto, phishing, other)
- PII extraction from unstructured text

**Model**: llama3.1 (8B parameters, 4-bit quantization)

**Inference API**:
```bash
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.1",
  "messages": [
    {
      "role": "user",
      "content": "Classify this scam: I met someone on Tinder..."
    }
  ]
}'
```

**Deployment**: Cloud Run with GPU (T4) for faster inference

---

## Data Flow: Evidence Upload → Report Generation

```
1. VICTIM SUBMITS CASE
   ↓
   POST /api/cases
   {
     "title": "Romance scam",
     "description": "My SSN is 123-45-6789...",
     "evidence_files": [...]
   }

2. PII EXTRACTION & TOKENIZATION
   ↓
   Regex detects: "123-45-6789" (SSN pattern)
   ↓
   Encrypt with AES-256-GCM
   ↓
   Store in /pii_vault: {token: "7a8f2e", encrypted_value: "..."}
   ↓
   Replace in description: "My SSN is <PII:SSN:7a8f2e>..."

3. SCAM CLASSIFICATION
   ↓
   LLM inference (Ollama)
   ↓
   Result: {"type": "Romance Scam", "confidence": 0.92}

4. STORE CASE IN FIRESTORE
   ↓
   /cases/{case_id}:
   {
     "description": "My SSN is <PII:SSN:7a8f2e>...",
     "classification": {"type": "Romance Scam", "confidence": 0.92},
     "status": "pending_review"
   }

5. ANALYST REVIEWS CASE
   ↓
   GET /api/cases/{case_id}
   ↓
   Returns: "My SSN is ███████..." (PII masked)

6. ANALYST APPROVES
   ↓
   POST /api/cases/{case_id}/approve
   ↓
   Fetch encrypted PII from /pii_vault
   ↓
   Decrypt: "123-45-6789"
   ↓
   Generate PDF report with real PII
   ↓
   Upload to Cloud Storage: gs://i4g-reports/{case_id}.pdf
   ↓
   Email victim with secure download link
```

---

## Deployment Architecture

### GCP Free Tier Strategy

| Service | Free Tier | Estimated Usage | Cost |
|---------|-----------|-----------------|------|
| Cloud Run | 2M requests/month | 100K requests/month | $0 |
| Firestore | 50K reads/day | 1K reads/day | $0 |
| Cloud Storage | 5 GB | 2 GB (evidence files) | $0 |
| Cloud Logging | 50 GB/month | 10 GB/month | $0 |
| Secret Manager | 6 active secrets | 3 secrets | $0 |

**Total Monthly Cost**: **$0** (within free tier limits)

**Scaling Trigger**: If usage exceeds free tier, apply for:
1. Google for Nonprofits ($10K/year credits)
2. AWS Activate ($5K credits)
3. NSF SBIR grant ($50K)

---

### Cloud Run Configuration

```bash
gcloud run deploy i4g-api \
  --image gcr.io/i4g-prod/api:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --service-account i4g-backend@i4g-prod.iam.gserviceaccount.com \
  --max-instances 10 \
  --memory 1Gi \
  --timeout 300 \
  --set-env-vars "FIRESTORE_PROJECT_ID=i4g-prod,ENVIRONMENT=production" \
  --set-secrets "TOKEN_ENCRYPTION_KEY=TOKEN_ENCRYPTION_KEY:latest"
```

**Auto-Scaling**:
- Minimum instances: 0 (scales to zero when idle)
- Maximum instances: 10 (free tier limit)
- Concurrency: 20 requests per instance
- Cold start time: ~3 seconds

---

## Security Architecture

### 1. **Authentication Flow (OAuth 2.0)**

```
1. User clicks "Sign In with Google"
   ↓
2. Redirect to Google consent screen
   ↓
3. User approves access
   ↓
4. Google returns authorization code
   ↓
5. Backend exchanges code for tokens
   ↓
6. Verify JWT signature
   ↓
7. Check if user is approved analyst (Firestore /analysts)
   ↓
8. Generate session token (expires in 1 hour)
   ↓
9. Store JWT in Streamlit session state
   ↓
10. All API calls include: Authorization: Bearer {JWT}
```

---

### 2. **PII Isolation**

```
┌─────────────────────────────────────────────────────┐
│                  Untrusted Zone                     │
│  ┌────────────┐         ┌────────────┐              │
│  │ User Input │   -->   │ API Layer  │              │
│  └────────────┘         └──────┬─────┘              │
└────────────────────────────────┼────────────────────┘
                                 │
                       ┌─────────▼─────────┐
                       │   PII Extraction  │
                       │  (Regex + LLM)    │
                       └─────────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                                     │
    ┌─────────▼────────┐              ┌────────────▼────────┐
    │   PII Vault      │              │   Cases DB          │
    │  (Encrypted)     │              │  (Tokenized)        │
    │  Firestore       │              │  Firestore          │
    │  /pii_vault      │              │  /cases             │
    └──────────────────┘              └──────────┬──────────┘
          ⚠️ RESTRICTED                           │
     (Backend SA only)                            │
                                         ┌────────▼──────────┐
                                         │ Analyst Dashboard │
                                         │  (PII masked as   │
                                         │   ███████)        │
                                         └───────────────────┘
```

---

### 3. **Encryption**

**At Rest**:
- **Firestore**: Automatic AES-256 encryption (Google-managed keys)
- **Cloud Storage**: Customer-Managed Encryption Keys (CMEK)
- **PII Vault**: Additional AES-256-GCM layer (app-level encryption)

**In Transit**:
- **All API calls**: TLS 1.3
- **Cloud Run**: HTTPS only (HTTP redirects to HTTPS)
- **Ollama**: HTTP localhost (same machine, no network)

**Key Management**:
```bash
# Encryption key stored in Secret Manager
gcloud secrets create TOKEN_ENCRYPTION_KEY \
  --data-file=<(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')

# Monthly key rotation (automated via Cloud Scheduler)
gcloud secrets versions add TOKEN_ENCRYPTION_KEY --data-file=new_key.txt
```

---

## Monitoring & Observability

### Structured Logging

```json
{
  "timestamp": "2025-10-30T12:00:00Z",
  "severity": "INFO",
  "correlation_id": "uuid-v4",
  "user_id": "analyst_uid_123",
  "action": "case_approved",
  "metadata": {
    "case_id": "uuid-v4",
    "classification": "Romance Scam",
    "confidence": 0.92
  }
}
```

---

### Custom Metrics

- **Request Rate**: `custom.googleapis.com/i4g/api_requests_per_second`
- **PII Vault Access**: `custom.googleapis.com/i4g/pii_vault_access_count`
- **Classification Accuracy**: `custom.googleapis.com/i4g/classification_accuracy`
- **LEO Reports Generated**: `custom.googleapis.com/i4g/reports_generated_count`

---

### Alerting Policies

1. **High Error Rate**: 5xx errors >5% for 5 minutes
2. **High Latency**: p95 latency >2 seconds for 5 minutes
3. **PII Vault Anomaly**: >100 accesses per minute
4. **Free Tier Quota**: >80% of monthly quota used

---

## Performance Benchmarks

### Response Times (p95)

- `POST /api/cases` (with LLM classification): 3.5 seconds
- `GET /api/cases`: 150 ms
- `GET /api/cases/{id}`: 200 ms
- `POST /api/cases/{id}/approve` (generate report): 2.2 seconds

### Throughput

- **Concurrent users**: 20 (tested with Locust)
- **Cases per day**: 50 (prototype usage)
- **LLM inference**: 5 tokens/second (Ollama on Cloud Run GPU)

---

## Disaster Recovery

### Backup Strategy

```bash
# Daily Firestore export (Cloud Scheduler cron job)
gcloud firestore export gs://i4g-backups/$(date +%Y%m%d) \
  --collection-ids=cases,analysts,pii_vault

# Retention: 7 days
gsutil lifecycle set lifecycle.json gs://i4g-backups
```

**lifecycle.json**:
```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7}
      }
    ]
  }
}
```

---

### Recovery Procedures

**Scenario 1: Accidental case deletion**

```bash
# 1. Find latest backup
gsutil ls gs://i4g-backups/

# 2. Import backup
gcloud firestore import gs://i4g-backups/20251030/
```

**Scenario 2: PII vault corruption**

```bash
# 1. Stop API (prevent further writes)
gcloud run services update i4g-api --no-traffic

# 2. Restore from backup
gcloud firestore import gs://i4g-backups/20251030/ --collection-ids=pii_vault

# 3. Validate restoration
python scripts/validate_pii_vault.py

# 4. Resume traffic
gcloud run services update i4g-api --traffic
```

---

## Technology Stack

### Backend
- **Language**: Python 3.11
- **Framework**: FastAPI 0.104+ (async, type hints)
- **RAG Pipeline**: LangChain 0.2+ (LCEL composition)
- **LLM**: Ollama (llama3.1 8B model, 4-bit quantization)
- **Vector DB**: ChromaDB (local embeddings via nomic-embed-text)

### Frontend
- **Dashboard**: Streamlit 1.28+ (analyst UI)
- **Styling**: Custom CSS (PII redaction, responsive design)

### Cloud Infrastructure
- **Hosting**: Google Cloud Platform
  - Cloud Run (API + dashboard)
  - Firestore (NoSQL database)
  - Cloud Storage (file uploads)
  - Secret Manager (API keys, encryption keys)
  - Cloud Logging (structured logs)
  - Cloud Monitoring (metrics + alerts)

### CI/CD
- **Version Control**: GitHub
- **CI Pipeline**: GitHub Actions
  - Lint (black, isort, mypy)
  - Test (pytest, 80% coverage)
  - Build (Docker image)
  - Deploy (Cloud Run via gcloud CLI)

---

## Future Architecture Improvements

### Phase 2 (Post-MVP)
- [ ] Add Redis caching layer (reduce Firestore reads)
- [ ] Implement async task queue (Celery + Cloud Tasks)
- [ ] Multi-region deployment (us-central1 + europe-west1)
- [ ] CDN for static assets (Cloud CDN)

### Phase 3 (Scale)
- [ ] Microservices split (auth, classification, report generation)
- [ ] Event-driven architecture (Pub/Sub)
- [ ] Real-time analytics dashboard (BigQuery + Data Studio)
- [ ] Mobile app (React Native)

---

## Questions & Support

- Maintainer: Jerry Soung (jerry.soung@gmail.com)
- Documentation: https://github.com/jsoung/i4g/tree/main/docs
- API Docs: https://api.i4g.org/docs

---

**Last Updated**: 2025-10-30<br/>
**Next Review**: 2026-01-30
