# Public-Facing Infrastructure TODO (docs.i4g.io / app.i4g.cloud / GitHub org)

Last updated: 2025-11-05

This is a short, shareable todo for setting up public-facing infrastructure for i4g. Save this as a reference and pick up items when you have time.

## Objectives
- Launch a public documentation site: `docs.i4g.io` (Docusaurus or MkDocs)
- Launch a hosted app: `app.i4g.cloud` (Cloud Run + Firebase Auth)
- Create a GitHub organization and repo conventions for i4g development

---

## Tasks

- [ ] Decide domain names and GitHub org
  - Options for GitHub org: `i4g`, `intelligence-for-good`, `intel-for-good`.
  - Choose whether to use `i4g.org` subdomains (e.g., `docs.i4g.org`) or `i4g.io`/`i4g.cloud`.
  - Note: choose a short, recognizable org name if available (keeps repo links short).

- [ ] Scaffold docs site
  - Repo: `i4g/docs`
  - Tech: Docusaurus (React) or MkDocs (Python) — Docusaurus recommended for extensibility.
  - CI/CD: GitHub Actions building and deploying to GitHub Pages or Cloud Run + Cloud CDN.
  - Content skeleton: Quickstart, Architecture, API, Contributing, FAQ.

- [ ] Scaffold hosted app repo
  - Repo: `i4g/app`
  - Deploy: Cloud Run (managed)
  - Auth: Firebase Auth or Cloud Identity for maintainers and users
  - Environments: `i4g-prod`, `i4g-staging` GCP projects (separate billing/credentials)
  - CI/CD: GitHub Actions + Terraform in `infra/` repo for infra-as-code

- [ ] Create `infra` repo and Terraform templates
  - Modules for: Cloud Run service, Cloud Storage buckets, Cloud DNS records, Cloud CDN, Certificate Manager, IAM roles
  - Include a minimal `bootstrap` script for initial project & DNS setup

- [ ] GitHub org & repo standards
  - Create repo templates (service, library, docs)
  - Configure branch protection, issue & PR templates, CODEOWNERS
  - Enable Dependabot, pre-commit hooks, and basic code scanning

- [ ] Security & operations checklist
  - DNS and TLS (use Certificate Manager or managed certificates)
  - Secret storage: Secret Manager; never commit secrets
  - Service accounts: least-privilege roles, separate SA per workload
  - Monitoring: Cloud Monitoring (uptime, errors), Logging exports if needed
  - On-call / runbooks: simple incident process and contact list

- [ ] Community & governance
  - Decide communication channels (docs, forum, Slack/Discord)
  - Create CONTRIBUTING.md, CODE_OF_CONDUCT.md, and LICENSE (MIT recommended)
  - Prepare short onboarding for volunteers (how to get access, repo etiquette)

---

## Notes for volunteers / non-technical stakeholders
- I will prepare short, plain-English status updates weekly (1–2 paragraphs) so volunteers can stay informed without attending meetings.
- The default strategy is to prioritize the docs site first (easy to publish) and then the hosted app.
- I recommend we start with free-tier GCP projects and request nonprofit credits before incurring costs.

---

## Where to start (quick picks)
1. Pick GitHub org name and register it.
2. Reserve DNS for `i4g.org` or `i4g.io` and add `docs` and `app` subdomains.
3. Create `i4g/docs` repo with a Docusaurus starter and a GitHub Action to publish to `docs.i4g.*`.


*Saved in `dtp/system_review/public_infra_todo.md`*