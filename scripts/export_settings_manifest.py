"""Generate a manifest of configurable settings and write docs artifacts."""

from __future__ import annotations

import argparse
import json
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence, Union, get_args, get_origin

import yaml
from pydantic.fields import FieldInfo, PydanticUndefined
from pydantic_settings import BaseSettings

from i4g.settings.config import PROJECT_ROOT, Settings

SMOKE_COMMAND = (
    "```bash\n" "conda run -n i4g I4G_PROJECT_ROOT=$PWD I4G_ENV=dev I4G_LLM__PROVIDER=mock i4g-account-job\n" "```"
)

INTRO_TEXT = (
    "Intelligence for Good spans three steady-state runtime profiles, so configuration lives in environment variables "
    "instead of hard-coded values.\n\n"
    "- Local sandbox runs on every developer laptop with mock identity, SQLite/Chroma, and Ollama so feature work stays "
    "fast and offline.\n"
    "- `i4g-dev` hosts the shared cloud deployment used for integration tests and stakeholder demos.\n"
    "- `i4g-prod` serves analysts and partners; it must stay isolated from experimental changes.\n\n"
    "Documenting every knob keeps contributors from accidentally pointing laptop jobs at production data while still "
    "letting us iterate quickly without the cost or latency of cloud resources.\n\n"
    "Usage guidance for developers and sysadmins:\n\n"
    "1. Prefer the `I4G_*` env vars when exporting values; legacy aliases exist only for backwards compatibility.\n"
    "2. When adding or changing a setting, update `src/i4g/settings/config.py`, extend "
    "`tests/unit/settings/`, and rerun `python scripts/export_settings_manifest.py` (pass `--docs-repo ../docs` when the "
    "docs checkout is available) before committing.\n"
    "3. Store credentials in `.env.local` or Secret Manager rather than committing secrets here; laptop runs can source "
    "the file via `direnv` or the built-in dotenv loader.\n"
    "4. Keep `I4G_ENV=local` for sandbox testing; other values assume GCP services (Firestore, Cloud Storage, Vertex AI) "
    "are reachable.\n"
    "5. Machine-readable manifests live next to this page (`docs/config/settings_manifest.{json,yaml}` in proto, "
    "`config/settings.yaml` in the docs site) for automation and CI validation.\n\n"
    "This catalog is assembled by `proto/scripts/export_settings_manifest.py` directly from "
    "`src/i4g/settings/config.py`. The descriptions below are automatically generated—do not hand-edit them; change the "
    "implementation defaults and rerun the exporter instead."
)


