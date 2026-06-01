#!/usr/bin/env python3
"""Standalone test for multi-source scholarly search.

Run from the project root:

    python scripts/test_research.py
"""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from app import create_app
from app.research_service import format_papers_for_prompt, search_papers

QUERY = "machine learning in education"
LIMIT = 3


def main():
    app = create_app()
    with app.app_context():
        print(f"Query: {QUERY!r}\n")
        papers, api_used, source = search_papers(QUERY, limit=LIMIT)
        print(f"api_used={api_used}")
        print(f"source={source}")
        print(f"papers returned={len(papers)}\n")

        if not papers:
            print("No papers returned. Check logs above for per-source errors.")
            return 1

        for i, paper in enumerate(papers, 1):
            print(f"--- Paper {i} ({paper.get('source')}) ---")
            print(f"Title:    {paper['title']}")
            print(f"Authors:  {paper['authors']}")
            print(f"Year:     {paper['year']}")
            print(f"Verify:   {paper.get('verification_url') or paper.get('url') or 'N/A'}")
            abstract = paper["abstract"] or "(none)"
            print(f"Abstract: {abstract[:200]}{'…' if len(abstract) > 200 else ''}")
            print()

        prompt_snippet = format_papers_for_prompt(papers)
        print("Prompt snippet (first 500 chars):")
        print(prompt_snippet[:500])
        if len(prompt_snippet) > 500:
            print("…")
        return 0


if __name__ == "__main__":
    sys.exit(main())
