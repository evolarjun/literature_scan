Instructions

Run the amr-weekly-digest skill to produce this week's AMR/antifungal literature digest.

Instructions:
1. Invoke the "amr-weekly-digest" skill (Skill tool, skill name "amr-weekly-digest").
2. Use the default 7-day lookback window ending today (call amr_week_bounds with no "end" argument to default to today).
3. Use the default topic scope: AMR, antifungals, metagenomics, 16S/ITS amplicon, long-read microbiology, and AMR/antifungal bioinformatics tools. Do not customize topics or queries.
4. Follow the skill's full workflow: sweep PubMed, sweep bioRxiv/medRxiv preprints, shortlist to Tier-1 journals plus relevant preprints, verify DOIs, write the categorized markdown digest (goal/approach/key features/findings/takeaway per paper, DOI link in every entry, preprints clearly labeled as preprints), and produce the companion CSV of selected papers.
5. Deliver both files (the markdown digest and the CSV) using SendUserFile.
6. In your final chat reply, include the actual substantive content of the digest (organized by topic, not just a pointer to the file) so the user can read the highlights without opening the files.

This is a recurring weekly task — treat it as a fresh, standalone run each time with no memory of prior weeks' conversations.
