---
name: amr-weekly-digest
description: Build a curated weekly literature digest on antimicrobial resistance, antifungals, metagenomics, 16S/ITS amplicon, long-read microbiology, and AMR/antifungal bioinformatics tools. Sweeps PubMed plus bioRxiv/medRxiv for a date window, filters to high-impact venues, and writes a categorized markdown review with per-paper goal/approach/findings/takeaway bullets and a companion citation CSV. Use for "this week's papers", recurring AMR or antifungal literature scans, or any windowed microbiology/AMR literature sweep.
---

# AMR weekly digest

Produces a categorized digest of the last N days of literature across six topics
relevant to an antimicrobial/antifungal/antiseptic testing lab: AMR, antifungals,
metagenomics, 16S and ITS amplicon work, long-read microbiology, and bioinformatics
tools for AMR/antifungal analysis.

The deliverable is two artifacts: a markdown review organized by topic with
goal / approach / key features / findings / takeaway bullets per paper and a DOI
link in every entry, plus a CSV of every selected paper. The chat reply carries the
same substance, not just a pointer to the file.

## Workflow

1. **Set the window.** `amr_week_bounds(end="YYYY-MM-DD", days=7)` returns both the
   PubMed `YYYY/MM/DD` and ISO `YYYY-MM-DD` forms. Omit `end` for today.
2. **Sweep PubMed.** `amr_pubmed_week(bounds["pubmed_min"], bounds["pubmed_max"])`
   runs all six queries in `AMR_QUERIES` with Entrez date (`edat`, i.e. first
   appearance in PubMed, which is what "published or available this week" means),
   fetches records, and attaches a `topics` list per record. Expect roughly
   700-900 records for a 7-day window.
3. **Sweep preprints.** `amr_preprint_week(bounds["iso_min"], bounds["iso_max"])`
   paginates bioRxiv and medRxiv, then `amr_filter_preprints(...)` keeps
   microbiology/bioinformatics/genomics/ID categories that carry at least one
   non-tool topic anchor, tags them, and de-duplicates by DOI keeping the highest
   version. The preprint sweep is the slow step (several minutes for ~1,900
   postings) — run it in a `background: true` cell alongside the PubMed work.
4. **Shortlist.** `amr_tier1(records)` filters PubMed hits to `AMR_TIER1_JOURNALS`.
   Print one compact line per candidate (`index|journal|topics|truncated title`) and
   pick 8-12 by relevance to susceptibility testing, resistance mechanism, ECV/MIC
   methodology, and tool utility. Then print full abstracts for only the picks.
5. **Verify DOIs.** Load the `literature-review` skill and run `verify_dois(dois)`
   before writing prose. Preprint DOIs resolve through CrossRef too.
6. **Write and lint.** Draft the markdown, run `style_pass(draft)` once, fix what it
   flags in a single pass, save. `amr_digest_csv(journal_recs, preprint_recs, path)`
   writes the companion table.

## Selection criteria that make the digest useful

Rank on operational relevance, not novelty alone. Papers that change how a testing
lab works outrank interesting biology: new ECVs or breakpoints, cross-resistance
between an established agent and a new one, MIC or checkerboard methodology,
susceptibility-testing panel design, and tools with stated error rates or resource
benchmarks. Reviews and editorials are usually cut unless they are the definitive
synthesis of the week. Label every preprint as a preprint in both the heading and
the takeaway, and say in the takeaway what would need confirming.

## Pitfalls

- **DOI extraction.** Read DOIs only from `PubmedData/ArticleIdList`. A `.//ArticleId`
  search over the whole record picks up reference-list DOIs and silently returns a
  cited paper's DOI instead. `amr_pubmed_fetch` already scopes this correctly; if you
  hand-roll an efetch parse, keep the scoping.
- **Topic tag false positives.** `AMR_TOPIC_PATTERNS` is deliberately broad, so the
  `antifungal` and `tools` tags catch unrelated preprints (`Aspergillus` in a plant
  paper, `benchmark` in an ML paper). Always read titles before shortlisting; never
  trust the tag alone.
- **`tools` is not an anchor.** `amr_filter_preprints` requires a topic anchor other
  than `tools`, otherwise every methods preprint in the corpus qualifies.
- **Journal names.** `AMR_TIER1_JOURNALS` matches `Journal/ISOAbbreviation` exactly
  (`Clin Microbiol Infect`, not the full title). Extend the tuple rather than
  loosening the match.
- **NCBI courtesy.** Helpers sleep between requests. Keep the pauses; do not
  parallelise E-utilities calls.

## Customizing

Add a topic by extending `AMR_QUERIES` (PubMed side) and `AMR_TOPIC_PATTERNS`
(preprint side) together — they are separate mechanisms and a topic present in only
one produces an asymmetric digest. Pass your own dicts to `amr_pubmed_week(queries=)`
and `amr_tag_topics(patterns=)` for a one-off variation without editing the skill.
