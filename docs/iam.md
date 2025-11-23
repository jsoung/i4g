# Identity & Access Management Strategy

**Status:** Draft (v0.1) — November 21, 2025
**Audience:** Engineering, security reviewers, product stakeholders across `proto`, `planning`, and `ui`

This document is the single source of truth for how we authenticate users, authorize workloads, and evolve IAM across the i4g platform. It consolidates IAM content from `architecture.md`, planning artifacts, and the UI books so every repository references one canonical strategy. Updates to IAM MUST originate here.

---

## 1. Objectives and Scope

1. **Protect victims and analysts** — tokenize PII, gate privileged tooling, and log every access.
2. **Support multiple personas** — victims/end users, volunteer analysts, law enforcement (LEO), and automated jobs.
3. **Enable fast iteration** — today’s prototype runs entirely on Cloud Run with Google Identity; we need a pragmatic stopgap while designing the long-term zero-trust model.
4. **Document the path forward** — outline future-state controls (VPN, per-role endpoints, self-serve IAM) even if unimplemented.

**Covered repositories:** `proto/`, `planning/`, `ui/`, `infra/`. Any IAM mention in other docs must reference this file.

---

## 2. Personas & Role Expectations

| Persona | Capabilities | Entry Requirements | Near-term Controls | Future Controls |
| --- | --- | --- | --- | --- |
| Victim / End User | Submit cases, upload evidence, check status | Google account (temporary), future passkey/email options | Cloud Run IAM via Google tokens, signed URLs for uploads | Dedicated intake endpoint with anti-abuse, CAPTCHA, fraud throttling |
| Analyst | Review cases, run RAG search, generate reports | Google account in Analyst group, future VPN cert | Cloud Run IAM + Google Group membership, Terraform-managed bindings | Analyst-only endpoint behind VPN / BeyondCorp + device posture checks |
| Law Enforcement (LEO) | Search approved cases, download reports | Provisioned Google account, MFA | Google Identity + role claim, signed report URLs | Dedicated LEO portal with read-only scope + case export formats |
| Automation (jobs) | Ingest feeds, generate reports, rotate secrets | Service accounts only | Terraform service accounts (`sa-ingest`, `sa-report`, etc.) with least privilege | Same accounts, plus workload-identity federation to CI/CD |

---

## 3. Service & Endpoint Matrix

| Service | Purpose | URL (dev) | IAM Owner | Notes |
| --- | --- | --- | --- | --- |
| FastAPI Gateway | API for intake, review, reports | `https://fastapi-gateway-y5jge5w2cq-uc.a.run.app/` | `sa-app` runtime | Protected by Identity-Aware Proxy (IAP). 404 at `/` is expected. |
| Streamlit Operations Console | Internal dashboards & queues | `https://streamlit-analyst-ui-y5jge5w2cq-uc.a.run.app/` | `sa-app` runtime | Protected by IAP; analysts/admins only. |
| Next.js Analyst Console | External portal | `https://i4g-console-y5jge5w2cq-uc.a.run.app/` | `sa-app` runtime | Protected by IAP; uses FastAPI APIs under the hood. |

All three application services currently reuse the shared runtime service account (`sa-app`). Terraform now owns both the Cloud Run `roles/run.invoker` binding (runtime + IAP service agent) and the IAP `roles/iap.httpsResourceAccessor` policy via the `i4g_analyst_members` input.

---

## 4. Authentication Strategy

### 4.1 Current State — IAP in front of every Cloud Run surface
- **Identity-Aware Proxy (IAP)** now fronts every Cloud Run service (FastAPI, Streamlit, Analyst Console). Each service may remain `--allow-unauthenticated` at the Cloud Run layer, but IAP blocks requests before they reach the service unless the caller is signed in with an approved Google account.
- **Browser experience:** Users hit the Cloud Run HTTPS endpoint, IAP redirects them to Google sign-in (if they are not already signed in), and—after verifying membership in the `roles/iap.httpsResourceAccessor` policy—the request is forwarded to Cloud Run with contextual headers (`X-Goog-Authenticated-User-Email`, signed JWT if enabled).
- **Access management:** Terraform manages the Cloud Run + IAP IAM policies (fed by `i4g_analyst_members`). It can also provision the IAP brand/OAuth clients when the project belongs to an organization, but that path is disabled by default because our dev/prod projects are standalone. Short-lived exceptions can still be layered on manually via Google Group changes or `gcloud iap web add-iam-policy-binding`, but Terraform remains the source of truth (§6).
- **CLI / service integrations:** Engineers can still run `gcloud auth print-identity-token --audiences=<run-url>` and call Cloud Run programmatically. When invoking through IAP, include the `X-Goog-IAP-JWT-Assertion` header (gcloud and client libraries handle this automatically). For debugging, you may also bypass IAP by running the service locally with mock auth.

