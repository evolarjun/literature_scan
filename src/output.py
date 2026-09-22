"""Output formatting for Markdown and CSV files."""

import csv
import os
from typing import Any, Dict, List
from .models import Paper


def write_markdown(
    papers: List[Paper],
    start_date: str,
    end_date: str,
    output_path: str,
    topic_labels: Dict[str, str],
    stats: Dict[str, Any],
):
    """Write candidate papers to a markdown file structured for Gemini processing."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# AMR & Microbiology Literature Scan ({start_date} to {end_date})\n\n")
        f.write(
            f"**Scan Window:** {start_date} to {end_date}  \n"
            f"**Candidate Papers:** {len(papers)} (after Tier-1 & topic filtering)  \n"
            f"**Total PubMed Hits:** {stats.get('pubmed_raw', 0)}  \n"
            f"**Total Preprints Screened:** {stats.get('preprints_raw', 0)}  \n\n"
            "---\n\n"
        )

        if not papers:
            f.write("*No papers matched the criteria for this scan window.*\n")
            return

        for idx, paper in enumerate(papers, 1):
            doi_link = (
                f"[{paper.doi}](https://doi.org/{paper.doi})"
                if paper.doi
                else "N/A"
            )

            # Map topic keys to human-readable labels
            readable_topics = [
                topic_labels.get(t, t) for t in paper.topics
            ]
            topics_str = ", ".join(readable_topics) if readable_topics else "General"

            preprint_badge = f" *(Preprint — {paper.source})*" if paper.is_preprint else ""

            # Clean abstract for markdown blockquote
            abstract_text = paper.abstract.strip() if paper.abstract else "*No abstract available.*"
            # Indent multi-line abstract with blockquote '>'
            quoted_abstract = "\n> ".join(abstract_text.splitlines())

            f.write(f"### {idx}. {paper.title}\n\n")
            f.write(f"- **Authors:** {paper.formatted_authors(max_authors=3)}\n")
            f.write(f"- **Journal / Venue:** {paper.journal}{preprint_badge}\n")
            f.write(f"- **Date:** {paper.pub_date or 'N/A'}\n")
            f.write(f"- **DOI:** {doi_link}\n")

            id_parts = []
            if paper.pmid:
                id_parts.append(f"**PMID:** [{paper.pmid}](https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/)")
            if paper.pmcid:
                id_parts.append(f"**PMCID:** [{paper.pmcid}](https://www.ncbi.nlm.nih.gov/pmc/articles/{paper.pmcid}/)")
            if id_parts:
                f.write(f"- {' | '.join(id_parts)}\n")

            f.write(f"- **Topics:** {topics_str}\n\n")
            f.write(f"> {quoted_abstract}\n\n")
            f.write("---\n\n")


def write_csv(papers: List[Paper], output_path: str, topic_labels: Dict[str, str]):
    """Write papers metadata and abstracts to CSV."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    fieldnames = [
        "title",
        "authors",
        "journal",
        "pub_date",
        "doi",
        "pmid",
        "pmcid",
        "topics",
        "source",
        "is_preprint",
        "abstract",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for p in papers:
            readable_topics = [topic_labels.get(t, t) for t in p.topics]
            writer.writerow(
                {
                    "title": p.title,
                    "authors": "; ".join(p.authors),
                    "journal": p.journal,
                    "pub_date": p.pub_date,
                    "doi": p.doi or "",
                    "pmid": p.pmid or "",
                    "pmcid": p.pmcid or "",
                    "topics": "; ".join(readable_topics),
                    "source": p.source,
                    "is_preprint": "True" if p.is_preprint else "False",
                    "abstract": p.abstract,
                }
            )
