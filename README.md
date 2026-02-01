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
