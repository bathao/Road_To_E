"""Render a bundle into the Vietnamese context block the model reads.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from app.features.head_coach import schemas

from .bundle import _period_label_vi
from .common import _HANDICAP_VI, _LEVEL_VI, _day_label_vi, _dm

# Below this many matches a segment is tagged [MẪU NHỎ] in the context block
# and the prompt forbids drawing win-rate conclusions from it.
_MIN_SAMPLE_MATCHES = 5


def _wr(d: dict) -> str:
    wr = d.get("win_rate")
    wr_s = f"{round(wr * 100)}%" if wr is not None else "—"
    played = d.get("played", 0)
    line = f"{played} trận (T{d.get('wins', 0)}/B{d.get('losses', 0)}, thắng {wr_s})"
    # Small samples are labelled so the model is barred from concluding on them.
    if 0 < played < _MIN_SAMPLE_MATCHES:
        line += " [MẪU NHỎ]"
    return line


def _elo_line(m: dict) -> str:
    """One context line for the user's dynamic ELO. Empty string for old
    snapshots stored before the rating existed (they must keep rendering)."""
    elo = m.get("my_elo") or {}
    if not elo:
        return ""
    line = (
        f"ĐIỂM ELO ĐỘNG của học trò: {elo.get('current')} "
        f"(neo {elo.get('anchor')} từ {elo.get('anchor_date')}, "
        f"đã tính {elo.get('counted_matches')} trận)"
    )
    to_e = elo.get("to_rank_e")
    if to_e:
        line += f" · còn {to_e} điểm nữa tới hạng E"

    weekly = elo.get("weekly") or []
    if weekly:
        parts = []
        for w in weekly:
            d = w.get("delta", 0)
            parts.append(
                f"{_dm(w['from'])}–{_dm(w['to'])}: {'+' if d > 0 else ''}{d} "
                f"({w.get('counted')} trận, cuối tuần {w.get('rating_end')})"
            )
        line += "\nDiễn biến ELO theo TUẦN (cũ → mới): " + " · ".join(parts)
    return line + "\n"


def _week_ahead_lines(tournaments: list[dict], today: dt.date) -> str:
    """The next-7-days scaffold for the week plan: one line per day carrying
    the EXACT label the model copies into PlanDay.day, annotated with any
    registered tournament running that day — code does all the calendar math
    (the model used to invent dates when told only 'còn N ngày')."""
    lines = []
    for i in range(7):
        day = today + dt.timedelta(days=i)
        events = []
        for t in tournaments:
            start = dt.date.fromisoformat(t["start_date"])
            end_iso = t.get("end_date")
            end = dt.date.fromisoformat(end_iso) if end_iso else start
            if start <= day <= end:
                total = (end - start).days + 1
                # Most real names already start with "Giải …" — don't stutter.
                name = t["name"]
                tag = name if name.lower().startswith("giải") else f"giải {name}"
                if total > 1:
                    tag += f" — ngày {(day - start).days + 1}/{total}"
                events.append(tag)
        note = "; ".join(events) or "(không có giải)"
        suffix = " (HÔM NAY)" if i == 0 else ""
        lines.append(f"  - {_day_label_vi(day)}{suffix}: {note}")
    return "\n".join(lines)


def _elo_opp_lines(d: dict) -> str:
    """Render the per-opponent ELO split for either bundle's context block."""
    eo = d.get("elo_by_opponent") or {}

    def _fmt(r: dict) -> str:
        return f"{r['name']} {'+' if r['net'] > 0 else ''}{r['net']} ({r['matches']} trận)"

    gains = " · ".join(_fmt(r) for r in eo.get("gains", [])) or "(chưa có)"
    drains = " · ".join(_fmt(r) for r in eo.get("drains", [])) or "(chưa có)"
    return (
        f"  - Nguồn ELO (lấy điểm nhiều nhất từ): {gains}\n"
        f"  - Ngốn ELO (mất điểm nhiều nhất vì): {drains}"
    )


