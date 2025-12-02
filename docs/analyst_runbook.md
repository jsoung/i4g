# Analyst Runbook — Hybrid Search Filters

Use this runbook whenever you need to operate the hybrid (semantic + structured) search stack, refresh
filter metadata, or migrate saved searches after the Milestone 3 upgrades.

## Audience & Scope
- Volunteer analysts and engineers who triage cases through the FastAPI/Next.js stack.
- Focus areas: structured filters, `/reviews/search/schema`, saved-search lifecycle, and UI alignment.

## Prerequisites
- Access to the FastAPI gateway via Identity-Aware Proxy (see `docs/iam.md`).
- `X-API-KEY` with analyst scope stored in `I4G_API_KEY`.
- Convenience variables set in your shell:
  ```bash
  export FASTAPI_BASE=${FASTAPI_BASE:-https://fastapi-gateway-y5jge5w2cq-uc.a.run.app}
  export I4G_API_KEY=${I4G_API_KEY:-dev-analyst-token}
  ```
- Conda environment `i4g` activated (`conda run -n i4g ...`).
- Optional: `jq` for formatting responses.

## 1. Refresh the Filter Schema
1. Call the schema endpoint to retrieve the latest indicator types, datasets, and presets:
   ```bash
   curl -sS \
     -H "X-API-KEY: $I4G_API_KEY" \
     "$FASTAPI_BASE/reviews/search/schema" | jq . > /tmp/hybrid_schema.json
   ```
2. To regenerate the committed snapshot for UI/dev parity, run:
   ```bash
   conda run -n i4g python scripts/refresh_hybrid_schema_snapshot.py \
     --api-base "$FASTAPI_BASE" \
     --api-key "$I4G_API_KEY"
   ```
   This command rewrites `docs/examples/reviews_search_schema.json`; commit the diff whenever backend schema data changes so UI fixtures stay aligned with prod.
3. Skim the response for:
   - `indicator_types`: entity kinds supported by SQL/Firestore.
   - `datasets`: ingest labels (e.g., `retrieval_poc_dev`, `network_smoke`).
   - `loss_buckets`, `time_presets`, and `entity_examples`: drive UI defaults. `entity_examples` is sampled directly from the latest SQL entities (limit controlled by `search.schema_entity_example_limit`) so values reflect whatever the ingestion pipeline most recently recorded.
4. Share the JSON with UI engineers (commit under `ui/apps/web/src/config/generated/` if schema-driven components require a local snapshot). For convenience, the most recent payload from Dec 1, 2025 lives in `docs/examples/reviews_search_schema.json`.
5. Re-run the command whenever ingestion introduces new entity columns or datasets. If expected datasets are missing, first execute the ingestion smoke in `docs/smoke_test.md#7-network-entities-ingestion-smoke-dev`.

## 2. Compose Advanced Hybrid Searches via API
1. Start from the schema output and build a payload that mirrors `HybridSearchRequest`:
   ```bash
   cat <<'EOF' >/tmp/hybrid_query.json
   {
     "text": "romance wallet",
     "classifications": ["romance"],
     "datasets": ["network_smoke"],
     "loss_buckets": [">50k"],
     "entities": [
       {"type": "crypto_wallet", "value": "bc1q", "match_mode": "prefix"},
       {"type": "browser_agent", "value": "chrome", "match_mode": "contains"}
     ],
     "time_range": {
       "start": "2025-11-01T00:00:00Z",
       "end": "2025-12-01T00:00:00Z"
     },
     "limit": 25,
     "vector_limit": 50,
     "structured_limit": 50,
     "offset": 0
   }
   EOF
   ```
2. Execute the hybrid search endpoint:
   ```bash
   curl -sS \
     -H "X-API-KEY: $I4G_API_KEY" \
     -H "Content-Type: application/json" \
     -X POST "$FASTAPI_BASE/reviews/search/query" \
     --data @/tmp/hybrid_query.json | jq '{count, total, vector_hits, structured_hits, results: (.results[:3])}'
   ```
