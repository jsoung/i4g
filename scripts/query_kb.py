"""
CLI query interface for scam detection using LangChain + Ollama.
"""

import argparse
import os
import sys
import warnings

from rich.console import Console

# Fix for OpenMP runtime conflict on macOS.
# This must be set before importing numpy, torch, or other libraries that use OpenMP.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from i4g.embedding.embedder import get_embedder
from i4g.rag.pipeline import build_qa_chain
from i4g.store.vector import load_index

console = Console()
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


def ensure_ollama_running() -> bool:
    """Quick connectivity check for Ollama."""
    import subprocess

    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Ask a question about possible scams.")
    parser.add_argument("question", type=str, help="User question text")
    args = parser.parse_args()

    if not ensure_ollama_running():
        console.print("[red]❌ Ollama is not running. Start it with:[/red]")
        console.print("    ollama serve\n")
        sys.exit(1)

    console.print("[green]✅ Ollama detected. Loading FAISS index...[/green]")

    embedder = get_embedder()
    try:
        store = load_index(embedder=embedder)
    except Exception as e:
        console.print(f"[red]Failed to load FAISS index:[/red] {e}")
        console.print("Make sure you ran `python scripts/build_index.py` successfully.")
        sys.exit(1)

    qa = build_qa_chain(store)
    console.print(f"[cyan]🤖 Querying local KB...[/cyan]\n")

    try:
        result = qa.invoke({"query": args.question})
    except Exception as e:
        console.print(f"[red]❌ Query failed:[/red] {e}")
        sys.exit(1)

    console.print("\n[bold green]🧠 Answer:[/bold green]")
    console.print(result.get("result", "No answer returned."))

    if "source_documents" in result:
        console.print("\n[bold yellow]📚 Source Documents:[/bold yellow]")
        for src in result["source_documents"]:
            console.print(f"- {src.metadata.get('source', 'unknown')}")


if __name__ == "__main__":
    main()