def _bundle_to_text(b: schemas.SourceSummary) -> str:
    """Render the bundle into the Vietnamese context block fed to the model.
    Every number here is computed by code from the database — the model only
    has to reason over the facts, never derive them."""
    t, m, d = b.training, b.match, b.match_detail

    minutes_cat = "; ".join(f"{k}: {v_}p" for k, v_ in m.get("minutes_by_category", {}).items()) or "—"
    muscle = "; ".join(f"{k}×{v_}" for k, v_ in t.get("muscle_volume", {}).items()) or "—"

    hdc = d.get("by_level_handicap", {})
    hdc_lines = "\n".join(
        f"  - Đối thủ {_LEVEL_VI.get(lv, lv)} · {_HANDICAP_VI[dr]}: {_wr(cell)}"
        for lv in ("below", "equal", "above", "unrated")
        for dr in ("even", "receive", "give")
        for cell in [hdc.get(lv, {}).get(dr)]
        if cell
    ) or "  (chưa có dữ liệu)"

    trend_lines = "\n".join(
        f"  - {tb['label']}: {_wr(tb)}"
        for tb in d.get("trend_by_month", [])
        if tb.get("played")
    ) or "  (chưa đủ dữ liệu)"

    # Head-to-head records are per-person facts (naturally few matches) — no
    # small-sample label here; the rule targets win-rate SEGMENTS.
    h2h_lines = "\n".join(
        f"  - {r['name']} ({_LEVEL_VI.get(r['level'], r['level'])}): "
        f"{r.get('played', 0)} trận (T{r.get('wins', 0)}/B{r.get('losses', 0)})"
        f"{'; gần nhất: ' + r['last'] if r.get('last') else ''}"
        + (
            f"\n    diễn biến (cũ → mới): {r['recent']}"
            if r.get("recent")
            else ""
        )
        for r in d.get("top_h2h", [])
    ) or "  (chưa có)"

    def _tour_line(t: dict) -> str:
        d = t.get("days_left", 0)
        when = (
            "ĐANG DIỄN RA"
            if d < 0
            else ("HÔM NAY" if d == 0 else f"còn {d} ngày (bắt đầu {t.get('start_date')})")
        )
        loc = f" tại {t['location']}" if t.get("location") else ""
        limit = f" Giới hạn trình: {t['level_limit']}." if t.get("level_limit") else ""
        if t.get("points_limit"):
            limit += f" Giới hạn điểm: ≤{t['points_limit']} điểm BBTV."
        entries = "; ".join(t.get("entries", [])) or "chưa ghi nội dung"
        note = f" Ghi chú: {t['note']}" if t.get("note") else ""
        # League (2026-09-25): a fixed block of 3–5 round-robin matches, no
        # knockout ladder — the coach must not plan it as a "đi sâu" run.
        fmt = (
            " Thể thức: LEAGUE — đánh vòng tròn 3–5 trận rồi kết thúc, không có"
            " vòng loại trực tiếp, kết quả chỉ tính thắng–thua."
            if t.get("format") == "league"
            else ""
        )
        return f"  - {t.get('name')}{loc}: {when}.{fmt}{limit} Nội dung: {entries}.{note}"

    tour_lines = "\n".join(_tour_line(t) for t in b.tournaments) or (
        "  (chưa đăng ký giải nào)"
    )

    note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.notes
    ) or "  (không có ghi chú)"

    coach_note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.coach_notes
    ) or "  (sổ tay trống)"

    def _sn_line(n: dict) -> str:
        tag_s = f" [{', '.join(n['tags'])}]" if n.get("tags") else ""
        return f"  - {n['date']}{tag_s}: {n['text']}"

    advice_lines = "\n".join(_sn_line(n) for n in b.coach_advice) or (
        "  (không có lời dặn nào đang mở)"
    )
    recap_lines = "\n".join(_sn_line(n) for n in b.session_recaps) or (
        "  (chưa có recap buổi tập nào)"
    )
    lesson_lines = "\n".join(_sn_line(n) for n in b.lessons) or (
        "  (chưa có bài học nào)"
    )

    def _task_line(x: dict) -> str:
        bits = [f"  - [{x['source']} · {x['status']}] {x['title']}"]
        if x.get("note"):
            bits.append(f"({x['note']})")
        if x.get("daily"):
            since = x.get("days_since_last")
            bits.append(
                f"— NHIỆM VỤ HẰNG NGÀY: chuỗi {x.get('streak', 0)} ngày, "
                + (
                    "chưa thực hiện lần nào"
                    if since is None
                    else f"lần cuối cách đây {since} ngày"
                )
            )
        return " ".join(bits)

    task_lines = "\n".join(_task_line(x) for x in b.tasks) or (
        "  (bảng nhiệm vụ trống)"
    )
    memo_lines = "\n".join(f"  - {x['text']}" for x in b.memos) or (
        "  (bảng ghi nhớ trống)"
    )

    racket_total = m.get("racket_minutes_total", 0)
    racket_tr = m.get("racket_minutes_training", 0)
    racket_ma = m.get("racket_minutes_matches", 0)

    return (
        f"Vận động viên: {b.player}.\n\n"
        f"=== KHỐI LƯỢNG TẬP & CẦM VỢT ({m.get('window_days')} ngày gần nhất) ===\n"
        f"Số ngày có hoạt động: {m.get('days_trained')}; ngày thể lực: {m.get('days_physical')}.\n"
        f"Giờ tập có chủ đích: {m.get('minutes_total')} phút ({minutes_cat}).\n"
        f"TỔNG THỜI GIAN CẦM VỢT: {racket_total} phút "
        f"(tập {racket_tr}p + thi đấu ~{racket_ma}p ước từ số set).\n\n"
        f"=== KẾT QUẢ THI ĐẤU ({m.get('window_days')} ngày gần nhất) ===\n"
        f"Đơn: {_wr(m.get('singles', {}))}\n"
        f"Đôi: {_wr(m.get('doubles', {}))}\n"
        f"1v2 (học trò đánh 1 MÌNH vs 2 người): {_wr(m.get('one_v_two', {}))}\n"
        f"2v1 (học trò + đồng đội vs 1 người): {_wr(m.get('two_v_one', {}))}\n"
        f"Gặp đối thủ đánh gai: {_wr(m.get('vs_pips', {}))}\n"
        f"Tổng các trận: {_wr(m.get('overall', {}))}\n"
        f"{_elo_line(m)}\n"
        f"=== PHÂN TÍCH TRẬN SÂU (cửa sổ {d.get('window')}, trận có tên đối thủ) ===\n"
        f"Tách theo hạng đối thủ và CHẤP (điểm chấp mỗi ván; trận có chấp phải diễn giải khác "
        f"trận đánh đồng):\n{hdc_lines}\n"
        f"THEO LOẠI TRẬN: đánh chơi (tập) {_wr(d.get('practice', {}))} · "
        f"đánh độ nhẹ {_wr(d.get('official', {}))} · "
        f"đánh giải (tournament) {_wr(d.get('tournament', {}))}\n"
        f"Xu hướng theo tháng:\n{trend_lines}\n"
        f"Đối đầu nhiều nhất (head-to-head, đơn):\n{h2h_lines}\n"
        f"ELO THEO ĐỐI THỦ trong cửa sổ (net; trận đôi/đồng đội tính cho mọi "
        f"đối thủ có mặt):\n{_elo_opp_lines(d)}\n\n"
        f"=== THỂ LỰC (Training Center) ===\n"
        f"Cấp độ: {t.get('level')}; tổng buổi đã xong: {t.get('total_sessions_done')}; "
        f"7 ngày: {t.get('sessions_last_7d')} buổi; 30 ngày: {t.get('sessions_last_30d')} buổi; "
        f"chuỗi hiện tại: {t.get('current_streak')} ngày; "
        f"số ngày từ buổi gần nhất: {t.get('days_since_last')}; "
        f"điều chỉnh cường độ: {t.get('intensity_bias')}.\n"
        f"Khối lượng theo nhóm cơ: {muscle}\n\n"
        f"=== GIẢI ĐẤU SẮP TỚI (học trò đã đăng ký) ===\n"
        f"{tour_lines}\n\n"
        f"=== 7 NGÀY TỚI (khung kế hoạch tuần — 'day' phải dùng NGUYÊN VĂN "
        f"nhãn ngày dưới đây) ===\n"
        f"{_week_ahead_lines(b.tournaments, dt.date.today())}\n\n"
        f"=== NHIỆM VỤ ĐANG THEO (bảng Tracking — nguồn: HLV trực tiếp / AI "
        f"/ tự giao; nhiệm vụ hằng ngày có chuỗi ngày — khen chuỗi tốt, nhắc "
        f"nhiệm vụ bị bỏ bê) ===\n"
        f"{task_lines}\n\n"
        f"=== ĐIỀU HỌC TRÒ TỰ NHẮC MÌNH MỖI NGÀY (bảng Remember — theo thứ tự ưu "
        f"tiên; tự đặt ra, đối chiếu số liệu xem có đang làm theo không) ===\n"
        f"{memo_lines}\n\n"
        f"=== HLV TRỰC TIẾP ĐANG DẶN (học trò ghi lại; chưa hoàn thành — cần tập tiếp) ===\n"
        f"{advice_lines}\n\n"
        f"=== RECAP CÁC BUỔI TẬP VỚI HLV TRỰC TIẾP (mới nhất trước) ===\n"
        f"{recap_lines}\n\n"
        f"=== KINH NGHIỆM HỌC TRÒ TỰ RÚT RA (nhật ký — mới nhất trước; chủ "
        f"quan, đối chiếu với số liệu khi dùng) ===\n"
        f"{lesson_lines}\n\n"
        f"=== GHI CHÚ HẰNG NGÀY CỦA HỌC TRÒ (mới nhất trước) ===\n"
        f"{note_lines}\n\n"
        f"=== SỔ TAY HLV (mục tiêu/mốc thời gian/ràng buộc đã chốt với học trò) ===\n"
        f"{coach_note_lines}\n"
    )


