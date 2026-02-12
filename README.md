# White House Briefings Scraper

Collects and explores archived White House press briefings. The project has two entry points:

- CLI workers (`discover.py`, `scrape.py`) that fetch and store data into PostgreSQL.
- A lightweight Flask web app (`wh_scraper.web`) for filtering and reading stored transcripts.

## Running the web browser

1. Ensure dependencies are installed (`uv sync` or `pip install -e .`).
2. Export database settings or rely on the defaults in `src/wh_scraper/config.py`.
3. Start the Flask server:

   ```bash
   FLASK_APP=wh_scraper.web.app:create_app \
   FLASK_ENV=development \
   flask run --reload
   ```

   The server listens on `http://127.0.0.1:5000` by default.

4. Open the URL in a browser to filter by administration/status, scroll the title list, and load transcripts inline.

## CLI workflows

Discover listing pages:

```bash
python -m wh_scraper.discover --start-page 1 --end-page 116
```

Scrape pending documents:

```bash
python -m wh_scraper.scrape --limit 100000
```

## Semantic search workflow

1. Ensure PostgreSQL has the [`vector`](https://github.com/pgvector/pgvector) extension installed **and upgraded to ≥ 0.5** (the setup script now checks this and will raise if the version is too old).
2. Configure OpenAI access in `.env`:

   ```
   OPENAI_API_KEY=sk-...
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   EMBEDDING_BATCH_SIZE=64
   CHUNK_MAX_TOKENS=400
   CHUNK_OVERLAP_TOKENS=40
   ```

3. Chunk scraped documents that have `clean_text` populated:

   ```bash
   python -m wh_scraper.chunk --limit 25
   ```

4. Generate embeddings for the pending chunks:

   ```bash
   python -m wh_scraper.embed --limit 200
   ```

5. Run a similarity search from the CLI:

   ```bash
   python -m wh_scraper.search "show me statements relating to Ukraine" --limit 5
   ```

   Results show chunk metadata (title, admin, date, URL) plus a snippet sorted by cosine similarity.
