#!/usr/bin/env python3
"""Generate synthetic retrieval evaluation datasets for Milestone 2 PoCs.

Running this script will populate `data/retrieval_poc/` with:
- `cases.jsonl`: synthetic scam scenarios with structured metadata.
- `ground_truth.yaml`: mapping of evaluation queries to relevant case IDs.
- `manifest.json`: summary metadata describing the run.

The records are intentionally deterministic given a seed so repeated runs are
reproducible. The goal is to provide a representative, non-sensitive dataset
for comparing retrieval backends (Vertex AI Search vs AlloyDB + pgvector).

You can:
- Limit generation to a subset of templates via `--include-templates wallet_verification romance_bitcoin`.
- Supply a JSON configuration describing custom templates via `--template-config path/to/templates.json`.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

AGENT_NAMES = [
    "Anna",
    "Marcus",
    "Linh",
    "Priya",
    "Stefan",
    "Riley",
    "Wei",
    "Camila",
    "Jon",
    "Fatima",
]

VICTIM_NAMES = [
    "Alex",
    "Jordan",
    "Taylor",
    "Morgan",
    "Casey",
    "Avery",
    "Emerson",
    "Reese",
    "Dakota",
    "Skyler",
]

WALLET_PROVIDERS = [
    "TrustWallet Security",
    "Ledger Support Desk",
    "Kraken Account Review",
    "Coinbase Safety Team",
    "Binance Wallet Guard",
]

ROMANCE_ALIASES = [
    "Sofia",
    "Luka",
    "Isabella",
    "Mateo",
    "Elena",
    "Noah",
    "Maya",
    "Diego",
]

ROMANCE_CITIES = [
    "Barcelona",
    "Lisbon",
    "Prague",
    "Buenos Aires",
    "Copenhagen",
]

INVEST_COMMUNITIES = [
    "Phoenix Alpha Circle",
    "Titan Yield Syndicate",
    "Atlas Signal Hub",
    "Nova Chain Collective",
    "Velocity Crypto Room",
]

EMERGING_TOKENS = [
    "SOLRIX",
    "LUMENX",
    "POLAR",
    "RADIANT",
    "NEONIA",
]

TECH_SUPPORT_BRANDS = [
    "Microsoft",
    "Apple",
    "Google",
    "Norton",
    "McAfee",
]

REMOTE_TOOLS = [
    "AnyDesk",
    "TeamViewer",
    "QuickAssist",
    "UltraViewer",
]

IMPOSTOR_AGENCIES = [
    "Internal Revenue Service",
    "Social Security Administration",
    "Department of Labor",
    "HM Revenue & Customs",
    "Australian Taxation Office",
]

RETAILERS = [
    "Amazon",
    "BestBuy",
    "Target",
    "Walmart",
    "Apple Store",
]

GIFT_CARD_BRANDS = [
    "Amazon",
    "Steam",
    "Apple",
    "Google Play",
    "Walmart",
]

CRYPTO_ASSETS = ["USDT", "USDC", "BTC", "ETH", "SOL"]


@dataclass
class TemplateConfig:
    label: str
    category: str
    channel: str
    count: int
    query: str
    notes: str
    tags: List[str]
    keywords: List[str]
    generator: Callable[["TemplateConfig", int, random.Random], Dict[str, object]]


def random_wallet(asset: str, rng: random.Random) -> str:
    if asset == "BTC":
        prefix = rng.choice(["1", "3", "bc1"])
        body = "".join(rng.choices("0123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz", k=30))
        return f"{prefix}{body}"
    if asset in {"USDT", "USDC", "ETH"}:
        body = "".join(rng.choices("0123456789abcdef", k=40))
        return f"0x{body}"
    if asset == "SOL":
        body = "".join(rng.choices("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ", k=32))
        return body
    body = "".join(rng.choices("0123456789ABCDEF", k=32))
    return body


def random_amount(asset: str, rng: random.Random) -> float:
    if asset in {"USDT", "USDC"}:
        return round(rng.uniform(80, 450), 2)
    if asset == "BTC":
        return round(rng.uniform(0.015, 0.18), 5)
    if asset == "ETH":
        return round(rng.uniform(0.25, 4.0), 3)
    if asset == "SOL":
        return round(rng.uniform(5, 40), 2)
    return round(rng.uniform(100, 800), 2)


def make_summary(text: str) -> str:
    snippet = text.strip().split(". ")[0]
    return snippet.strip()


def iso_timestamp(offset_days: int, rng: random.Random) -> str:
    now = datetime.utcnow() - timedelta(days=offset_days)
    shifted = now - timedelta(hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
    return shifted.strftime(ISO_FORMAT)


def wallet_verification_generator(cfg: TemplateConfig, idx: int, rng: random.Random) -> Dict[str, object]:
    agent = rng.choice(AGENT_NAMES)
    victim = rng.choice(VICTIM_NAMES)
    provider = rng.choice(WALLET_PROVIDERS)
    asset = rng.choice(CRYPTO_ASSETS)
    amount = random_amount(asset, rng)
    wallet = random_wallet(asset, rng)
    text = (
        f"Hi {victim}, this is {agent} from {provider}. "
        f"We flagged a withdrawal attempt on your wallet. To keep the account active, "
        f"send a verification deposit of {amount} {asset} to {wallet} in the next 15 minutes. "
        "Reply DONE once complete so we can secure your funds."
    )
    return {
        "text": text,
        "summary": make_summary(text),
        "entities": {
            "people": [{"role": "agent", "value": agent}] + [{"role": "victim", "value": victim}],
            "organizations": [{"value": provider}],
            "crypto_assets": [{"value": asset}],
            "wallet_addresses": [{"value": wallet}],
        },
        "tags": cfg.tags + [asset.lower(), "verification"],
        "risk_level": "high",
        "structured_fields": {
            "payment_method": "crypto_transfer",
            "asset": asset,
            "amount": amount,
            "deadline_minutes": 15,
        },
    }


def romance_bitcoin_generator(cfg: TemplateConfig, idx: int, rng: random.Random) -> Dict[str, object]:
    alias = rng.choice(ROMANCE_ALIASES)
    victim = rng.choice(VICTIM_NAMES)
    city = rng.choice(ROMANCE_CITIES)
    asset = rng.choice(["BTC", "USDT", "ETH"])
    amount = random_amount(asset, rng)
    wallet = random_wallet(asset, rng)
    text = (
        f"My love {victim}, the visa office in {city} finally approved us but I must show proof of funds today. "
        f"Please send {amount} {asset} to {wallet}. Once I land we will start our life together. "
        "I am counting every minute until we meet."
    )
    return {
        "text": text,
        "summary": make_summary(text),
        "entities": {
            "people": [{"role": "alias", "value": alias}, {"role": "victim", "value": victim}],
            "locations": [{"value": city}],
            "crypto_assets": [{"value": asset}],
            "wallet_addresses": [{"value": wallet}],
        },
        "tags": cfg.tags + ["romance", asset.lower()],
        "risk_level": "high",
        "structured_fields": {
            "payment_method": "crypto_transfer",
            "asset": asset,
            "amount": amount,
            "pretext": "immigration_fee",
        },
    }


def investment_group_generator(cfg: TemplateConfig, idx: int, rng: random.Random) -> Dict[str, object]:
    community = rng.choice(INVEST_COMMUNITIES)
    token = rng.choice(EMERGING_TOKENS)
    analyst = rng.choice(AGENT_NAMES)
    entry_price = round(rng.uniform(0.08, 0.42), 3)
    target = round(entry_price * rng.uniform(2.5, 4.8), 3)
    text = (
        f"Alert from {community}! Analyst {analyst} confirmed liquidity injection on {token}. "
        f"Buy at ${entry_price} before 21:30 UTC and flip when it hits ${target}. "
        "Screenshots required in chat to verify your position."
    )
    return {
        "text": text,
        "summary": make_summary(text),
        "entities": {
            "organizations": [{"value": community}],
            "people": [{"role": "analyst", "value": analyst}],
            "tokens": [{"value": token}],
        },
        "tags": cfg.tags + [token.lower(), "pump"],
        "risk_level": "medium",
        "structured_fields": {
            "payment_method": "crypto_exchange",
            "token": token,
            "entry_price_usd": entry_price,
            "target_price_usd": target,
            "channel_requirements": "screenshot_verification",
        },
    }


def tech_support_generator(cfg: TemplateConfig, idx: int, rng: random.Random) -> Dict[str, object]:
    brand = rng.choice(TECH_SUPPORT_BRANDS)
    tool = rng.choice(REMOTE_TOOLS)
    ticket_id = f"{rng.randint(100000, 999999)}-{chr(rng.randint(65, 90))}"
    callback = f"+1-888-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
    text = (
        f"{brand} Security Desk: ticket {ticket_id} shows your license expired. "
        f"Install {tool} and share the session code. Once connected we will refund the $349 fee, "
        f"but you must stay on the line. Call {callback} now."
    )
    return {
        "text": text,
        "summary": make_summary(text),
        "entities": {
            "organizations": [{"value": f"{brand} Security Desk"}],
            "software": [{"value": tool}],
            "ticket_ids": [{"value": ticket_id}],
            "phone_numbers": [{"value": callback}],
        },
        "tags": cfg.tags + [brand.lower(), tool.lower()],
        "risk_level": "high",
        "structured_fields": {
            "payment_method": "gift_card_or_wire",
            "fee_amount_usd": 349,
            "requires_remote_access": True,
            "callback_number": callback,
        },
    }


def impostor_refund_generator(cfg: TemplateConfig, idx: int, rng: random.Random) -> Dict[str, object]:
    agency = rng.choice(IMPOSTOR_AGENCIES)
    retailer = rng.choice(RETAILERS)
    amount = rng.randint(1200, 5400)
    transaction_id = f"TX-{rng.randint(100000, 999999)}"
    text = (
        f"{agency} automated notice: your {retailer} refund of ${amount} was returned due to unpaid compliance fees. "
        f"Settle the balance today via government bonds or the levy increases. Reference case {transaction_id} when calling the hotline."
    )
    hotline = f"+1-877-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
    return {
        "text": text,
        "summary": make_summary(text),
        "entities": {
            "agencies": [{"value": agency}],
            "retailers": [{"value": retailer}],
            "transaction_ids": [{"value": transaction_id}],
            "phone_numbers": [{"value": hotline}],
        },
        "tags": cfg.tags + [agency.lower().replace(" ", "-"), "refund"],
        "risk_level": "medium",
        "structured_fields": {
            "payment_method": "prepaid_bonds",
            "fee_amount_usd": amount,
            "hotline": hotline,
            "case_reference": transaction_id,
        },
    }


def gift_card_shakedown_generator(cfg: TemplateConfig, idx: int, rng: random.Random) -> Dict[str, object]:
    executive = rng.choice(AGENT_NAMES)
    victim = rng.choice(VICTIM_NAMES)
    retailer = rng.choice(GIFT_CARD_BRANDS)
    quantity = rng.randint(3, 6)
    value = rng.choice([100, 200, 500])
    text = (
        f"Urgent: it's {executive} from the leadership team. Our investor demo starts in 20 minutes and "
        f"procurement failed to secure the {retailer} gift cards. Buy {quantity} cards worth ${value} each right now, "
        "scratch the codes, and text back photos. We will reimburse you immediately."
    )
    return {
        "text": text,
        "summary": make_summary(text),
        "entities": {
            "people": [{"role": "executive", "value": executive}, {"role": "victim", "value": victim}],
            "retailers": [{"value": retailer}],
        },
        "tags": cfg.tags + [retailer.lower(), "gift-card"],
        "risk_level": "high",
        "structured_fields": {
            "payment_method": "gift_card_codes",
            "card_brand": retailer,
            "card_quantity": quantity,
            "card_value_usd": value,
        },
    }


TEMPLATE_GENERATORS: Dict[str, Callable[[TemplateConfig, int, random.Random], Dict[str, object]]] = {
    "wallet_verification": wallet_verification_generator,
    "romance_bitcoin": romance_bitcoin_generator,
    "investment_group": investment_group_generator,
    "tech_support": tech_support_generator,
    "impostor_refund": impostor_refund_generator,
    "gift_card_shakedown": gift_card_shakedown_generator,
}


DEFAULT_TEMPLATE_SPECS = [
    {
        "label": "wallet_verification",
        "category": "account_takeover",
        "channel": "sms",
        "count": 40,
        "query": "wallet verification crypto deposit scam",
        "notes": "SMS/IM messages demanding a crypto verification payment to keep an account active.",
        "tags": ["crypto", "account-security", "sms"],
        "keywords": ["wallet verification", "suspicious withdrawal", "send crypto"],
        "generator": "wallet_verification",
    },
    {
        "label": "romance_bitcoin",
        "category": "romance_scam",
        "channel": "chat",
        "count": 40,
        "query": "romance scam asking for bitcoin to pay travel documents",
        "notes": "Chat-based romance pretext requesting crypto to cover urgent travel or visa fees.",
        "tags": ["romance", "emotional", "chat"],
        "keywords": ["visa approved", "send bitcoin", "meet soon"],
        "generator": "romance_bitcoin",
    },
    {
        "label": "investment_group",
        "category": "investment_scam",
        "channel": "telegram",
        "count": 40,
        "query": "telegram pump group early entry token signal",
        "notes": "Pump-and-dump alerts from gated trading communities.",
        "tags": ["investment", "telegram", "signals"],
        "keywords": ["liquidity injection", "buy before", "target price"],
        "generator": "investment_group",
    },
    {
        "label": "tech_support",
        "category": "tech_support_scam",
        "channel": "email",
        "count": 40,
        "query": "tech support refund scam remote access install anydesk",
        "notes": "Email/SMS tech-support refund scams requiring remote-control tools.",
        "tags": ["tech-support", "refund", "remote-access"],
        "keywords": ["license expired", "install anydesk", "stay on the line"],
        "generator": "tech_support",
    },
    {
        "label": "impostor_refund",
        "category": "government_impostor",
        "channel": "phone",
        "count": 20,
        "query": "irs refund returned compliance fee bond scam",
        "notes": "Government impostor calls asking for compliance fees via bonds or vouchers.",
        "tags": ["impostor", "government", "phone"],
        "keywords": ["refund returned", "compliance fee", "case reference"],
        "generator": "impostor_refund",
    },
    {
        "label": "gift_card_shakedown",
        "category": "business_email_compromise",
        "channel": "sms",
        "count": 20,
        "query": "urgent executive gift card codes reimbursement",
        "notes": "Executive impersonation demanding bulk gift cards for emergencies.",
        "tags": ["bec", "gift-card", "urgent"],
        "keywords": ["investor demo", "scratch the codes", "reimburse"],
        "generator": "gift_card_shakedown",
    },
]


def _build_template(spec: Dict[str, Any]) -> TemplateConfig:
    label = spec.get("label")
    generator_name = spec.get("generator") or label
    if not label:
        raise ValueError("Template spec missing 'label'.")
    if generator_name not in TEMPLATE_GENERATORS:
        raise ValueError(f"Unknown generator '{generator_name}' for template '{label}'.")
    generator = TEMPLATE_GENERATORS[generator_name]
    tags = spec.get("tags") or []
    keywords = spec.get("keywords") or []
    if isinstance(tags, str):
        tags = [tags]
    if isinstance(keywords, str):
        keywords = [keywords]
    return TemplateConfig(
        label=label,
        category=spec.get("category", "uncategorised"),
        channel=spec.get("channel", "unknown"),
        count=int(spec.get("count", 0)),
        query=spec.get("query", label),
        notes=spec.get("notes", ""),
        tags=list(tags),
        keywords=list(keywords),
        generator=generator,
    )


def get_default_templates() -> Dict[str, TemplateConfig]:
    templates: Dict[str, TemplateConfig] = {}
    for spec in DEFAULT_TEMPLATE_SPECS:
        template = _build_template(spec)
        templates[template.label] = template
    return templates


def load_templates(config_path: Path | None) -> Dict[str, TemplateConfig]:
    if config_path is None:
        return get_default_templates()

    if not config_path.exists():
        raise FileNotFoundError(f"Template config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict) or "templates" not in data:
        raise ValueError("Template config must be a JSON object with a 'templates' list.")

    templates: Dict[str, TemplateConfig] = {}
    for item in data.get("templates", []):
        if not isinstance(item, dict):
            raise ValueError("Each template entry must be an object.")
        template = _build_template(item)
        templates[template.label] = template

    if not templates:
        raise ValueError("No templates defined in configuration file.")

    return templates


def select_templates(
    templates: Dict[str, TemplateConfig], include_labels: Sequence[str] | None
) -> List[TemplateConfig]:
    if include_labels:
        missing = [label for label in include_labels if label not in templates]
        if missing:
            raise ValueError(f"Requested templates not found: {', '.join(missing)}")
        return [templates[label] for label in include_labels]

    return list(templates.values())


def escape_yaml(value: str) -> str:
    return value.replace('"', '\\"')


def build_dataset(
    templates: Sequence[TemplateConfig], output_dir: Path, seed: int, cases_per_template: int | None
) -> None:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, object]] = []
    distribution = []

    for cfg in templates:
        count = cases_per_template if cases_per_template is not None else cfg.count
        template_records: List[Dict[str, object]] = []
        for idx in range(count):
            case_id = f"{cfg.label}-{idx:03d}"
            payload = cfg.generator(cfg, idx, rng)
            timestamp = iso_timestamp(rng.randint(2, 180), rng)
            tags = sorted({*payload.get("tags", []), cfg.category, cfg.channel})
            metadata = {
                "template": cfg.label,
                "keywords": cfg.keywords,
                "seed_index": idx,
            }
            extra_metadata = payload.get("extra_metadata")
            if isinstance(extra_metadata, dict):
                metadata.update(extra_metadata)

            record = {
                "case_id": case_id,
                "category": cfg.category,
                "channel": cfg.channel,
                "summary": payload.get("summary"),
                "text": payload.get("text"),
                "entities": payload.get("entities", {}),
                "tags": tags,
                "timestamp": timestamp,
                "risk_level": payload.get("risk_level", "medium"),
                "ground_truth_label": cfg.label,
                "language": "en",
                "structured_fields": payload.get("structured_fields", {}),
                "metadata": metadata,
            }
            template_records.append(record)
        records.extend(template_records)
        distribution.append({"label": cfg.label, "count": count, "category": cfg.category, "channel": cfg.channel})

    rng.shuffle(records)

    cases_path = output_dir / "cases.jsonl"
    with cases_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    manifest = {
        "generated_at": datetime.utcnow().strftime(ISO_FORMAT),
        "seed": seed,
        "total_records": len(records),
        "templates": distribution,
        "output": str(cases_path.relative_to(output_dir.parent)),
        "version": "synthetic-v1",
    }
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    queries = []
    for cfg in templates:
        relevant_ids = [rec["case_id"] for rec in records if rec["ground_truth_label"] == cfg.label]
        queries.append(
            {
                "id": cfg.label,
                "text": cfg.query,
                "notes": cfg.notes,
                "tags": cfg.tags,
                "relevant_case_ids": relevant_ids,
            }
        )

    yaml_lines = ["version: 1", f"generated_at: '{manifest['generated_at']}'", "queries:"]
    for item in queries:
        yaml_lines.append(f"  - id: {item['id']}")
        yaml_lines.append(f"    text: \"{escape_yaml(item['text'])}\"")
        yaml_lines.append(f"    notes: \"{escape_yaml(item['notes'])}\"")
        yaml_lines.append("    tags:")
        for tag in item["tags"]:
            yaml_lines.append(f"      - {tag}")
        yaml_lines.append("    relevant_case_ids:")
        for cid in item["relevant_case_ids"]:
            yaml_lines.append(f"      - {cid}")
    yaml_content = "\n".join(yaml_lines) + "\n"
    with (output_dir / "ground_truth.yaml").open("w", encoding="utf-8") as fh:
        fh.write(yaml_content)

    print(f"✅ Generated {len(records)} cases at {cases_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare synthetic retrieval evaluation dataset")
    parser.add_argument("--output-dir", default="data/retrieval_poc", help="Directory to store dataset artifacts")
    parser.add_argument("--seed", type=int, default=20251110, help="Random seed for reproducibility")
    parser.add_argument(
        "--cases-per-template",
        type=int,
        default=None,
        help="Override number of cases per template (default uses template-specific counts)",
    )
    parser.add_argument(
        "--include-templates",
        nargs="+",
        help="Subset of template labels to generate (defaults to all available templates).",
    )
    parser.add_argument(
        "--template-config",
        help="Path to JSON file that defines templates (overrides the built-in archetypes).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    config_path = Path(args.template_config).expanduser() if args.template_config else None
    templates_map = load_templates(config_path)
    templates = select_templates(templates_map, args.include_templates)
    build_dataset(templates, output_dir=output_dir, seed=args.seed, cases_per_template=args.cases_per_template)


if __name__ == "__main__":
    main()