3. Confirm the response includes:
   - `results`: merged cases annotated with `source` (vertex, structured, merged).
   - `vector_hits` / `structured_hits`: backend-specific hit counts.
   - `diagnostics.filters_applied`: echo of normalized filters for audit.
4. Log the request/response in `planning/change_log.md` if you capture anomalies (missing entities, unexpected dataset coverage).

## 3. Operate the Next.js Analyst Console
1. **Local dev:**
   ```bash
   cd ../ui
   pnpm install # once per machine
   I4G_API_URL=$FASTAPI_BASE I4G_API_KEY=$I4G_API_KEY pnpm --filter web dev
   ```
   - Navigate to http://localhost:3000/search.
   - Use the Advanced Filters drawer. Chips are populated from `/reviews/search/schema`. When new indicators appear, restart `pnpm dev` after refreshing `/tmp/hybrid_schema.json`.
2. **Cloud console:** visit `https://i4g-console-y5jge5w2cq-uc.a.run.app/search` (IAP-guarded). Confirm that:
   - Entity chips match the schema output.
   - Dataset selectors include `network_smoke` after the ingestion smoke completes.
   - Saved-search dropdowns render existing entries (see §4) and highlight favorites.
3. **Smoke automation:** run `pnpm --filter web test:smoke` (see `docs/smoke_test.md`) whenever filters or API payloads change. The Playwright script submits a canned hybrid query and verifies that entity facets render.

## 4. Saved-Search Migration Playbook
1. **Export existing searches** (per owner or shared scope):
   ```bash
   conda run -n i4g i4g-admin export-saved-searches \
     --owner $USER \
     --limit 100 \
     --output /tmp/saved_searches_$USER.json
   ```
   Use `--all` instead of `--owner` to include shared entries. The export strips timestamps so you can edit freely.
2. **Update payloads**:
   - Ensure each `params` object matches `HybridSearchRequest` (text, datasets, entities, time_range, etc.).
   - Add the new `entities` array using filter specs from the schema response.
   - Include `time_range` whenever analysts depend on preset windows; use ISO 8601 UTC strings.
   - Tag migrated searches with `"tags": ["hybrid-v1"]` (or similar) to distinguish them.
3. **Import** back into SQLite/Firestore:
   ```bash
   conda run -n i4g i4g-admin import-saved-searches \
     --shared \
     --input /tmp/saved_searches_$USER.json
   ```
   Omit `--shared` to keep ownership. The CLI validates payloads with `SavedSearchImportRequest` before persisting.
4. **Verify**:
   - `curl -sS -H "X-API-KEY: $I4G_API_KEY" "$FASTAPI_BASE/reviews/search/saved" | jq '.items[] | {name, tags, params}'`
   - Load the analyst console and confirm the migrated searches appear in the Saved Search menu.
5. **Cleanup**: remove stale entries with `i4g-admin prune-saved-searches --tags legacy --dry-run` before deleting, then rerun without `--dry-run`.

## 5. Operational Notes & Troubleshooting
- **Filters missing datasets/entities:** Rerun the ingestion smoke (`docs/smoke_test.md#7-network-entities-ingestion-smoke-dev`) and confirm Vertex search holds the new cases (`i4g-admin vertex-search ...`).
- **Schema contract drift:** Regenerate UI fixtures or `apps/web/src/config/schema.ts` after every backend change, and include the schema diff in PR descriptions.
- **Saved-search conflicts:** API returns HTTP 409 when a duplicate name exists for the same owner. Use `i4g-admin bulk-update-tags --add hybrid-v1` to mark converted searches and avoid collisions.
- **Audit logging:** Every `/reviews/search/query` call emits a `search` action in `review_actions`. Use these logs to cross-check analyst activity during incident reviews.
- **Documentation:** When you change the workflow, update this file and `planning/change_log.md` with the run ID, dataset, and any schema deltas.
