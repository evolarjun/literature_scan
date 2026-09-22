"""Filtering, topic tagging, and deduplication logic."""

import re
from typing import Dict, List, Set
from .models import Paper


def tag_topics(paper: Paper, patterns: Dict[str, List[str]]) -> List[str]:
    """Tag a paper with topics whose regex patterns match title or abstract."""
    text = f"{paper.title} {paper.abstract}".lower()
    matched = []

    for topic_key, pattern_list in patterns.items():
        for pat in pattern_list:
            if re.search(pat, text, re.IGNORECASE):
                matched.append(topic_key)
                break

    return matched


def filter_tier1(papers: List[Paper], journal_whitelist: List[str]) -> List[Paper]:
    """Filter PubMed papers to only those published in Tier-1 journals.

    Preprints are bypassed by this filter.
    """
    whitelist_set = {j.strip() for j in journal_whitelist}
    kept = []
    for paper in papers:
        if paper.is_preprint:
            kept.append(paper)
        elif paper.journal.strip() in whitelist_set:
            kept.append(paper)
    return kept


def filter_preprints(papers: List[Paper]) -> List[Paper]:
    """Filter preprints to ensure they match at least one anchor topic (not 'tools' alone).

    Peer-reviewed papers pass through untouched.
    """
    kept = []
    for paper in papers:
        if not paper.is_preprint:
            kept.append(paper)
        else:
            # Must have at least one topic other than 'tools'
            non_tool_topics = [t for t in paper.topics if t != "tools"]
            if non_tool_topics:
                kept.append(paper)
    return kept


def deduplicate(papers: List[Paper]) -> List[Paper]:
    """Deduplicate papers by DOI (or fallback to normalized title).

    Prefers PubMed records over preprints when both exist.
    """
    seen_identifiers: Set[str] = set()
    deduped: List[Paper] = []

    # Sort so PubMed records come before preprints
    # This guarantees that if both exist with the same DOI, PubMed is kept
    sorted_papers = sorted(papers, key=lambda p: (1 if p.is_preprint else 0))

    for paper in sorted_papers:
        if paper.doi:
            ident = f"doi:{paper.doi.strip().lower()}"
        elif paper.pmid:
            ident = f"pmid:{paper.pmid.strip()}"
        else:
            # Fallback to normalized title
            norm_title = re.sub(r"\W+", "", paper.title.lower())
            ident = f"title:{norm_title}"

        if ident not in seen_identifiers:
            seen_identifiers.add(ident)
            deduped.append(paper)

    return deduped