### 4.2 Medium-Term Enhancements (in parallel)
- Replace per-user bindings with Google Group bindings (`group:i4g-analysts@googlegroups.com`, `group:i4g-leo@...`) so onboarding/offboarding requires only Workspace group membership changes.
- Add device-based checks by pairing IAP with BeyondCorp Enterprise or Context-Aware Access policies (post-Milestone 3).
- Introduce per-persona Cloud Run services, each with its own IAP policy and rate limits, to isolate analyst vs. LEO experiences.

### 4.3 Future-State Principles
- **Role-specific endpoints:** separate Cloud Run services (or distinct URL paths) for Victim, Analyst, and LEO experiences, each with unique IAM claims and throttling settings.
- **VPN / Zero-Trust Network Access for Analysts:** use BeyondCorp Enterprise, Cloud VPN + Identity-Aware Proxy, or another certificate-based solution. Documented as TBD; decision deferred until load justifies the investment.
- **Non-Google identity options:** evaluate passkeys or external IdPs (Auth0 for Nonprofits, Okta) to accommodate victims without Google accounts.

---

## 5. Authorization & Service Accounts

1. **Runtime Service Accounts**
   - `sa-app`: shared by FastAPI, Streamlit, and the Next.js analyst console. Roles: `roles/datastore.user`, `roles/storage.objectViewer`, `roles/secretmanager.secretAccessor`, `roles/run.invoker` (self), `roles/logging.logWriter`, plus Discovery Engine search role.
   - `sa-ingest`, `sa-report`, `sa-vault`, `sa-infra`: keep existing least-privilege grants (see Terraform modules).

2. **Cloud Run + IAP Policy Management**
   - Terraform now manages both the Cloud Run `roles/run.invoker` binding (runtime service account + IAP service agent + any extra service accounts) *and* the IAP `roles/iap.httpsResourceAccessor` policy for each service. Both derive from `i4g_analyst_members` plus optional per-service overrides.
   - Requirement: maintain this list via tfvars or Google Groups; avoid manual IAM edits so Terraform remains authoritative.

3. **Data Plane Permissions**
   - Firestore: analysts read only assigned cases; PII vault locked to backend service account.
   - Cloud Storage: uniform bucket-level access; signed URLs for user downloads/uploads.
   - Vertex AI Search / future vector stores: custom roles bound to runtime SAs.
   - Secret Manager: versioned secrets per service account; rotate quarterly.

4. **Audit & Monitoring**
   - Cloud Audit Logs retained ≥400 days.
   - Daily Terraform drift check (planned).
   - Streaming alerts for IAM policy changes, authentication failures, and Quick Auth Portal usage anomalies.

---

## 6. Identity-Aware Proxy (IAP) Configuration

IAP is now the ingress layer for every Cloud Run HTTPS endpoint. The helper SPA has been removed; instead, analysts hit the standard Cloud Run URLs and IAP gates access.

### 6.1 Terraform-managed configuration
- `infra/modules/iap/project` wires project-level access defaults (allowed domains, HTTP OPTIONS). When `iap_manage_brand=true` (only possible if the project belongs to an organization), it will also create/manage the brand; otherwise it simply reuses the manually created brand name.
- `infra/modules/iap/cloud_run_service` always manages the `roles/iap.httpsResourceAccessor` bindings derived from `i4g_analyst_members`. When `iap_manage_clients=true`, it additionally creates per-service OAuth clients and Secret Manager entries; for standalone projects we leave this disabled and rely on Google’s default IAP client.
- Every environment now requires the following tfvars before planning:
   - `iap_support_email` — verified Workspace/Gmail address (only used when managing the brand but kept for parity).
   - `iap_application_title` *(optional)* — consent screen title.
   - `iap_manage_brand`, `iap_existing_brand_name`, `iap_manage_clients` *(optional)* — feature toggles described above.
   - `iap_secret_replication_locations` *(optional)* — list of regions for the stored secrets (defaults to the Cloud Run region).
