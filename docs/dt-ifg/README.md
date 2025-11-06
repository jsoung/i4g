# DT-IFG Planning Artifacts

_Last updated: 6 Nov 2025_

This folder contains source material from the DT-IFG discovery project and the planning documents that guide the migration to the new i4g platform.

## Inventory
- `system_review.md` — detailed assessment of the current DT-IFG production environment.
- `migration_plan.md` — milestone-based migration strategy (GCP-only focus).
- `gap_analysis.md` — capability matrix comparing DT-IFG vs i4g target stack.
- `technology_evaluation.md` — open-first technology options for identity, retrieval, LLMs, and ops.
- `future_architecture.md` — proposed end-state GCP architecture.
- `implementation_roadmap.md` — workstream breakdown and sequencing for execution.
- `change_log.md` — running log of major planning decisions.
- `doc_site_option.md` — documentation platform comparison for the public-facing site.
- `public_infra_todo.md` — checklist for docs/app hosting and GitHub org setup.
- `discovery-export.sh` — script used to capture GCP asset inventory.

## How to Use This Folder
1. **Planning reference**: Use these docs to seed the new repositories (product code, infra, documentation) as they are created.
2. **Updates**: When decisions change, update the relevant markdown and add an entry to `change_log.md`.
3. **Sharing**: These files are self-contained; copy them into new repos as-needed so volunteers have context.
4. **Archival**: Keep this folder in version control until the migration is complete; afterwards archive in an "ops" or "planning" repo.
