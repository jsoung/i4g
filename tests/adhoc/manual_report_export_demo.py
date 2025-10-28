"""
Manual Ad-Hoc Test: Report Generation and Export

This script demonstrates end-to-end generation and export of a fraud report
using the ReportGenerator.

Usage:
    # For local export
    python tests/adhoc/manual_report_export_demo.py
"""
import argparse
from i4g.reports.generator import ReportGenerator

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, default="TrustWallet verification fee", help="Text query to seed the report.")
    args = parser.parse_args()

    print("Initializing report generator...")
    generator = ReportGenerator()

    print(f"Generating report based on query: '{args.query}'")

    result = generator.generate_report(
        text_query=args.query
    )

    print("\n=== Report Generation Complete ===")
    if result.get("report_path"):
        print(f"✅ Local Report Path: {result['report_path']}")
    print("\nSummary:")
    print(result.get("summary"))
    print("\n---")

if __name__ == "__main__":
    main()