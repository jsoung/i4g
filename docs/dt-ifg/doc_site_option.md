# Documentation Tool Comparison — Volunteer-Friendly Options

Last updated: 2025-11-06

This one-pager compares documentation platforms that work well for small, volunteer-led or nonprofit projects. The goal is a site with: sidebar navigation, search, optional versioning, easy editing, and a low or zero monthly cost.

| Tool | Model & Cost | Key strengths | Ease of use | Best for |
|---|---:|---|---:|---|
| GitBook | SaaS — free for open-source / nonprofit tiers | Visual editor, Git-sync, polished UI, hosted (no infra to run) | Very high | Non-technical and mixed teams who want a premium editing experience without hosting headaches |
| Docusaurus | Open source — self-host or use GitHub Pages / Cloud Run | Powerful features (versioning, localization), React-based extensibility | Medium (requires web/React skills to customize) | Technical teams wanting full control and extensibility |
| Read the Docs + MkDocs | Open source — free hosting options | Simple config (YAML), static-site generation, strong versioning | High (familiar Git workflow) | Projects comfortable with Git-based authoring and seeking fully open-source stack |
| Mintlify | Paid SaaS | AI writing tooling, highly polished docs UI | Very high (but paid) | Teams with budget that want advanced writing features and low maintenance |
| Google Workspace (Docs/Sites) | SaaS — free for many nonprofits | Familiar editor, collaboration, zero ops | Extremely high | Internal knowledge bases or non-technical audiences where ease matters more than a docs-site aesthetic |

## Recommendation — quick pick

- If you want minimal ops and a modern editor: choose GitBook (free for open-source/nonprofit projects). It gives a great experience for volunteers and non-technical contributors.
- If you prefer a fully open-source stack with no vendor lock-in and your contributors are comfortable with Git: choose MkDocs (or Docusaurus if you need React-based customization).

## Notes and next steps

- If you choose GitBook: create an `i4g/docs` repo as the canonical content source and connect it to GitBook (or edit directly in GitBook's editor). Configure a simple redirect from `docs.i4g.*` to the GitBook-hosted domain, or use a custom domain with DNS CNAME.
- If you choose MkDocs/Docusaurus: prepare a repo scaffold with a starter site, GitHub Actions for build + publish (GitHub Pages or Cloud Run + Cloud CDN), and a CONTRIBUTING guide for non-technical editors.
- Consider reserving a short alias domain (e.g., `i4g.org` or `i4g.io`) and set up redirects to the canonical docs domain to make links shorter when sharing.

If you'd like, I can scaffold a Docusaurus starter or generate an MkDocs repo with GitHub Actions configured. Tell me which option you prefer and I'll create the starter repo under `dtp/system_review/` for review.
