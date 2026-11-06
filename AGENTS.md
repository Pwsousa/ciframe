# AGENTS.md

deciframe is a song-discovery tool for musicians: search by title/artist,
genre, chords you already know, or a famous chord sequence, and it finds
similar songs. Full description: [README.md](README.md).

## Stack

- Backend: Python 3.9, Flask 3.1, gunicorn. Single file (`main.py`) that
  loads `data/top/dataset_final.csv` into memory once at startup. The chord
  sequence catalog (6 seeded legacy entries + visitor registrations) is the one
  thing persisted, in SQLite at `instance/deciframe.db`.
- Frontend: AngularJS 1.4.9 + jQuery, loaded from CDN in `static/index.html`,
  no build step. Legacy, and there's no plan to modernize the stack itself —
  but touching it is no longer off-limits when a task needs it; see
  [docs/adr/0003-lift-frontend-freeze.md](docs/adr/0003-lift-frontend-freeze.md).
- Deploy: local-only via Docker for now. No cloud target has been chosen.

## Run locally

Docker (matches how the app actually ships):

```
docker build -t ciframe .
docker run -v ciframe-data:/app/instance -p 8080:8080 ciframe
```

Or a plain virtualenv:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py        # serves on :5000 instead of :8080
```

## Run the tests

```
pip install -r requirements-dev.txt
pytest
```

`tests/conftest.py` points `CIFRAME_DB_PATH` at a temporary file before
importing `main`, so the suite never touches `instance/deciframe.db`.

## Verify it's up

```
curl http://localhost:8080/generos
```

Done when this returns a JSON array of genre names (e.g. `["Rock", "Samba", ...]`), not an error page. If it hangs on startup, it's still parsing the CSV — give it a few seconds.

## Gotchas

- Editing `data/top/*.csv` requires a restart: it's read once at import time, not per-request.
- Every endpoint returns `json.dumps(...)` as a plain string, not `jsonify` — responses come back `Content-Type: text/html`. This is intentional legacy behavior; changing it is a real API change, not a cleanup.
- The SQLite file is `instance/deciframe.db`, overridable with `CIFRAME_DB_PATH`. Keep it out of `/app/data`: mounting a volume there would shadow `dataset_final.csv` and the app would fail to start.
- The 6 original sequences (`legado_id` 0–5) still match through the CSV's pre-computed `SEQ_FAMOSA` tag, not through the structural matcher. That is intentional: no structural rule reproduces the curated tag (see `docs/adr/0002-persist-custom-sequences.md`). Only visitor-registered sequences use the contiguous-run rule.
- `tests/conftest.py` sets `CIFRAME_DB_PATH` before importing `main`; don't import `main` from a test module that bypasses conftest.
- Check `docs/adr/` before changing the deploy setup — it has a documented reason for its current state.
