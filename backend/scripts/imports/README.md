# Historical data importers (one-off)

One-time scripts that loaded the user's historical tracker data from Excel
screenshots into `data/tabletennis.db`. They are **not** part of the running
app — the imported data already lives in the committed database. They are kept
here only as provenance: what was imported and how each value was mapped.

Each script is idempotent (it clears its own date range first, then re-inserts)
so re-running it is safe. Run from the `backend/` directory, e.g.:

    .venv\Scripts\python scripts\imports\import_may2026.py

| Script | Date range | Source |
|---|---|---|
| `import_mar_early2026.py` | 2026-03-01 .. 2026-03-08 | third screenshot (March only) |
| `import_mar_gap2026.py`   | 2026-03-09 .. 2026-03-22 | fourth screenshot (gap fill) |
| `import_mar_apr2026.py`   | 2026-03-23 .. 2026-05-03 | second screenshot |
| `import_may2026.py`       | 2026-05-04 .. 2026-05-31 | first screenshot |

Mapping decisions (doubles vs singles, serve-count → minutes, physical
checklist, non-playing entries, etc.) are documented in each file's docstring.
