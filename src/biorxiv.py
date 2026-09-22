"""bioRxiv and medRxiv API client."""

import logging
import time
from typing import Dict, List, Optional, Set
import requests

from .models import Paper

logger = logging.getLogger(__name__)

BIORXIV_BASE = "https://api.biorxiv.org/details"


class PreprintClient:
    """Client for bioRxiv and medRxiv details API."""

    def __init__(self, delay_seconds: float = 1.0):
        self.delay_seconds = delay_seconds
        self._last_request_time = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_time = time.time()

    def fetch_preprints(
        self,
        server: str,
        start_date: str,
        end_date: str,
        categories: Optional[List[str]] = None,
        max_pages: int = 100,
    ) -> List[Paper]:
        """Fetch preprints from bioRxiv or medRxiv within the date window.

        Args:
            server: 'biorxiv' or 'medrxiv'
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            categories: List of categories to keep (matched case-insensitively)
            max_pages: Safeguard against infinite loops

        Returns:
            List of Paper objects with latest version per DOI.
        """
        category_set = (
            {c.lower().replace(" ", "_") for c in categories}
            if categories
            else None
        )

        cursor = 0
        page = 0
        raw_by_doi: Dict[str, dict] = {}

        logger.info(
            "Fetching %s preprints from %s to %s...",
            server,
            start_date,
            end_date,
        )

        while page < max_pages:
            url = f"{BIORXIV_BASE}/{server}/{start_date}/{end_date}/{cursor}"
            self._throttle()
            page += 1

            try:
                resp = requests.get(url, timeout=45)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(
                    "Error fetching %s page %d (cursor=%d): %s",
                    server,
                    page,
                    cursor,
                    e,
                )
                break

            collection = data.get("collection", [])
            if not collection:
                break

            logger.info(
                "  [%s page %d] Fetched %d items (cursor %d)",
                server,
                page,
                len(collection),
                cursor,
            )

            for item in collection:
                # Filter by category if specified
                item_cat = (
                    item.get("category", "")
                    .strip()
                    .lower()
                    .replace(" ", "_")
                )
                if category_set and item_cat not in category_set:
                    continue

                doi = (item.get("doi") or "").strip().lower()
                if not doi:
                    continue

                # Version deduplication: keep highest version
                try:
                    ver = int(item.get("version", 1))
                except (ValueError, TypeError):
                    ver = 1

                existing = raw_by_doi.get(doi)
                if existing:
                    try:
                        ex_ver = int(existing.get("version", 1))
                    except (ValueError, TypeError):
                        ex_ver = 1
                    if ver > ex_ver:
                        raw_by_doi[doi] = item
                else:
                    raw_by_doi[doi] = item

            cursor += len(collection)
            # If the collection returned is small, we reached the end
            if len(collection) < 30:
                break

        # Convert kept raw dicts to Paper instances
        papers: List[Paper] = []
        for raw in raw_by_doi.values():
            doi = (raw.get("doi") or "").strip()
            title = (raw.get("title") or "Untitled").strip()
            abstract = (raw.get("abstract") or "").strip()
            pub_date = (raw.get("date") or "").strip()
            category = (raw.get("category") or "").strip()

            raw_authors = raw.get("authors") or ""
            if isinstance(raw_authors, str):
                author_list = [
                    a.strip() for a in raw_authors.split(";") if a.strip()
                ]
            elif isinstance(raw_authors, list):
                author_list = [str(a).strip() for a in raw_authors if str(a).strip()]
            else:
                author_list = []

            journal_label = f"{server.capitalize()} ({category})" if category else server.capitalize()

            papers.append(
                Paper(
                    title=title,
                    authors=author_list,
                    journal=journal_label,
                    pub_date=pub_date,
                    doi=doi,
                    abstract=abstract,
                    source=server,
                    is_preprint=True,
                )
            )

        logger.info(
            "Found %d unique %s preprints in specified categories",
            len(papers),
            server,
        )
        return papers
