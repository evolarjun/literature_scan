"""Data models for literature scan records."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Paper:
    """Represents a scientific paper or preprint."""

    title: str
    authors: List[str]
    journal: str
    pub_date: str
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    abstract: str = ""
    topics: List[str] = field(default_factory=list)
    source: str = "pubmed"  # "pubmed", "biorxiv", or "medrxiv"
    is_preprint: bool = False

    def formatted_authors(self, max_authors: int = 3) -> str:
        """Return authors formatted as first N plus et al."""
        if not self.authors:
            return "Unknown Authors"
        if len(self.authors) <= max_authors:
            return ", ".join(self.authors)
        return ", ".join(self.authors[:max_authors]) + ", et al."
