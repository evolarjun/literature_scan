"""CLI entry point for weekly AMR literature scan."""

import argparse
from datetime import datetime, timedelta, timezone
import logging
import os
import sys
from typing import Dict, List, Set
import yaml

from src.biorxiv import PreprintClient
from src.filters import deduplicate, filter_preprints, filter_tier1, tag_topics
from src.models import Paper
from src.output import write_csv, write_markdown
from src.pubmed import PubMedClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("literature_scan")


def load_config(config_path: str) -> dict:
    """Load YAML configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def calculate_date_window(end_date_str: str, days: int):
    """Compute start and end date strings for PubMed (YYYY/MM/DD) and bioRxiv (YYYY-MM-DD)."""
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=days)

    pubmed_min = start_dt.strftime("%Y/%m/%d")
    pubmed_max = end_dt.strftime("%Y/%m/%d")
    iso_min = start_dt.strftime("%Y-%m-%d")
    iso_max = end_dt.strftime("%Y-%m-%d")

    return {
        "pubmed_min": pubmed_min,
        "pubmed_max": pubmed_max,
        "iso_min": iso_min,
        "iso_max": iso_max,
    }


def main():
    parser = argparse.ArgumentParser(description="AMR Weekly Literature Scan")
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="End date of search window (YYYY-MM-DD, defaults to today)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of lookback days (default: 7)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="digests",
        help="Directory to save weekly scan outputs (default: digests)",
    )
    args = parser.parse_args()

    # 1. Load config
    if not os.path.exists(args.config):
        logger.error("Configuration file not found: %s", args.config)
        sys.exit(1)

    config = load_config(args.config)
    queries = config.get("queries", {})
    topic_patterns = config.get("topic_patterns", {})
    preprint_categories = config.get("preprint_categories", {})
    tier1_journals = config.get("tier1_journals", [])

    topic_labels = {k: v.get("label", k) for k, v in queries.items()}

    # 2. Compute date bounds
    bounds = calculate_date_window(args.end_date, args.days)
    logger.info(
        "Scan window: %s to %s (%d days)",
        bounds["iso_min"],
        bounds["iso_max"],
        args.days,
    )

    stats = {
        "pubmed_raw": 0,
        "preprints_raw": 0,
    }

    # 3. PubMed Sweep
    logger.info("Starting PubMed sweep across %d topics...", len(queries))
    pubmed_client = PubMedClient()
    pmid_to_topics: Dict[str, Set[str]] = {}

    for topic_key, query_info in queries.items():
        term = query_info.get("query", "")
        if not term:
            continue
        logger.info("Searching PubMed for topic: %s", topic_key)
        try:
            matched_pmids = pubmed_client.search(
                term,
                min_date=bounds["pubmed_min"],
                max_date=bounds["pubmed_max"],
            )
            logger.info("  Found %d PMIDs for %s", len(matched_pmids), topic_key)
            for pmid in matched_pmids:
                if pmid not in pmid_to_topics:
                    pmid_to_topics[pmid] = set()
                pmid_to_topics[pmid].add(topic_key)
        except Exception as e:
            logger.error("Error during PubMed search for %s: %s", topic_key, e)

    unique_pmids = list(pmid_to_topics.keys())
    stats["pubmed_raw"] = len(unique_pmids)
    logger.info("Total unique PMIDs found: %d", len(unique_pmids))

    # Fetch PubMed records
    logger.info("Fetching PubMed records in batches...")
    pubmed_papers: List[Paper] = []
    if unique_pmids:
        try:
            pubmed_papers = pubmed_client.fetch(unique_pmids)
            for p in pubmed_papers:
                if p.pmid and p.pmid in pmid_to_topics:
                    p.topics.extend(list(pmid_to_topics[p.pmid]))
        except Exception as e:
            logger.error("Error fetching PubMed records: %s", e)

    logger.info("Fetched %d PubMed records", len(pubmed_papers))

    # Additional topic pattern tagging on PubMed papers
    for p in pubmed_papers:
        extra_topics = tag_topics(p, topic_patterns)
        p.topics = sorted(list(set(p.topics + extra_topics)))

    # Filter PubMed to Tier-1 journals
    tier1_pubmed = filter_tier1(pubmed_papers, tier1_journals)
    logger.info("PubMed papers after Tier-1 filter: %d", len(tier1_pubmed))

    # 4. Preprint Sweep
    logger.info("Starting Preprint sweep (bioRxiv & medRxiv)...")
    preprint_client = PreprintClient()
    all_preprints: List[Paper] = []

    for server, cats in preprint_categories.items():
        try:
            preprints = preprint_client.fetch_preprints(
                server=server,
                start_date=bounds["iso_min"],
                end_date=bounds["iso_max"],
                categories=cats,
            )
            all_preprints.extend(preprints)
        except Exception as e:
            logger.error("Error fetching preprints from %s: %s", server, e)

    stats["preprints_raw"] = len(all_preprints)
    logger.info("Total preprints screened: %d", len(all_preprints))

    # Tag preprints with topics
    for p in all_preprints:
        p.topics = tag_topics(p, topic_patterns)

    # Filter preprints to those with anchor topics (not 'tools' alone)
    filtered_preprints = filter_preprints(all_preprints)
    logger.info(
        "Preprints after anchor topic filter: %d",
        len(filtered_preprints),
    )

    # 5. Merge and Deduplicate
    all_candidates = tier1_pubmed + filtered_preprints
    final_papers = deduplicate(all_candidates)
    logger.info("Final shortlisted candidate papers: %d", len(final_papers))

    # 6. Write outputs
    md_filename = f"{bounds['iso_max']}.md"
    csv_filename = f"{bounds['iso_max']}.csv"

    md_path = os.path.join(args.output_dir, md_filename)
    csv_path = os.path.join(args.output_dir, csv_filename)

    logger.info("Writing markdown output to %s...", md_path)
    write_markdown(
        papers=final_papers,
        start_date=bounds["iso_min"],
        end_date=bounds["iso_max"],
        output_path=md_path,
        topic_labels=topic_labels,
        stats=stats,
    )

    logger.info("Writing CSV output to %s...", csv_path)
    write_csv(
        papers=final_papers,
        output_path=csv_path,
        topic_labels=topic_labels,
    )

    logger.info("Scan completed successfully!")
    print(f"\n--- SCAN SUMMARY ---")
    print(f"Date Window: {bounds['iso_min']} to {bounds['iso_max']}")
    print(f"PubMed Raw Hits: {stats['pubmed_raw']}")
    print(f"Preprints Screened: {stats['preprints_raw']}")
    print(f"Tier-1 PubMed Candidates: {len(tier1_pubmed)}")
    print(f"Filtered Preprints: {len(filtered_preprints)}")
    print(f"Final Candidates (Deduped): {len(final_papers)}")
    print(f"Saved: {md_path}")
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
