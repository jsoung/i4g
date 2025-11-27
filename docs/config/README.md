# Settings & Environment Variables

Intelligence for Good spans three steady-state runtime profiles, so configuration lives in environment variables instead of hard-coded values.

- Local sandbox runs on every developer laptop with mock identity, SQLite/Chroma, and Ollama so feature work stays fast and offline.
- `i4g-dev` hosts the shared cloud deployment used for integration tests and stakeholder demos.
- `i4g-prod` serves analysts and partners; it must stay isolated from experimental changes.

Documenting every knob keeps contributors from accidentally pointing laptop jobs at production data while still letting us iterate quickly without the cost or latency of cloud resources.

Usage guidance for developers and sysadmins:

1. Prefer the `I4G_*` env vars when exporting values; legacy aliases exist only for backwards compatibility.
2. When adding or changing a setting, update `src/i4g/settings/config.py`, extend `tests/unit/settings/`, and rerun `python scripts/export_settings_manifest.py` (pass `--docs-repo ../docs` when the docs checkout is available) before committing.
3. Store credentials in `.env.local` or Secret Manager rather than committing secrets here; laptop runs can source the file via `direnv` or the built-in dotenv loader.
4. Keep `I4G_ENV=local` for sandbox testing; other values assume GCP services (Firestore, Cloud Storage, Vertex AI) are reachable.
5. Machine-readable manifests live next to this page (`docs/config/settings_manifest.{json,yaml}` in proto, `config/settings.yaml` in the docs site) for automation and CI validation.

This catalog is assembled by `proto/scripts/export_settings_manifest.py` directly from `src/i4g/settings/config.py`. The descriptions below are automatically generated—do not hand-edit them; change the implementation defaults and rerun the exporter instead.

