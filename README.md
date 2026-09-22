# AMR Weekly Literature Scan Pipeline

An automated, deterministic Python pipeline that runs weekly via GitHub Actions to sweep **PubMed** and **bioRxiv/medRxiv** for high-impact literature in antimicrobial resistance (AMR), metagenomics, long-read sequencing, and microbial bioinformatics tools.

The resulting candidate papers are filtered to Tier-1 clinical and genomic microbiology journals, formatted with full abstracts and metadata, and committed directly to `digests/` in Markdown and CSV formats. These files can then be provided to a **Gemini Spark job** (using [`prompt_template.md`](prompt_template.md)) to curate and draft the final operational literature digest.

---

## Architecture

```
┌────────────────────────────────┐
│   GitHub Actions (Weekly Cron) │
│        Runs Mondays 08:00 UTC  │
└───────────────┬────────────────┘
                │
        ┌───────▼────────┐
        │    main.py     │
        └───┬────────┬───┘
            │        │
   ┌────────▼───┐  ┌─▼─────────────┐
   │ PubMed API │  │ bioRxiv API   │
   │ (E-utils)  │  │ & medRxiv     │
   └────────┬───┘  └─┬─────────────┘
            │        │
            └────┬───┘
                 │
      ┌──────────▼──────────┐
      │ Filters & Dedupe    │
      │ • Tier-1 Whitelist  │
      │ • Anchor Topics     │
      │ • Deduplicate (DOI) │
      └──────────┬──────────┘
                 │
       ┌─────────▼──────────┐
       │   Commit to repo   │
       │  • digests/DATE.md │
       │  • digests/DATE.csv│
       └─────────┬──────────┘
                 │
                 ▼
 ┌───────────────────────────────┐
 │       Gemini Spark Job        │
 │  (Prompt: prompt_template.md) │
 │  Produces 8-12 paper review   │
 └───────────────────────────────┘
```

---

## Directory Structure

```
literature_scan/
├── .github/
│   └── workflows/
│       └── weekly_scan.yml      # GitHub Actions workflow definition
├── digests/                     # Date-stamped scan outputs (.md and .csv)
├── src/
│   ├── models.py                # Paper dataclass
│   ├── pubmed.py                # PubMed E-utilities client
│   ├── biorxiv.py               # bioRxiv and medRxiv API client
│   ├── filters.py               # Tier-1 whitelist, preprint anchors, deduplication
│   └── output.py                # Markdown and CSV writers
├── config.yaml                  # Queries, topic regexes, preprint categories, Tier-1 journals
├── prompt_template.md           # Instructions for Gemini Spark digest curation
├── main.py                      # CLI orchestration entry point
├── requirements.txt             # Python dependencies (requests, pyyaml)
└── README.md
```

---

## Setup & GitHub Configuration

### 1. Repository Permissions
In your GitHub repository settings:
- Go to **Settings** → **Actions** → **General** → **Workflow permissions**.
- Select **"Read and write permissions"** so the GitHub Actions workflow can commit and push weekly scan files to `main`.

### 2. Secrets (Optional)
In your repository **Settings** → **Secrets and variables** → **Actions** under **Repository secrets** (click **"New repository secret"**):
- `NCBI_API_KEY`: (Optional) Raises NCBI E-utilities rate limit from 3 req/s to 10 req/s.
- `USER_EMAIL`: (Optional) Email address provided in NCBI request headers per NCBI guidelines.

---

## Local Development & Private Environment (using `uv`)

You can use [`uv`](https://github.com/astral-sh/uv) to manage a fast, isolated private virtual environment.

### 1. Install `uv` (if not already installed)
- **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **macOS via Homebrew:**
  ```bash
  brew install uv
  ```

### 2. Create and Populate the Private Environment
From the project root directory:

```bash
# Create an isolated virtual environment (.venv)
uv venv

# Install project dependencies into the virtual environment
uv pip install -r requirements.txt
```

*(Note: `.venv/` is already included in `.gitignore` so your private environment files will never be committed).*

### 3. Run the Pipeline

You can run the script directly through `uv run` (which automatically uses the private `.venv` without needing to activate it manually):

- **Default run (7-day lookback ending today):**
  ```bash
  uv run main.py
  ```

- **Run with custom parameters:**
  ```bash
  uv run main.py --end-date 2026-09-22 --days 3 --output-dir digests/
  ```

- **Alternatively, activate the environment manually:**
  ```bash
  source .venv/bin/activate
  python main.py
  ```

---

## Downstream Digest with Gemini Spark

Once a weekly scan file (e.g., `digests/2026-09-22.md`) is committed:
1. Open the [Gemini web UI](https://gemini.google.com).
2. Attach or paste the contents of `digests/YYYY-MM-DD.md`.
3. Provide the prompt from [`prompt_template.md`](prompt_template.md).
4. Gemini will curate the top 8–12 papers according to operational relevance and generate the finalized weekly review.

