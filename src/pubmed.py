"""PubMed E-utilities API client."""

import logging
import os
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import requests

from .models import Paper

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClient:
    """Client for NCBI E-utilities (esearch and efetch)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        tool: str = "literature_scan",
    ):
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.email = email or os.environ.get("USER_EMAIL")
        self.tool = tool
        self.rate_limit_pause = 0.12 if self.api_key else 0.35
        self._last_request_time = 0.0

    def _throttle(self):
        """Enforce rate limits between NCBI requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_pause:
            time.sleep(self.rate_limit_pause - elapsed)
        self._last_request_time = time.time()

    def _base_params(self) -> Dict[str, str]:
        params = {"tool": self.tool}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email
        return params

    def search(
        self,
        query: str,
        min_date: str,
        max_date: str,
        max_results: int = 1000,
    ) -> List[str]:
        """Search PubMed using Entrez date (edat) and return matching PMIDs.

        min_date and max_date must be formatted as YYYY/MM/DD.
        """
        url = f"{EUTILS_BASE}/esearch.fcgi"
        pmids: List[str] = []
        retstart = 0
        batch_size = 500

        while True:
            params = {
                **self._base_params(),
                "db": "pubmed",
                "term": query,
                "datetype": "edat",
                "mindate": min_date,
                "maxdate": max_date,
                "retstart": str(retstart),
                "retmax": str(min(batch_size, max_results - len(pmids))),
                "retmode": "json",
            }

            self._throttle()
            logger.debug("Calling esearch retstart=%d", retstart)
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            id_list = data.get("esearchresult", {}).get("idlist", [])
            total_count = int(data.get("esearchresult", {}).get("count", 0))

            if not id_list:
                break

            pmids.extend(id_list)
            retstart += len(id_list)

            if retstart >= total_count or len(pmids) >= max_results:
                break

        return pmids

    def fetch(self, pmids: List[str], batch_size: int = 200) -> List[Paper]:
        """Fetch full metadata and abstracts for given PMIDs in batches."""
        if not pmids:
            return []

        papers: List[Paper] = []
        url = f"{EUTILS_BASE}/efetch.fcgi"

        for i in range(0, len(pmids), batch_size):
            chunk = pmids[i : i + batch_size]
            params = {
                **self._base_params(),
                "db": "pubmed",
                "id": ",".join(chunk),
                "retmode": "xml",
            }

            self._throttle()
            logger.debug("Calling efetch for %d PMIDs", len(chunk))
            resp = requests.post(url, data=params, timeout=45)
            resp.raise_for_status()

            parsed_papers = self._parse_efetch_xml(resp.content)
            papers.extend(parsed_papers)

        return papers

    def _parse_efetch_xml(self, xml_content: bytes) -> List[Paper]:
        """Parse PubMed efetch XML into Paper models."""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error("Failed to parse PubMed efetch XML: %s", e)
            return []

        papers: List[Paper] = []

        for article in root.iter("PubmedArticle"):
            # 1. PMID
            pmid_elem = article.find(".//MedlineCitation/PMID")
            pmid = pmid_elem.text.strip() if (pmid_elem is not None and pmid_elem.text) else None
            if not pmid:
                continue

            art_elem = article.find(".//MedlineCitation/Article")
            if art_elem is None:
                continue

            # 2. Title
            title_elem = art_elem.find("ArticleTitle")
            title = "".join(title_elem.itertext()).strip() if title_elem is not None else "Untitled"

            # 3. Authors
            authors: List[str] = []
            for author_node in art_elem.findall(".//AuthorList/Author"):
                last = author_node.findtext("LastName") or ""
                init = author_node.findtext("Initials") or ""
                if last:
                    name = f"{last} {init}".strip() if init else last
                    authors.append(name)
                else:
                    coll = author_node.findtext("CollectiveName")
                    if coll:
                        authors.append(coll.strip())

            # 4. Journal ISO Abbreviation (critical for Tier-1 filtering)
            journal = ""
            iso_abbr = art_elem.findtext(".//Journal/ISOAbbreviation")
            if iso_abbr:
                journal = iso_abbr.strip()
            else:
                medline_ta = article.findtext(".//MedlineCitation/MedlineJournalInfo/MedlineTA")
                if medline_ta:
                    journal = medline_ta.strip()
                else:
                    journal = art_elem.findtext(".//Journal/Title") or "Unknown Journal"

            # 5. Publication Date
            pub_date = ""
            # Check ArticleDate first (often more precise for online first)
            art_date = art_elem.find(".//ArticleDate")
            if art_date is not None:
                y = art_date.findtext("Year") or ""
                m = (art_date.findtext("Month") or "01").zfill(2)
                d = (art_date.findtext("Day") or "01").zfill(2)
                if y:
                    pub_date = f"{y}-{m}-{d}"

            if not pub_date:
                # Check JournalIssue PubDate
                pd = art_elem.find(".//JournalIssue/PubDate")
                if pd is not None:
                    y = pd.findtext("Year") or ""
                    m = (pd.findtext("Month") or "01").zfill(2)
                    d = (pd.findtext("Day") or "01").zfill(2)
                    if y:
                        pub_date = f"{y}-{m}-{d}"
                    else:
                        pub_date = pd.findtext("MedlineDate") or ""

            # 6. DOI and PMCID from PubmedData/ArticleIdList only
            doi = None
            pmcid = None
            article_id_list = article.find(".//PubmedData/ArticleIdList")
            if article_id_list is not None:
                for aid in article_id_list.findall("ArticleId"):
                    id_type = aid.get("IdType")
                    if id_type == "doi" and aid.text:
                        doi = aid.text.strip()
                    elif id_type == "pmc" and aid.text:
                        pmcid = aid.text.strip()

            # Fallback for DOI: ELocationID
            if not doi:
                for eid in art_elem.findall("ELocationID"):
                    if eid.get("EIdType") == "doi" and eid.text:
                        doi = eid.text.strip()
                        break

            # 7. Abstract text
            abstract_parts: List[str] = []
            for at in art_elem.findall(".//Abstract/AbstractText"):
                label = at.get("Label")
                text = "".join(at.itertext()).strip()
                if not text:
                    continue
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = "\n\n".join(abstract_parts)

            papers.append(
                Paper(
                    title=title,
                    authors=authors,
                    journal=journal,
                    pub_date=pub_date,
                    doi=doi,
                    pmid=pmid,
                    pmcid=pmcid,
                    abstract=abstract,
                    source="pubmed",
                    is_preprint=False,
                )
            )

        return papers
