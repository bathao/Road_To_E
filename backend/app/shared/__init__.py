"""Code shared by several features (added 2026-10-16, REFACTOR.md Phase 2).

Feature packages under ``app/features`` must not import each other's private
names; anything two of them need lives here instead:

- ``ollama``    — the local LLM plumbing (model resolution, one structured
                  chat call, the empty-reply retry, the VRAM probe).
- ``jobs``      — the generating → done | error lifecycle every background
                  LLM job follows, plus stuck-row recovery at startup.
- ``persona``   — the coach persona sentences every system prompt opens with.
- ``format_vi`` — Vietnamese labels/formatters the prompts share.
- ``time``      — re-attaching UTC to naive SQLite timestamps.
"""
