#!/usr/bin/env python3
"""Add Azure migration secrets to Google Secret Manager.

This helper wraps the Secret Manager API so operators can safely rotate the
connection strings and admin keys that power the weekly Azure -> GCP refresh.

Examples:

    # Prompt for each value interactively (recommended for shared terminals)
    python scripts/infra/add_azure_secrets.py --project i4g-dev

    # Read values from environment variables instead of prompting
    AZURE_SQL_CONNECTION_STRING="..." \
    AZURE_STORAGE_CONNECTION_STRING="..." \
    AZURE_SEARCH_ADMIN_KEY="..." \
    python scripts/infra/add_azure_secrets.py --project i4g-dev

    # Force prompts even if environment variables are set
    python scripts/infra/add_azure_secrets.py --project i4g-dev --prompt-only

    # Auto-create the secrets if Terraform hasn't done so yet
    python scripts/infra/add_azure_secrets.py --project i4g-dev --auto-create
"""

from __future__ import annotations

import argparse
import os
from getpass import getpass
from typing import Iterable, List, Optional

from google.api_core import exceptions
from google.cloud import secretmanager

SECRET_SPECS = (
    {
        "secret_id": "azure-sql-connection-string",
        "env_var": "AZURE_SQL_CONNECTION_STRING",
        "prompt": "Azure SQL connection string",
    },
    {
        "secret_id": "azure-storage-connection-string",
        "env_var": "AZURE_STORAGE_CONNECTION_STRING",
        "prompt": "Azure Storage connection string",
    },
    {
        "secret_id": "azure-search-admin-key",
        "env_var": "AZURE_SEARCH_ADMIN_KEY",
        "prompt": "Azure Cognitive Search admin key",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add Secret Manager versions for Azure migration credentials")
    parser.add_argument("--project", default="i4g-dev", help="GCP project that owns the secrets (default: i4g-dev)")
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Always prompt for values, even when environment variables are populated.",
    )
    parser.add_argument(
        "--secrets",
        nargs="*",
        help="Limit updates to specific secret IDs (defaults to all Azure migration secrets).",
    )
    parser.add_argument(
        "--auto-create",
        action="store_true",
        help="Create secrets automatically when they are missing.",
    )
    parser.add_argument(
        "--replication-location",
        help="When auto-creating secrets, use user-managed replication in the given location.",
    )
    return parser.parse_args()


def select_specs(selected: Optional[Iterable[str]]) -> List[dict]:
    if not selected:
        return list(SECRET_SPECS)
    wanted = set(selected)
    specs = [spec for spec in SECRET_SPECS if spec["secret_id"] in wanted]
    missing = wanted.difference({spec["secret_id"] for spec in specs})
    if missing:
        raise ValueError(f"Unknown secret ids requested: {', '.join(sorted(missing))}")
    return specs


def get_secret_value(spec: dict, prompt_only: bool) -> str:
    env_value = None if prompt_only else os.environ.get(spec["env_var"])
    if env_value:
        return env_value
    prompt = f"{spec['prompt']} (input hidden): "
    while True:
        value = getpass(prompt)
        if value.strip():
            return value
        print("Value cannot be empty. Please try again.")


def ensure_secret(
    client: secretmanager.SecretManagerServiceClient,
    project: str,
    secret_id: str,
    *,
    auto_create: bool,
    replication_location: Optional[str],
) -> bool:
    secret_name = client.secret_path(project, secret_id)
    try:
        client.get_secret(request={"name": secret_name})
        return True
    except exceptions.NotFound:
        if not auto_create:
            print(
                "  Secret not found. Terraform normally creates it; rerun with --auto-create if this environment is still bootstrapping."
            )
            return False

        if replication_location:
            replication = {
                "user_managed": {
                    "replicas": [
                        {"location": replication_location},
                    ]
                }
            }
            replication_desc = f"user-managed ({replication_location})"
        else:
            replication = {"automatic": {}}
            replication_desc = "automatic"

        client.create_secret(
            request={
                "parent": f"projects/{project}",
                "secret_id": secret_id,
                "secret": {
                    "replication": replication,
                },
            }
        )
        print(f"  Created secret '{secret_id}' with {replication_desc} replication.")
        return True


def add_version(client: secretmanager.SecretManagerServiceClient, project: str, secret_id: str, value: str) -> str:
    secret_path = client.secret_path(project, secret_id)
    request = secretmanager.AddSecretVersionRequest(
        parent=secret_path,
        payload={"data": value.encode("utf-8")},
    )
    response = client.add_secret_version(request=request)
    return response.name


def main() -> None:
    args = parse_args()
    specs = select_specs(args.secrets)

    client = secretmanager.SecretManagerServiceClient()
    for spec in specs:
        print(f"\nProcessing secret '{spec['secret_id']}'")
        try:
            if not ensure_secret(
                client,
                args.project,
                spec["secret_id"],
                auto_create=args.auto_create,
                replication_location=args.replication_location,
            ):
                continue

            value = get_secret_value(spec, args.prompt_only)
            version_name = add_version(client, args.project, spec["secret_id"], value)
            print(f"Added secret version: {version_name}")
        except exceptions.NotFound:
            print("Secret not found. Ensure Terraform has created it and you have permissions before rerunning.")
        except exceptions.PermissionDenied:
            print("Permission denied. Verify your account can access Secret Manager in this project.")


if __name__ == "__main__":
    main()