| Section | Setting | Env Vars | Type | Default | Description |
| --- | --- | --- | --- | --- | --- |
| account_list | `account_list.api_key` | `I4G_ACCOUNT_LIST__API_KEY`<br />`ACCOUNT_LIST_API_KEY`<br />`ACCOUNT_LIST__API_KEY` | `str &#124; NoneType` | `None` | Account list extraction configuration. |
| account_list | `account_list.artifact_prefix` | `I4G_ACCOUNT_LIST__ARTIFACT_PREFIX`<br />`ACCOUNT_LIST_ARTIFACT_PREFIX`<br />`ACCOUNT_LIST__ARTIFACT_PREFIX` | `str` | `account_list` | Account list extraction configuration. |
| account_list | `account_list.default_formats` | `I4G_ACCOUNT_LIST__DEFAULT_FORMATS`<br />`ACCOUNT_LIST_DEFAULT_FORMATS`<br />`ACCOUNT_LIST__DEFAULT_FORMATS` | `list[str]` | `[]` | Account list extraction configuration. |
| account_list | `account_list.drive_folder_id` | `I4G_ACCOUNT_LIST__DRIVE_FOLDER_ID`<br />`ACCOUNT_LIST_DRIVE_FOLDER_ID`<br />`ACCOUNT_LIST__DRIVE_FOLDER_ID` | `str &#124; NoneType` | `None` | Account list extraction configuration. |
| account_list | `account_list.enable_vector` | `I4G_ACCOUNT_LIST__ENABLE_VECTOR`<br />`ACCOUNT_LIST_ENABLE_VECTOR`<br />`ACCOUNT_LIST__ENABLE_VECTOR` | `bool` | `True` | Account list extraction configuration. |
| account_list | `account_list.enabled` | `I4G_ACCOUNT_LIST__ENABLED`<br />`ACCOUNT_LIST_ENABLED`<br />`ACCOUNT_LIST__ENABLED` | `bool` | `True` | Account list extraction configuration. |
| account_list | `account_list.header_name` | `I4G_ACCOUNT_LIST__HEADER_NAME`<br />`ACCOUNT_LIST_HEADER_NAME`<br />`ACCOUNT_LIST__HEADER_NAME` | `str` | `X-ACCOUNTLIST-KEY` | Account list extraction configuration. |
| account_list | `account_list.max_top_k` | `I4G_ACCOUNT_LIST__MAX_TOP_K`<br />`ACCOUNT_LIST_MAX_TOP_K`<br />`ACCOUNT_LIST__MAX_TOP_K` | `int` | `250` | Account list extraction configuration. |
| account_list | `account_list.require_api_key` | `I4G_ACCOUNT_LIST__REQUIRE_API_KEY`<br />`ACCOUNT_LIST_REQUIRE_API_KEY`<br />`ACCOUNT_LIST__REQUIRE_API_KEY` | `bool` | `True` | Account list extraction configuration. |
| api | `api.base_url` | `I4G_API__BASE_URL`<br />`API_URL`<br />`API__BASE_URL` | `str` | `http://127.0.0.1:8000` | API endpoint configuration shared by CLI + dashboards. |
| api | `api.key` | `I4G_API__KEY`<br />`API_KEY`<br />`API__KEY` | `str` | `dev-analyst-token` | API endpoint configuration shared by CLI + dashboards. |
| data_dir | `data_dir` | `I4G_DATA_DIR` | `Path` | `/Users/jerry/Work/project/i4g/data` | Top-level configuration model with nested sections for each subsystem. |
| env | `env` | `I4G_ENV`<br />`ENV`<br />`ENVIRONMENT`<br />`RUNTIME__ENV` | `str` | `local` | Top-level configuration model with nested sections for each subsystem. |
| identity | `identity.audience` | `I4G_IDENTITY__AUDIENCE`<br />`IDENTITY_AUDIENCE`<br />`IDENTITY__AUDIENCE` | `str &#124; NoneType` | `None` | Identity provider wiring for auth-enabled services. |
| identity | `identity.client_id` | `I4G_IDENTITY__CLIENT_ID`<br />`IDENTITY_CLIENT_ID`<br />`IDENTITY__CLIENT_ID` | `str &#124; NoneType` | `None` | Identity provider wiring for auth-enabled services. |
| identity | `identity.disable_auth` | `I4G_IDENTITY__DISABLE_AUTH`<br />`IDENTITY_DISABLE_AUTH`<br />`IDENTITY__DISABLE_AUTH` | `bool` | `False` | Identity provider wiring for auth-enabled services. |
| identity | `identity.issuer` | `I4G_IDENTITY__ISSUER`<br />`IDENTITY_ISSUER`<br />`IDENTITY__ISSUER` | `str &#124; NoneType` | `None` | Identity provider wiring for auth-enabled services. |
| identity | `identity.provider` | `I4G_IDENTITY__PROVIDER`<br />`IDENTITY_PROVIDER`<br />`IDENTITY__PROVIDER` | `Literal['mock', 'google_identity', 'authentik', 'firebase']` | `mock` | Identity provider wiring for auth-enabled services. |
| ingestion | `ingestion.default_region` | `I4G_INGESTION__DEFAULT_REGION`<br />`INGESTION_DEFAULT_REGION`<br />`INGESTION__DEFAULT_REGION` | `str` | `us-central1` | Scheduler + job configuration for ingestion workflows. |
| ingestion | `ingestion.default_service_account` | `I4G_INGESTION__DEFAULT_SERVICE_ACCOUNT`<br />`INGESTION_SERVICE_ACCOUNT`<br />`INGESTION__SERVICE_ACCOUNT` | `str &#124; NoneType` | `None` | Scheduler + job configuration for ingestion workflows. |
| ingestion | `ingestion.enable_scheduled_jobs` | `I4G_INGESTION__ENABLE_SCHEDULED_JOBS`<br />`INGESTION_ENABLE_SCHEDULED_JOBS`<br />`INGESTION__ENABLE_SCHEDULED_JOBS` | `bool` | `False` | Scheduler + job configuration for ingestion workflows. |
| ingestion | `ingestion.scheduler_project` | `I4G_INGESTION__SCHEDULER_PROJECT`<br />`INGESTION_SCHEDULER_PROJECT`<br />`INGESTION__SCHEDULER_PROJECT` | `str &#124; NoneType` | `None` | Scheduler + job configuration for ingestion workflows. |
| llm | `llm.chat_model` | `I4G_LLM__CHAT_MODEL`<br />`LLM_CHAT_MODEL`<br />`LLM__CHAT_MODEL` | `str` | `llama3` | Large language model provider settings. |
| llm | `llm.ollama_base_url` | `I4G_LLM__OLLAMA_BASE_URL`<br />`OLLAMA_BASE_URL`<br />`LLM__OLLAMA_BASE_URL` | `str` | `http://127.0.0.1:11434` | Large language model provider settings. |
| llm | `llm.provider` | `I4G_LLM__PROVIDER`<br />`LLM_PROVIDER`<br />`LLM__PROVIDER` | `Literal['ollama', 'vertex_ai', 'mock']` | `ollama` | Large language model provider settings. |
| llm | `llm.temperature` | `I4G_LLM__TEMPERATURE`<br />`LLM_TEMPERATURE`<br />`LLM__TEMPERATURE` | `float` | `0.1` | Large language model provider settings. |
| llm | `llm.vertex_ai_location` | `I4G_LLM__VERTEX_AI_LOCATION`<br />`LLM_VERTEX_AI_LOCATION`<br />`LLM__VERTEX_AI__LOCATION` | `str &#124; NoneType` | `us-central1` | Large language model provider settings. |
| llm | `llm.vertex_ai_model` | `I4G_LLM__VERTEX_AI_MODEL`<br />`LLM_VERTEX_AI_MODEL`<br />`LLM__VERTEX_AI__MODEL` | `str &#124; NoneType` | `None` | Large language model provider settings. |
| llm | `llm.vertex_ai_project` | `I4G_LLM__VERTEX_AI_PROJECT`<br />`LLM_VERTEX_AI_PROJECT`<br />`LLM__VERTEX_AI__PROJECT` | `str &#124; NoneType` | `None` | Large language model provider settings. |
| observability | `observability.otlp_endpoint` | `I4G_OBSERVABILITY__OTLP_ENDPOINT`<br />`OBS_OTLP_ENDPOINT`<br />`OBSERVABILITY__OTLP_ENDPOINT` | `str &#124; NoneType` | `None` | Logging, tracing, and metrics configuration. |
| observability | `observability.structured_logging` | `I4G_OBSERVABILITY__STRUCTURED_LOGGING`<br />`OBS_STRUCTURED_LOGGING`<br />`OBSERVABILITY__STRUCTURED_LOGGING` | `bool` | `True` | Logging, tracing, and metrics configuration. |
| observability | `observability.trace_sample_rate` | `I4G_OBSERVABILITY__TRACE_SAMPLE_RATE`<br />`OBS_TRACE_SAMPLE_RATE`<br />`OBSERVABILITY__TRACE_SAMPLE_RATE` | `float` | `0.0` | Logging, tracing, and metrics configuration. |
| project_root | `project_root` | `I4G_PROJECT_ROOT` | `Path` | `/Users/jerry/Work/project/i4g` | Top-level configuration model with nested sections for each subsystem. |
| runtime | `runtime.log_level` | `I4G_RUNTIME__LOG_LEVEL`<br />`LOG_LEVEL`<br />`RUNTIME__LOG_LEVEL` | `str` | `INFO` | Process-level runtime controls. |
| secrets | `secrets.local_env_file` | `I4G_SECRETS__LOCAL_ENV_FILE`<br />`SECRETS_LOCAL_ENV_FILE`<br />`SECRETS__LOCAL_ENV_FILE` | `Path &#124; NoneType` | `None` | Secret resolution strategy (local vs Secret Manager). |
| secrets | `secrets.project` | `I4G_SECRETS__PROJECT`<br />`SECRETS_PROJECT`<br />`SECRETS__PROJECT` | `str &#124; NoneType` | `None` | Secret resolution strategy (local vs Secret Manager). |
| secrets | `secrets.use_secret_manager` | `I4G_SECRETS__USE_SECRET_MANAGER`<br />`SECRETS_USE_SECRET_MANAGER`<br />`SECRETS__USE_SECRET_MANAGER` | `bool` | `False` | Secret resolution strategy (local vs Secret Manager). |
| storage | `storage.cloudsql_database` | `I4G_STORAGE__CLOUDSQL_DATABASE`<br />`CLOUDSQL_DATABASE`<br />`STORAGE__CLOUDSQL__DATABASE` | `str &#124; NoneType` | `None` | Structured + blob storage configuration. |
| storage | `storage.cloudsql_instance` | `I4G_STORAGE__CLOUDSQL_INSTANCE`<br />`CLOUDSQL_INSTANCE`<br />`STORAGE__CLOUDSQL__INSTANCE` | `str &#124; NoneType` | `None` | Structured + blob storage configuration. |
| storage | `storage.evidence_bucket` | `I4G_STORAGE__EVIDENCE_BUCKET`<br />`STORAGE_EVIDENCE_BUCKET`<br />`STORAGE__EVIDENCE_BUCKET` | `str &#124; NoneType` | `None` | Structured + blob storage configuration. |
| storage | `storage.evidence_local_dir` | `I4G_STORAGE__EVIDENCE_LOCAL_DIR`<br />`STORAGE_EVIDENCE_LOCAL_DIR`<br />`STORAGE__EVIDENCE__LOCAL_DIR` | `Path` | `/Users/jerry/Work/project/i4g/data/evidence` | Structured + blob storage configuration. |
| storage | `storage.firestore_collection` | `I4G_STORAGE__FIRESTORE_COLLECTION`<br />`FIRESTORE_COLLECTION`<br />`STORAGE__FIRESTORE__COLLECTION` | `str` | `cases` | Structured + blob storage configuration. |
| storage | `storage.firestore_project` | `I4G_STORAGE__FIRESTORE_PROJECT`<br />`FIRESTORE_PROJECT`<br />`STORAGE__FIRESTORE__PROJECT` | `str &#124; NoneType` | `None` | Structured + blob storage configuration. |
| storage | `storage.reports_bucket` | `I4G_STORAGE__REPORTS_BUCKET` | `str &#124; NoneType` | `None` | Structured + blob storage configuration. |
| storage | `storage.sqlite_path` | `I4G_STORAGE__SQLITE_PATH` | `Path` | `/Users/jerry/Work/project/i4g/data/i4g_store.db` | Structured + blob storage configuration. |
| storage | `storage.structured_backend` | `I4G_STORAGE__STRUCTURED_BACKEND`<br />`STRUCTURED_BACKEND`<br />`STORAGE__STRUCTURED_BACKEND` | `Literal['sqlite', 'firestore', 'cloudsql']` | `sqlite` | Structured + blob storage configuration. |
| vector | `vector.backend` | `I4G_VECTOR__BACKEND`<br />`VECTOR_BACKEND`<br />`VECTOR__BACKEND` | `Literal['chroma', 'faiss', 'pgvector', 'vertex_ai']` | `chroma` | Vector store configuration supporting multiple backends. |
| vector | `vector.chroma_dir` | `I4G_VECTOR__CHROMA_DIR` | `Path` | `/Users/jerry/Work/project/i4g/data/chroma_store` | Vector store configuration supporting multiple backends. |
| vector | `vector.collection` | `I4G_VECTOR__COLLECTION`<br />`VECTOR_COLLECTION`<br />`VECTOR__COLLECTION` | `str` | `i4g_vectors` | Vector store configuration supporting multiple backends. |
| vector | `vector.embedding_model` | `I4G_VECTOR__EMBEDDING_MODEL`<br />`EMBED_MODEL`<br />`VECTOR__EMBED_MODEL` | `str` | `nomic-embed-text` | Vector store configuration supporting multiple backends. |
| vector | `vector.faiss_dir` | `I4G_VECTOR__FAISS_DIR`<br />`VECTOR_FAISS_DIR`<br />`VECTOR__FAISS_DIR` | `Path` | `/Users/jerry/Work/project/i4g/data/faiss_store` | Vector store configuration supporting multiple backends. |
| vector | `vector.pgvector_dsn` | `I4G_VECTOR__PGVECTOR_DSN`<br />`VECTOR_PGVECTOR_DSN`<br />`VECTOR__PGVECTOR__DSN` | `str &#124; NoneType` | `None` | Vector store configuration supporting multiple backends. |
| vector | `vector.vertex_ai_index` | `I4G_VECTOR__VERTEX_AI_INDEX`<br />`VECTOR_VERTEX_AI_INDEX`<br />`VECTOR__VERTEX_AI__INDEX` | `str &#124; NoneType` | `None` | Vector store configuration supporting multiple backends. |
| vector | `vector.vertex_ai_location` | `I4G_VECTOR__VERTEX_AI_LOCATION`<br />`VECTOR_VERTEX_AI_LOCATION`<br />`VECTOR__VERTEX_AI__LOCATION` | `str &#124; NoneType` | `us-central1` | Vector store configuration supporting multiple backends. |
| vector | `vector.vertex_ai_project` | `I4G_VECTOR__VERTEX_AI_PROJECT`<br />`VECTOR_VERTEX_AI_PROJECT`<br />`VECTOR__VERTEX_AI__PROJECT` | `str &#124; NoneType` | `None` | Vector store configuration supporting multiple backends. |

## Local Account-List Smoke

```bash
conda run -n i4g I4G_PROJECT_ROOT=$PWD I4G_ENV=dev I4G_LLM__PROVIDER=mock i4g-account-job
```