def _snapshot_pair_lines(stats: dict) -> str:
    """Render the current-vs-previous snapshot for the prompt — every number
    computed by code; the model only compares."""
    cur = stats.get("current") or {}
    prev = stats.get("previous")

    def _pair(label: str, key: str, unit: str = "") -> str:
        line = f"- {label}: {cur.get(key, 0)}{unit}"
        if prev is not None:
            line += f" (kỳ trước: {prev.get(key, 0)}{unit})"
        return line

    def _elo(d: dict) -> str:
        if d.get("elo_end") is None:
            return "chưa có ELO (trước mốc neo)"
        delta = d.get("elo_delta", 0)
        return (
            f"{'+' if delta > 0 else ''}{delta} điểm "
            f"({d.get('elo_counted', 0)} trận tính điểm, cuối kỳ {d.get('elo_end')})"
        )

    def _matches(d: dict) -> str:
        wr = d.get("win_rate")
        wr_s = f"{round(wr * 100)}%" if wr is not None else "—"
        return (
            f"{d.get('matches_played', 0)} trận "
            f"(T{d.get('matches_wins', 0)}/B{d.get('matches_losses', 0)}, thắng {wr_s})"
        )

    lines = [
        _pair("Số ngày có hoạt động", "days_trained"),
        _pair("Ngày thể lực", "days_physical"),
        _pair("Buổi thể lực hoàn thành (Training Center)", "physical_sessions"),
        _pair("Phút tập có chủ đích", "minutes_total", "p"),
        _pair("Tổng phút cầm vợt", "racket_minutes_total", "p"),
        f"- Trận đấu: {_matches(cur)}"
        + (f" (kỳ trước: {_matches(prev)})" if prev is not None else ""),
        _pair("Đối thủ MỚI lần đầu gặp (đánh ĐƠN)", "new_opponents"),
        f"- ELO: {_elo(cur)}" + (f" (kỳ trước: {_elo(prev)})" if prev is not None else ""),
    ]
    if prev is None:
        lines.append("(Kỳ liền trước chưa có dữ liệu theo dõi — không so sánh được.)")
    return "\n".join(lines)


