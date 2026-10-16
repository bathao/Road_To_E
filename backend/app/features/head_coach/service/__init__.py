"""Head Coach service — a package since 2026-10-16.

The Head Coach is a *consumer*: it calls the tracker/training services
in-process, assembles a facts bundle (bundle.py), renders it for the local
model (render.py) and persists verdicts / recaps / chat replies through the
shared job lifecycle (verdict.py, recap.py, chat.py). Every public and
test-used private name is re-exported here so router, tactics, registry
and tests keep using ``service.X``; tests that monkeypatch an LLM call
patch the submodule that owns the job (``service.verdict._call_model``…).
"""
from __future__ import annotations

from .bundle import (  # noqa: F401
    _ELO_OPP_TOP,
    _H2H_PROGRESSION,
    _MATCH_DETAIL_DAYS,
    _RECAP_H2H,
    _RECAP_PERIODS,
    _RECAP_WINDOW_DAYS,
    _RECENT_NOTES,
    _STATS_WINDOW_DAYS,
    _VERDICT_H2H,
    _elo_opp_split,
    _h2h_progression,
    _match_detail,
    _match_summary,
    _memo_dicts,
    _ms,
    _period_label_vi,
    _period_stats,
    _player_name,
    _session_note_dict,
    _task_dicts,
    _training_summary,
    coach_note_dicts,
    gather_bundle,
    gather_recap_bundle,
)
from .chat import (  # noqa: F401
    _CHAT_HISTORY_CHAR_BUDGET,
    _MAX_NOTE_CHARS,
    _MAX_NOTES_PER_REPLY,
    _call_chat_model,
    _history_for_prompt,
    _msg_out,
    _pending_reply,
    _save_new_notes,
    chat_history,
    run_chat_job,
    start_chat,
)
from .common import (  # noqa: F401
    _HANDICAP_VI,
    _LEVEL_VI,
    _call_with_empty_retry,
    _day_label_vi,
    _dm,
    _hdc_vi,
    _ollama_chat,
    _tz,
)
from .debug import (  # noqa: F401
    debug_info,
)
from .directives import (  # noqa: F401
    _METRIC_UNIT_VI,
    _week_actual,
    directive_progress,
)
from .notes import (  # noqa: F401
    add_note,
    delete_note,
    list_notes,
)
from .recap import (  # noqa: F401
    _call_recap_model,
    _recap_to_out,
    get_recaps,
    run_recap_job,
    start_recap,
)
from .recovery import (  # noqa: F401
    recover_stuck_jobs,
)
from .render import (  # noqa: F401
    _MIN_SAMPLE_MATCHES,
    _SN_KIND_VI,
    _bundle_to_text,
    _elo_line,
    _elo_opp_lines,
    _recap_bundle_to_text,
    _snapshot_pair_lines,
    _week_ahead_lines,
    _wr,
)
from .verdict import (  # noqa: F401
    _METRIC_RANGE,
    _call_model,
    _sanitize_directives,
    _to_out,
    get_latest,
    get_status,
    run_generate_job,
    start_generate,
)