- Terraform automatically grants Cloud Run `roles/run.invoker` to the shared runtime service account plus the IAP service agent so the proxy can reach the backend. Only service-to-service callers should be added via the legacy `*_invoker_members` variables.
- Outputs (`terraform output iap`) expose the brand name plus optional OAuth client metadata (null until `iap_manage_clients=true`).
- Drift management: rerun `terraform plan -var-file=terraform.tfvars` whenever group membership changes to confirm the policy is still aligned; record ad-hoc manual bindings in `planning/change_log.md`.

### 6.2 Manual overrides / break-glass
Terraform is the source of truth, but if we need an emergency change before a plan/apply cycle finishes, use the stock `gcloud` commands:

1. **Enable IAP for a service** (only if Terraform hasn’t already done so):
      ```bash
      gcloud iap web enable \
         --resource-type=run \
         --service=i4g-console \
         --project=i4g-dev \
         --region=us-central1
      ```
2. **Grant access to a group or user** (remember to capture the change in `planning/change_log.md` and back-port to Terraform tfvars):
      ```bash
      gcloud iap web add-iam-policy-binding \
         --resource-type=run \
         --service=i4g-console \
         --project=i4g-dev \
         --region=us-central1 \
         --member=group:i4g-analysts@googlegroups.com \
         --role=roles/iap.httpsResourceAccessor
      ```
3. **Repeat for FastAPI and Streamlit** as needed; Terraform will reconcile the bindings on the next apply.

### 6.3 Consuming identity inside the app
- FastAPI can trust IAP headers (`X-Goog-Authenticated-User-Email`) for lightweight auditing, but authorization decisions should still use Firestore roles. If you need cryptographic verification, enable signed headers in IAP and verify the JWT using the documented audience.
- Command-line scripts can continue to call Cloud Run directly with `gcloud auth print-identity-token` as long as the caller account is part of the IAP policy.

---

## 7. Future IAM Roadmap

| Phase | Timeline (est.) | Deliverables |
| --- | --- | --- |
| **Phase 0 (Now)** | Dec 2025 | Publish this IAM strategy, remove the Quick Auth helper, gate every Cloud Run service behind Terraform-managed IAP, document troubleshooting. |
| **Phase 1** | Q1 2026 | Integrate GIS + Authorization headers directly into Next.js and Streamlit UIs; remove reliance on GAIA cookies; add low-risk law-enforcement read-only views. |
| **Phase 2** | Q2 2026 | Introduce role-specific Cloud Run services (victim intake, analyst tools, LEO portal). Enforce analyst access through VPN/Zero-Trust access, log device posture, and expand auditing. |
| **Phase 3** | Q3 2026 | Evaluate non-Google identity options (passkeys, Auth0 for Nonprofits), finalize automation for IAM drift detection, and implement signed report attestations for legal workflows. |

Open questions to track:
1. Which VPN / ZTNA solution best balances cost and volunteer usability? (BeyondCorp, AppGate, Cloudflare Zero Trust, etc.)
2. How do we onboard law-enforcement partners who cannot use Google accounts? Need alternative IdP integration plan.
3. What compliance requirements (CJIS, HIPAA, etc.) apply, and how do they influence log retention and MFA policies?

---

## 8. Operational Runbook Highlights

- **Group Management:** Manage `i4g-analysts@googlegroups.com` and `i4g-leo@googlegroups.com` manually until we automate via Workspace Admin APIs. Document membership changes in `planning/change_log.md`.
- **Terraform Inputs:** `i4g_analyst_members` list should contain Google Groups, not individuals, after the transition. Keep dev/prod tfvars in sync.
- **Incident Response:** On suspected credential leak, (1) remove the user from the Google Group, (2) rotate secrets via Secret Manager, (3) re-run Terraform to enforce IAM bindings, (4) rotate the IAP OAuth client secret (new Secret Manager version) if needed.
- **Logging & Metrics:** Track `403` responses from Cloud Run; correlate with IAP audit logs to detect auth friction or brute-force attempts.

---

## 9. References

- `docs/architecture.md` — system overview (now defers IAM details to this document).
- `planning/future_architecture.md` — long-term blueprint; IAM sections summarized here.
- `docs/book/api/authentication.md` — references this file for authoritative instructions.
- `infra/` Terraform modules (`iam/`, `run/service`) — enforce the described policies.

*End of document.*