_SN_KIND_VI = {
    "advice": "HLV dặn",
    "drill": "Bài tập",
    "recap": "Recap buổi tập",
    "lesson": "Bài học tự rút ra",
}


def _recap_bundle_to_text(b: dict) -> str:
    """Render the recap bundle into the Vietnamese context block."""
    label = _period_label_vi(
        b["period_type"],
        dt.date.fromisoformat(b["period_start"]),
        dt.date.fromisoformat(b["period_end"]),
    )
    r = b.get("results", {})
    k = b.get("by_kind", {})

    minutes_cat = "; ".join(
        f"{cat}: {v_}p" for cat, v_ in b.get("minutes_by_category", {}).items()
    ) or "—"

    weekly = b.get("elo_weekly") or []
    elo_lines = ""
    if len(weekly) > 1:  # month recaps: show the week-by-week path
        parts = [
            f"{_dm(w['from'])}–{_dm(w['to'])}: "
            f"{'+' if w['delta'] > 0 else ''}{w['delta']} ({w['counted']} trận, "
            f"cuối tuần {w['rating_end']})"
            for w in weekly
        ]
        elo_lines = "Diễn biến ELO theo tuần trong kỳ: " + " · ".join(parts) + "\n"

    h2h_lines = "\n".join(
        f"  - {p['name']} ({_LEVEL_VI.get(p['level'], p['level'])}): "
        f"{p['played']} trận (T{p['wins']}/B{p['losses']})"
        + (
            f"\n    diễn biến (cũ → mới): {p['recent']}"
            if p.get("recent")
            else ""
        )
        for p in b.get("top_h2h", [])
    ) or "  (không có trận đơn có tên đối thủ trong kỳ)"

    def _sn_line(n: dict) -> str:
        tag_s = f" [{', '.join(n['tags'])}]" if n.get("tags") else ""
        kind = _SN_KIND_VI.get(n.get("kind", ""), n.get("kind", ""))
        return f"  - {n['date']} · {kind}{tag_s}: {n['text']}"

    sn_lines = "\n".join(_sn_line(n) for n in b.get("session_notes", [])) or (
        "  (nhật ký trống trong kỳ)"
    )
    task_lines = "\n".join(
        f"  - [{x['source']} · {x['status']}] {x['title']}"
        + (
            f" — hằng ngày: chuỗi {x.get('streak', 0)} ngày"
            + (
                f", lần cuối cách {x['days_since_last']} ngày"
                if x.get("days_since_last") is not None
                else ", chưa thực hiện lần nào"
            )
            if x.get("daily")
            else ""
        )
        for x in b.get("tasks", [])
    ) or "  (bảng nhiệm vụ trống)"
    memo_lines = "\n".join(
        f"  - {x['text']}" for x in b.get("memos", [])
    ) or "  (bảng ghi nhớ trống)"
    note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.get("day_notes", [])
    ) or "  (không có ghi chú)"
    coach_note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.get("coach_notes", [])
    ) or "  (sổ tay trống)"

    return (
        f"Vận động viên: {b.get('player')}.\n"
        f"KỲ TỔNG KẾT: {label}.\n\n"
        f"=== SỐ LIỆU KỲ NÀY (so với KỲ LIỀN TRƯỚC) ===\n"
        f"{_snapshot_pair_lines(b.get('stats', {}))}\n"
        f"Phút tập theo hạng mục (kỳ này): {minutes_cat}\n\n"
        f"=== KẾT QUẢ THI ĐẤU TRONG KỲ ===\n"
        f"Đơn: {_wr(r.get('singles', {}))}\n"
        f"Đôi: {_wr(r.get('doubles', {}))}\n"
        f"1v2 (học trò đánh 1 MÌNH vs 2 người): {_wr(r.get('one_v_two', {}))}\n"
        f"2v1 (học trò + đồng đội vs 1 người): {_wr(r.get('two_v_one', {}))}\n"
        f"Gặp đối thủ đánh gai: {_wr(r.get('vs_pips', {}))}\n"
        f"Tổng các trận: {_wr(r.get('overall', {}))}\n"
        f"THEO LOẠI TRẬN: đánh chơi (tập) {_wr(k.get('practice', {}))} · "
        f"đánh độ nhẹ {_wr(k.get('official', {}))} · "
        f"đánh giải (tournament) {_wr(k.get('tournament', {}))}\n"
        f"{elo_lines}"
        f"Đối đầu nhiều nhất trong kỳ (đơn):\n{h2h_lines}\n"
        f"ELO THEO ĐỐI THỦ trong kỳ (net; trận đôi/đồng đội tính cho mọi đối "
        f"thủ có mặt):\n{_elo_opp_lines(b)}\n\n"
        f"=== NHẬT KÝ TRONG KỲ (lời HLV dặn / bài tập / recap / bài học học "
        f"trò tự rút ra) ===\n"
        f"{sn_lines}\n\n"
        f"=== NHIỆM VỤ ĐANG THEO CUỐI KỲ (bảng Tracking — nhận xét chuỗi "
        f"ngày giữ được / bị bỏ bê) ===\n"
        f"{task_lines}\n\n"
        f"=== ĐIỀU HỌC TRÒ TỰ NHẮC MÌNH MỖI NGÀY (bảng Remember — tự đặt ra; "
        f"nhận xét kỳ này có làm theo không) ===\n"
        f"{memo_lines}\n\n"
        f"=== GHI CHÚ HẰNG NGÀY CỦA HỌC TRÒ TRONG KỲ ===\n"
        f"{note_lines}\n\n"
        f"=== SỔ TAY HLV (mục tiêu/ràng buộc đã chốt — bối cảnh, có thể ngoài kỳ) ===\n"
        f"{coach_note_lines}\n"
    )
