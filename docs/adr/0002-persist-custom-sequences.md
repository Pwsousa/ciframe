# Persist the custom chord sequence catalog in SQLite

The app used to keep its famous chord sequences in two hardcoded places: six
entries in `main.py` (indexed 0–5) and four entries in the AngularJS controller.
The backend entries were not computed from the songs — they were looked up
against a pre-computed `SEQ_FAMOSA` tag already present in the CSV. There was no
way for a visitor to add a sequence, and no storage that could grow without a
code change. The task required an open, anonymous catalog that survives a
restart, while songs and genres stay in the in-memory CSV and the six original
searches keep returning exactly the same results.

We introduced a single SQLite database for the sequence catalog, using Python's
stdlib `sqlite3` so the Docker image gains no new dependency and no second
service. The database lives at `instance/deciframe.db`, overridable with
`CIFRAME_DB_PATH`. It deliberately does not live under `data/`: the Dockerfile
needs a volume to persist the file across container recreation, and a volume
mounted at `/app/data` would shadow `dataset_final.csv` and prevent the app from
starting. The volume is therefore `VOLUME ["/app/instance"]`, with
`docker run -v ciframe-data:/app/instance`.

The `sequencias` table stores `id`, `nome`, the ordered chord list as JSON,
`criada_em`, a canonical `chave` with a `UNIQUE` constraint, and a nullable
`legado_id` with its own `UNIQUE` constraint. The key makes duplicate detection
atomic and case-insensitive while still respecting chord order (`c|g|am` is the
same sequence as `C,G,Am`). The six originals are seeded idempotently by
checking the key before inserting; `INSERT OR IGNORE` was rejected because it
would still consume AUTOINCREMENT ids on every boot.

The `legado_id` column also marks the split in matching semantics. The six
originals keep using the curated `SEQ_FAMOSA` tag, because research against all
67,585 songs showed that no structural algorithm reproduces that tag exactly:
set containment had 100% recall but 1.63% precision, ordered subsequence 1.79%,
and the best candidate, a contiguous run with consecutive-duplicate collapse,
reached 7.91% — better, but still not the curated result. Visitor sequences have
no tag, so they use that contiguous-run rule in real time, over a normalized
chord string pre-computed once per song at CSV load. The trade-off is explicit:
the two families behave differently, but the regression criterion is preserved
without freezing the new catalog.

The catalog is exposed as `GET /api/sequencias` and `POST /api/sequencias`
(anonymous, `201` on success, `400` on invalid input, `409` with the existing
entry on duplicates). `GET /similares?sequencia=` now accepts both the current
comma/space format and the old concatenated legacy format; an unknown sequence
returns `[]`. Responses remain `json.dumps(...)` strings rather than `jsonify`,
preserving the existing API contract.

Consequences: the catalog can grow at runtime and survives restarts when the
volume is used, but schema changes are now a real migration concern — there is
only `CREATE TABLE IF NOT EXISTS`, no migration framework. SQLite allows one
writer at a time; WAL and a busy timeout are enough for this catalog's volume,
but not a general concurrency strategy. Backups become a file copy of
`instance/deciframe.db`. Rejected alternatives were a JSON/TinyDB file (no
atomic uniqueness, corruption risk under concurrent anonymous writes) and
PostgreSQL/MySQL/Redis (extra service, contrary to the single local-only
container decision in ADR 0001). Finally, the frontend now has one source of
truth for the catalog; the four hardcoded JavaScript sequences were removed so
the UI cannot drift from the backend again.