@dataclass(slots=True)
class SettingRecord:
    """Flattened view of a single settings field."""

    path: str
    section: str
    type: str
    default: Any
    env_vars: list[str]
    description: str

    def as_jsonable(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the record."""

        return {
            "path": self.path,
            "section": self.section,
            "type": self.type,
            "default": _serialize_value(self.default),
            "env_vars": self.env_vars,
            "description": self.description,
        }


def _serialize_value(value: Any) -> Any:
    """Convert arbitrary defaults into JSON-friendly primitives."""

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(v) for v in value]
    return str(value)


def _type_to_string(annotation: Any) -> str:
    """Return a human-readable representation of a type annotation."""

    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type):
            return annotation.__name__
        return str(annotation)

    if origin in (types.UnionType, Union):
        return " | ".join(_type_to_string(arg) for arg in get_args(annotation))

    args = get_args(annotation)
    if origin is list:
        inner = ", ".join(_type_to_string(arg) for arg in args) or "Any"
        return f"list[{inner}]"
    if origin is tuple:
        inner = ", ".join(_type_to_string(arg) for arg in args) or "Any"
        return f"tuple[{inner}]"
    if origin.__module__ == "typing" and origin.__qualname__ == "Literal":
        return "Literal[" + ", ".join(repr(arg) for arg in args) + "]"

    args_repr = ", ".join(_type_to_string(arg) for arg in args)
    name = getattr(origin, "__name__", str(origin))
    return f"{name}[{args_repr}]" if args_repr else name


def _unwrap_annotation(annotation: Any) -> Any:
    """Return the underlying type for Annotated/typing constructs."""

    origin = get_origin(annotation)
    if origin is None:
        return annotation
    if origin.__module__ == "typing" and origin.__qualname__ == "Annotated":
        return get_args(annotation)[0]
    return annotation


def _is_settings_model(annotation: Any) -> bool:
    """Return True if annotation points to a BaseSettings subclass."""

    annotation = _unwrap_annotation(annotation)
    return isinstance(annotation, type) and issubclass(annotation, BaseSettings)


def _field_default(field: FieldInfo) -> Any:
    """Retrieve the declared default for a field."""

    if field.default is not PydanticUndefined:
        return field.default
    if field.default_factory is not None:  # type: ignore[truthy-function]
        return field.default_factory()
    return None


def _canonical_env(path: Sequence[str], env_prefix: str, env_delim: str) -> str:
    """Build the canonical env var name for the given path."""

    parts = env_delim.join(part.upper() for part in path)
    return f"{env_prefix}{parts}" if env_prefix else parts


def _alias_choices(field: FieldInfo) -> list[str]:
    """Return any additional alias choices for a field."""

    alias = getattr(field, "validation_alias", None)
    if alias is None:
        return []
    choices = getattr(alias, "choices", None)
    if not choices:
        return [str(alias)]
    return list(choices)


def _collect_records(
    model: type[BaseSettings],
    *,
    path_prefix: Sequence[str],
    env_prefix: str,
    env_delim: str,
    section_description: str,
) -> list[SettingRecord]:
    records: list[SettingRecord] = []
    for name, field in model.model_fields.items():
        if bool(getattr(field, "exclude", False)):
            continue
        annotation = _unwrap_annotation(field.annotation)
        if _is_settings_model(annotation):
            nested = annotation if isinstance(annotation, type) else get_origin(annotation)
            nested_desc = (nested.__doc__ or "").strip() if nested else section_description
            records.extend(
                _collect_records(
                    nested,  # type: ignore[arg-type]
                    path_prefix=(*path_prefix, name),
                    env_prefix=env_prefix,
                    env_delim=env_delim,
                    section_description=nested_desc or section_description,
                )
            )
            continue

        path = (*path_prefix, name)
        section = path[0]
        canonical_env = _canonical_env(path, env_prefix, env_delim)
        aliases = _alias_choices(field)
        env_names = [canonical_env] + [alias for alias in aliases if alias != canonical_env]
        default_value = _field_default(field)
        description = field.description or section_description
        records.append(
            SettingRecord(
                path=".".join(path),
                section=section,
                type=_type_to_string(field.annotation),
                default=default_value,
                env_vars=env_names,
                description=description,
            )
        )
    return records


def build_manifest() -> list[SettingRecord]:
    """Walk the Settings model and collect flattened field metadata."""

    env_prefix = Settings.model_config.get("env_prefix", "") or ""
    env_delim = Settings.model_config.get("env_nested_delimiter", "__") or "__"
    manifest: list[SettingRecord] = []
    section_desc = (Settings.__doc__ or "").strip()
    manifest.extend(
        _collect_records(
            Settings,
            path_prefix=(),
            env_prefix=env_prefix,
            env_delim=env_delim,
            section_description=section_desc,
        )
    )
    manifest.sort(key=lambda record: record.path)
    return manifest


def write_json(records: list[SettingRecord], output_dir: Path) -> Path:
    """Write the JSON manifest to the given directory."""

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "src/i4g/settings/config.py",
        "env_prefix": Settings.model_config.get("env_prefix", "") or "",
        "fields": [record.as_jsonable() for record in records],
    }
    path = output_dir / "settings_manifest.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_yaml(records: list[SettingRecord], output_dir: Path) -> Path:
    """Write the YAML manifest."""

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "src/i4g/settings/config.py",
        "env_prefix": Settings.model_config.get("env_prefix", "") or "",
        "fields": [record.as_jsonable() for record in records],
    }
    path = output_dir / "settings_manifest.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def render_markdown(records: list[SettingRecord], *, title: str, intro: str, postscript: str | None = None) -> str:
    """Render settings metadata into a Markdown table."""

    table = _render_table_markdown(records)
    content = f"# {title}\n\n" + intro + "\n\n" + table + "\n"
    if postscript:
        content += "\n" + postscript.strip() + "\n"
    return content


def _render_table_markdown(records: list[SettingRecord]) -> str:
    """Return a Markdown table representing the settings."""

    header = "| Section | Setting | Env Vars | Type | Default | Description |"
    divider = "| --- | --- | --- | --- | --- | --- |"
    rows: list[str] = []
    for record in records:
        section = _sanitize_cell(record.section)
        setting = _format_code_cell(record.path)
        env_block = "<br />".join(_format_code_cell(env) for env in record.env_vars)
        type_repr = _format_code_cell(record.type)
        default_repr = _format_code_cell(_format_default(record.default))
        description = _sanitize_cell(record.description)
        row = " | ".join([section, setting, env_block, type_repr, default_repr, description])
        rows.append(f"| {row} |")
    return "\n".join([header, divider, *rows])


def _sanitize_cell(value: str) -> str:
    """Escape Markdown table delimiters while preserving readability."""

    text = str(value)
    escaped = text.replace("|", "&#124;")
    return escaped.replace("\n", "<br />")


def _format_code_cell(value: str) -> str:
    """Render the provided value as inline code with safe escaping."""

    sanitized = _sanitize_cell(value).replace("`", "\\`")
    return f"`{sanitized}`"


def write_markdown(records: list[SettingRecord], output_dir: Path) -> Path:
    """Write the default Markdown table to the proto docs directory."""

    postscript = "## Local Account-List Smoke\n\n" + SMOKE_COMMAND
    content = render_markdown(
        records,
        title="Settings & Environment Variables",
        intro=INTRO_TEXT,
        postscript=postscript,
    )
    path = output_dir / "README.md"
    path.write_text(content, encoding="utf-8")
    return path


def _format_default(value: Any) -> str:
    """Convert the default into a string without introducing table delimiters."""

    serialized = _serialize_value(value)
    if isinstance(serialized, str):
        return serialized
    if isinstance(serialized, list):
        return json.dumps(serialized)
    if serialized is None:
        return "None"
    return str(serialized)


def ensure_directory(path: Path) -> Path:
    """Create the directory if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def write_docs_repo(records: list[SettingRecord], docs_repo: Path) -> None:
    """Write Markdown/YAML copies into the docs repository if requested."""

    book_dir = ensure_directory(docs_repo / "book" / "config")
    md_path = book_dir / "settings.md"
    yaml_path = book_dir / "settings.yaml"
    md_content = render_markdown(
        records,
        title="Runtime & Environment Variables",
        intro=INTRO_TEXT,
        postscript=None,
    )
    md_path.write_text(md_content, encoding="utf-8")
    yaml_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fields": [record.as_jsonable() for record in records],
    }
    yaml_path.write_text(yaml.safe_dump(yaml_payload, sort_keys=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proto-docs-dir",
        type=Path,
        default=PROJECT_ROOT / "docs" / "config",
        help="Directory (inside proto) where manifest outputs should be written.",
    )
    parser.add_argument(
        "--docs-repo",
        type=Path,
        default=None,
        help="Optional path to the docs repository root to mirror outputs.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for CLI usage."""

    args = parse_args()
    records = build_manifest()
    target_dir = ensure_directory(args.proto_docs_dir)
    write_json(records, target_dir)
    write_yaml(records, target_dir)
    write_markdown(records, target_dir)
    if args.docs_repo:
        write_docs_repo(records, args.docs_repo)


if __name__ == "__main__":
    main()
