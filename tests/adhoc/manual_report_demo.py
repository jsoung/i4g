"""Manual demo: Render an FBI-style scam report using template + dummy data."""

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def render_report(template_name: str, data: dict, output_path: Path):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template(template_name)
    rendered = template.render(**data)
    output_path.write_text(rendered)
    print(f"✅ Report generated at: {output_path}")


if __name__ == "__main__":
    data = {
        "title": "Crypto Investment Scam",
        "case_id": "CASE-2025-001",
        "date": datetime.date.today().isoformat(),
        "summary": "User was contacted through social media promising high crypto returns.",
        "entities": {
            "people": ["John Doe", "Anna Lee"],
            "organizations": ["TrustWallet", "Binance"],
            "wallet_addresses": ["0xAbC...", "1FzWL..."],
        },
        "classification": "Crypto Scam",
        "confidence": 92.5,
        "recommendation": "Escalate to federal review; wallet tracking advised.",
        "evidence": "Screenshot logs and wallet addresses extracted.",
    }

    output_file = Path("data/reports/fbi_report_CASE-2025-001.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    render_report("fbi_template.md.j2", data, output_file)
