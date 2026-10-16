"""Business logic for the Daily Tracker tab — a package since 2026-10-16.

Modules (leaf → composite): text, periods, tally · players · matches · grid
· export · journal · boards · coaches · activities · stats · match_stats ·
rating_analytics.
Every public AND test-used private name is re-exported here so callers
(router, head_coach, tactics, tests) keep using ``service.X``; new code
should import from the submodule that owns the name.
"""
from __future__ import annotations

# The user's dynamic ELO lives in rating.py; these re-exports keep the old
# ``service.compute_my_rating`` call sites working.
from app.features.tracker.rating import (  # noqa: F401
    compute_my_rating,
    get_my_anchor_date,
    get_my_points,
    handicap_bonus,
    set_my_points,
    snapshot_match_points,
)

from .activities import (  # noqa: F401
    EVENT_SEARCH_LIMIT,
    list_categories,
    list_events,
    set_physical_checks,
    upsert_activity,
    upsert_day_note,
)
from .boards import (  # noqa: F401
    _TASK_DONE_KEEP_DAYS,
    _memo_to_out,
    _task_streak,
    _task_to_out,
    create_memo,
    create_task,
    delete_memo,
    delete_task,
    list_memos,
    list_tasks,
    reorder_memos,
    set_task_check,
    update_memo,
    update_task,
)
from .coaches import (  # noqa: F401
    COACH_PACKAGE_SIZE,
    _coach_sessions,
    _counts_toward_package,
    _non_package_coach_ids,
    coach_package_start_allowed,
    compute_coach_packages,
    create_coach,
    default_coach_id,
    list_coaches,
    start_next_coach_package,
)
from .export import (  # noqa: F401
    _COLOR_HEX,
    _RATING_HEX,
    _build_grid,
    export_csv,
    export_xlsx,
)
from .grid import (  # noqa: F401
    _GROUP_ORDER,
    _NOTE_SNIPPET_LEN,
    OVERALL_GREEN_RACKET_MINUTES,
    PACKAGE_MARK,
    PHYSICAL_ITEM_LABELS,
    PHYSICAL_ITEMS,
    RACKET_DURATION_KEYS,
    RACKET_MINUTES_PER_SET,
    RangeData,
    _grid_cells,
    _load_range,
    _match_result_lines,
    _physical_dates,
    build_week,
    compute_overall_colors,
    earliest_data_date,
    format_duration,
    format_match_cell,
    format_physical_cell,
    has_data_between,
    latest_data_date,
    note_snippet,
    physical_checks_by_date,
    physical_is_yellow,
    racket_minutes_by_day,
)
from .journal import (  # noqa: F401
    SESSION_NOTE_TAG_LABELS,
    SESSION_NOTE_TAGS,
    SN_KIND_ADVICE,
    SN_KIND_DRILL,
    SN_KIND_LESSON,
    SN_KIND_RECAP,
    _group_day_matches,
    _journal_coach_names,
    _journal_day_match_rows,
    _journal_day_out,
    _journal_group_out,
    _journal_matches,
    _journal_result_token,
    clean_session_tags,
    create_session_note,
    delete_session_note,
    has_coach_session,
    journal_day,
    journal_days,
    list_active_advice,
    session_note_to_out,
    set_match_note,
    update_session_note,
)
from .match_stats import (  # noqa: F401
    _CATEGORY_KEY,
    _LEVEL_ORDER,
    MATCH_STATS_FLOOR,
    _h2h_accumulate,
    _H2HAcc,
    _opponent_ids_in,
    _query_named_matches,
    _record_tail,
    _trend_buckets,
    build_handicap_split,
    build_match_stats,
    count_new_opponents,
)
from .matches import (  # noqa: F401
    _annotate_elo,
    create_match,
    delete_match,
    get_or_create_event,
    last_handicap_vs,
    list_player_matches,
    match_to_out,
    next_order,
    normalize_handicap_pattern,
    tournament_default_event,
    update_match,
)
from .periods import (  # noqa: F401
    _WEEKDAYS,
    _bucket_ranges,
    _date_range,
    _first_of_month,
    _last_of_month,
    _next_month,
)
from .players import (  # noqa: F401
    _PICKER_RECENT_DAYS,
    _RANK_TOPS,
    _level_of,
    _rank_band,
    _refreeze_player_snapshots,
    create_or_get_player,
    level_from_points,
    list_players,
    list_players_db,
    player_to_out,
    update_player,
)
from .rating_analytics import (  # noqa: F401
    build_rating_breakdown,
    elo_by_opponent,
)
from .stats import (  # noqa: F401
    build_breakdown,
    build_stats,
)
from .tally import (  # noqa: F401
    _NEWEST_FIRST,
    _blank_match_stats,
    _finalize_match_stats,
    _is_vs_pips,
    _playing_matches,
    _result_letter,
    _result_of,
    _tally,
    win_rate,
)
from .text import (  # noqa: F401
    _fold,
)
