"""Static program reference for the Training Center.

This module is the single source of truth for *what* a session contains. The DB
(models.py) only stores the player's progress through these programs. Nothing
here is persisted, so editing it changes future sessions without a migration.

KNEE-SAFE curriculum. The player has grade-1 knee osteoarthritis, so this program
deliberately AVOIDS deep squats, lunges, and jumping/plyometrics. It builds the
muscles around the knee (quads via leg raises, glutes/hips, hamstrings, calves)
and the rotational core, using low-load, low-impact home exercises. "Progression"
across levels = more reps/holds + slightly harder variants, NOT more impact.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Shown under the header so the player is reminded of the knee constraint.
SAFETY_NOTE_VI = (
    "Ưu tiên CƠ ĐÙI để giảm tải lên khớp gối (theo chỉ định bác sĩ). "
    "Không squat sâu / lunge / bật nhảy mạnh. Bài quad nhẹ (quad set, nâng chân, "
    "short-arc) tập được hằng ngày. Dừng ngay nếu đau gối."
)

# Day-types a session focuses on + the Vietnamese focus label in the header.
DAY_TYPES = ("legs", "core", "balance")
DAY_FOCUS_VI = {
    "legs": "Cơ đùi (ưu tiên) — khoẻ đùi để giảm tải gối",
    "core": "Cơ lõi: xoay & kháng xoay",
    "balance": "Thăng bằng · vai · cổ tay (bổ trợ TT, nhẹ gối)",
}
# A 6-session micro-cycle that PRIORITISES quads: legs 3/6, core 2/6, balance 1/6.
# Quad-strengthening is the evidence-based priority for knee OA, so leg days come
# up every other session.
DAY_CYCLE = ("legs", "core", "legs", "balance", "legs", "core")

# Levels, in unlock order.
LEVELS = ("foundation", "explosive", "tt_specific")
LEVEL_VI = {
    "foundation": "Căn bản",
    "explosive": "Sức bền & ổn định",
    "tt_specific": "Chuyên biệt (nhẹ khớp gối)",
}
LEVEL_GOAL_VI = {
    "foundation": "Kích hoạt đùi/mông/hông KHÔNG tải sâu gối; làm quen giữ trụ.",
    "explosive": "Tăng sức bền cơ quanh gối + ổn định lõi, vẫn nhẹ khớp.",
    "tt_specific": "Mô phỏng di chuyển bóng bàn cường độ vừa, low-impact, bảo vệ gối.",
}
# Number of sessions ("Day" tiles) per level.
SESSIONS_PER_LEVEL = 21


@dataclass(frozen=True)
class Exercise:
    key: str
    name_vi: str
    muscle: str  # nhóm cơ
    tt_benefit: str  # why it helps table tennis (motivation, shown on the card)
    kind: str  # "reps" | "timed"
    target: dict  # {"sets":3,"reps":20} or {"sets":3,"sec":45}
    day_type: str  # legs | core | balance
    per_side: bool = False  # target is per side (left/right)
    gif: str = ""  # served from frontend /exercises/<key>.gif (placeholder ok)
    form_cue: str = ""  # form tip / safety warning


def _gif(key: str) -> str:
    return f"/exercises/{key}.gif"


# ---- Exercise library (knee-safe; reused across sessions) ----
_EX = [
    # --- legs: QUAD-FIRST, then glutes/hips/calves; no deep knee load ---
    # The two evidence-based knee-OA staples — safe to do daily.
    Exercise("quad_set", "Gồng cơ đùi (quad set)", "Đùi trước (đẳng trường)",
             "Bài nền số 1 cho gối: đùi trước khoẻ → giảm lực lên khớp gối.",
             "reps", {"sets": 3, "reps": 12}, "legs",
             gif=_gif("quad_set"),
             form_cue="Chân duỗi, SIẾT cơ đùi ép khoeo xuống, GIỮ ~5 giây rồi thả. Không đau khớp."),
    Exercise("short_arc_quad", "Duỗi gối biên độ ngắn (kê khăn)", "Đùi trước (VMO)",
             "Mạnh đùi trước trong tầm KHÔNG đau — trực tiếp bảo vệ gối.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("short_arc_quad"),
             form_cue="Kê cuộn khăn dưới khoeo, duỗi thẳng cẳng chân rồi hạ chậm; biên độ NHỎ."),
    Exercise("straight_leg_raise", "Nâng chân thẳng (đùi trước)", "Đùi trước (quad)",
             "Khoẻ đùi trước để giữ trụ gối vững khi đánh.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("straight_leg_raise"),
             form_cue="Nằm ngửa, gối THẲNG, nâng chân ~30–40°, hạ chậm. Dừng nếu đau gối."),
    Exercise("side_leg_raise", "Nâng chân ngang (đùi/hông ngoài)", "Đùi ngoài, hông",
             "Khoẻ hông để bước ngang vững, không ngã.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("side_leg_raise"),
             form_cue="Nằm nghiêng, nâng chân thẳng sang ngang; không lăn người ra sau."),
    Exercise("prone_leg_raise", "Nằm sấp nâng chân (đùi sau)", "Đùi sau, mông",
             "Cân bằng nhóm cơ quanh gối, giảm tải khớp.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("prone_leg_raise"),
             form_cue="Nằm sấp, siết mông nâng chân thẳng lên biên độ nhỏ; không ưỡn lưng."),
    Exercise("wall_sit_shallow", "Wall Sit (gối nông)", "Đùi trước (tĩnh)",
             "Sức bền đùi để giữ tư thế thủ thấp.",
             "timed", {"sets": 3, "sec": 30}, "legs",
             gif=_gif("wall_sit_shallow"),
             form_cue="Tựa lưng tường, gối cong NÔNG (không xuống 90°). Đau là dừng."),
    Exercise("glute_bridge", "Cầu mông (glute bridge)", "Mông, đùi sau",
             "Mông khoẻ ổn định thân, đỡ tải lên gối.",
             "reps", {"sets": 3, "reps": 15}, "legs",
             gif=_gif("glute_bridge"),
             form_cue="Nằm ngửa, gối co, nâng hông siết mông; không ưỡn lưng quá."),
    Exercise("calf_raise", "Nhón gót (mũi chân)", "Bắp chân, cổ chân",
             "Lực cổ chân/bắp chân cho bước bật nhẹ.",
             "reps", {"sets": 3, "reps": 20}, "legs",
             gif=_gif("calf_raise"),
             form_cue="Đứng nhón gót lên–xuống chậm; vịn tường nếu cần."),
    Exercise("mini_squat", "Squat nông (nhẹ khớp)", "Đùi, mông",
             "Khoẻ chân dạng squat mà không tải sâu gối.",
             "reps", {"sets": 3, "reps": 15}, "legs",
             gif=_gif("mini_squat"),
             form_cue="Cong gối NÔNG ~30°, gối không vượt mũi chân; vịn ghế nếu cần."),
    Exercise("lateral_toe_steps", "Di chuyển ngang nhón chân", "Bắp chân, hông (footwork)",
             "Mô phỏng bước ngang bóng bàn — nhón chân nên nhẹ khớp gối.",
             "timed", {"sets": 3, "sec": 30}, "legs",
             gif=_gif("lateral_toe_steps"),
             form_cue="Nhón gót, bước ngang qua–lại nhẹ nhàng; KHÔNG khuỵu gối sâu, không nhảy."),
    Exercise("toe_stand_hold", "Đứng nhón chân (giữ)", "Bắp chân, cổ chân, thăng bằng",
             "Vững cổ chân + trụ nhẹ nhàng, không tải gối.",
             "timed", {"sets": 3, "sec": 30}, "balance",
             gif=_gif("toe_stand_hold"),
             form_cue="Nhón cả hai gót lên và GIỮ; vịn tường nếu mất thăng bằng."),
    Exercise("single_leg_glute_bridge", "Cầu mông một chân", "Mông (một bên)",
             "Sức mạnh đơn chân, cân bằng trái/phải.",
             "reps", {"sets": 3, "reps": 12}, "legs", per_side=True,
             gif=_gif("single_leg_glute_bridge"),
             form_cue="Cầu mông nhưng duỗi một chân; giữ hông ngang, không lệch."),
    Exercise("lateral_lunge", "Chùng chân ngang (lateral lunge)", "Mông, đùi trong, đùi",
             "Khoẻ mông + bước ngang rộng cứu bóng. Mông khoẻ giúp giảm tải gối.",
             "reps", {"sets": 2, "reps": 8}, "legs", per_side=True,
             gif=_gif("lateral_lunge"),
             form_cue="Bước rộng sang ngang, dồn trọng tâm chân trụ, gối theo hướng mũi chân; "
                      "KHÔNG xuống sâu (giữ nông), vịn ghế nếu cần. Đau gối là dừng."),
    Exercise("inner_thigh_raise", "Nâng chân trong (đùi trong)", "Đùi trong",
             "Đùi trong giữ trụ khi bước rộng cứu bóng.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("inner_thigh_raise"),
             form_cue="Nằm nghiêng, chân trên gác ra trước, nâng chân dưới lên."),
    Exercise("hip_hinge", "Gập hông đứng (hip hinge)", "Đùi sau, mông, lưng dưới",
             "Tạo lực từ chân–hông lên thân (chuỗi sau) cho cú giật mạnh; gối thẳng nên nhẹ khớp.",
             "reps", {"sets": 3, "reps": 12}, "legs",
             gif=_gif("hip_hinge"),
             form_cue="Chân rộng bằng vai, GỐI HƠI MỀM (không gập sâu), đẩy MÔNG ra sau, lưng thẳng; "
                      "cúi tới khi căng đùi sau rồi siết mông đứng dậy. Lực ở hông/đùi sau, KHÔNG ở gối."),
    # --- core: rotational + anti-rotation + stability, no knee load ---
    Exercise("plank", "Plank", "Toàn bộ lõi",
             "Nền tảng ổn định thân khi đánh.",
             "timed", {"sets": 3, "sec": 30}, "core",
             gif=_gif("plank"),
             form_cue="Chống khuỷu, siết bụng+mông, lưng không võng."),
    Exercise("crunch", "Gập bụng ngắn", "Bụng trên",
             "Tăng sức giữ trọng tâm.",
             "reps", {"sets": 3, "reps": 20}, "core",
             gif=_gif("crunch"),
             form_cue="Cuộn vai lên, không kéo cổ."),
    Exercise("dead_bug", "Dead Bug", "Lõi sâu (an toàn lưng/gối)",
             "Lõi ổn định mà không tải khớp gối.",
             "reps", {"sets": 3, "reps": 16}, "core",
             gif=_gif("dead_bug"),
             form_cue="Nằm ngửa, hạ tay & chân đối diện; ép lưng sát sàn."),
    Exercise("double_leg_lift_hold", "Nằm ngửa nâng hai chân & giữ", "Bụng dưới + đùi trước (tĩnh)",
             "Vừa siết bụng dưới vừa gồng đùi trước giữ trụ — gối thẳng nên không tải khớp.",
             "timed", {"sets": 3, "sec": 20}, "core",
             gif=_gif("double_leg_lift_hold"),
             form_cue="Nâng hai chân thẳng khỏi sàn vài chục cm rồi GIỮ; ÉP lưng sát sàn. "
                      "Nếu lưng cong/đau thì nâng chân cao hơn hoặc hơi co gối."),
    Exercise("side_plank", "Plank nghiêng", "Cơ lườn",
             "Đánh xa bàn không bị lệch người.",
             "timed", {"sets": 3, "sec": 25}, "core", per_side=True,
             gif=_gif("side_plank"),
             form_cue="Thân thẳng một đường, hông không võng."),
    Exercise("plank_knee_rotation", "Plank xoay hông qua lại", "Cơ liên sườn, lõi xoay, vai",
             "Xoay lõi + vai vững cho lực xoáy cú giật. Tập trên cẳng tay nên gối KHÔNG chịu lực.",
             "reps", {"sets": 2, "reps": 8}, "core", per_side=True,
             gif=_gif("plank_knee_rotation"),
             form_cue="Giữ plank cẳng tay vững, GỐI THẲNG; xoay hông cho hông/gối lật sang hai bên, "
                      "từ tốn có kiểm soát. Trọng tâm ở cẳng tay + mũi chân, KHÔNG quỳ/dồn lên gối. "
                      "Vai gánh lực đáng kể — dừng nếu vai hoặc gối khó chịu."),
    Exercise("plank_shoulder_tap", "Plank chạm vai (kháng xoay)", "Lõi kháng xoay, vai",
             "Giữ thân KHÔNG lắc khi tay hoạt động — đúng yêu cầu ổn định lúc vung vợt.",
             "reps", {"sets": 3, "reps": 10}, "core", per_side=True,
             gif=_gif("plank_shoulder_tap"),
             form_cue="Plank cao (chống tay), GỐI THẲNG, chân mở rộng cho vững; lần lượt chạm tay lên "
                      "vai đối diện mà HÔNG KHÔNG lắc. Lực ở tay + mũi chân, không dồn gối."),
    Exercise("bird_dog", "Bird-dog (tay–chân chéo)", "Lõi sâu, mông, lưng (chuỗi sau)",
             "Ổn định thân khi vươn người cứu bóng; phối hợp chéo tay–chân.",
             "reps", {"sets": 3, "reps": 10}, "core", per_side=True,
             gif=_gif("bird_dog"),
             form_cue="Quỳ chống tay (KÊ ĐỆM/khăn gấp dưới gối), duỗi thẳng tay và chân ĐỐI DIỆN, "
                      "giữ 2 giây rồi đổi bên; lưng phẳng, không võng. Cộm/đau gối thì đổi sang Dead Bug."),
    Exercise("bicycle_crunch", "Gập bụng xe đạp", "Bụng + lườn xoay",
             "Phối hợp xoay lõi liên tục như khi đôi công.",
             "reps", {"sets": 3, "reps": 20}, "core",
             gif=_gif("bicycle_crunch"),
             form_cue="Chạm khuỷu–gối đối diện chậm; gối không cần co sâu."),
    Exercise("russian_twist", "Russian Twist", "Cơ lườn xoay",
             "Chính là vòng xoay của cú giật thuận/trái tay.",
             "reps", {"sets": 3, "reps": 24}, "core",
             gif=_gif("russian_twist"),
             form_cue="Xoay từ lườn, không giật cổ; lưng dưới giữ ổn định."),
    Exercise("standing_trunk_twist", "Đứng xoay lườn", "Lườn xoay (đứng)",
             "Tập đúng vòng xoay thân của cú giật, đứng nên không tải gối.",
             "reps", {"sets": 3, "reps": 24}, "core",
             gif=_gif("standing_trunk_twist"),
             form_cue="Chân đứng vững (gối thẳng tự nhiên), xoay thân trái–phải từ hông/lườn."),
    Exercise("wood_chop", "Xoay chéo lườn (đốn củi)", "Lườn xoay chéo",
             "Truyền lực xoáy chéo như khi giật/bạt.",
             "reps", {"sets": 3, "reps": 20}, "core", per_side=True,
             gif=_gif("wood_chop"),
             form_cue="Vung tay chéo từ cao xuống thấp, xoay lườn; gối chỉ hơi mềm, KHÔNG khuỵu sâu."),
    # --- balance & recovery ---
    Exercise("single_leg_balance", "Đứng một chân", "Hông, cổ chân",
             "Trụ vững khi phải rướn người cứu bóng.",
             "timed", {"sets": 3, "sec": 30}, "balance", per_side=True,
             gif=_gif("single_leg_balance"),
             form_cue="Đứng một chân, siết hông; bám điểm tựa nếu loạng choạng."),
    Exercise("hamstring_stretch", "Giãn cơ đùi sau", "Đùi sau",
             "Giữ biên độ bước, tránh căng cơ.",
             "timed", {"sets": 2, "sec": 40}, "balance", per_side=True,
             gif=_gif("hamstring_stretch"),
             form_cue="Lưng thẳng, gập từ hông; không nảy."),
    Exercise("groin_stretch", "Giãn cơ háng", "Háng",
             "Tránh chấn thương khi chạy ngang.",
             "timed", {"sets": 2, "sec": 40}, "balance", per_side=True,
             gif=_gif("groin_stretch"),
             form_cue="Giãn tới căng nhẹ, không nảy."),
    Exercise("gentle_bounce", "Nhún nhẹ trên mũi chân", "Bắp chân, nhịp (low-impact)",
             "Tập nhịp split-step nhẹ nhàng, không hại gối.",
             "timed", {"sets": 3, "sec": 30}, "balance",
             gif=_gif("gentle_bounce"),
             form_cue="Nhún nhẹ trên mũi chân, tiếp đất mềm; KHÔNG nhảy cao."),
    Exercise("quad_stretch", "Giãn đùi trước", "Đùi trước",
             "Giãn cơ đùi quanh gối, giảm cứng khớp.",
             "timed", {"sets": 2, "sec": 30}, "balance", per_side=True,
             gif=_gif("quad_stretch"),
             form_cue="Đứng vịn tường, kéo gót về mông NHẸ NHÀNG, không ép."),
    Exercise("single_leg_eyes_closed", "Đứng một chân nhắm mắt", "Hông, cổ chân (nâng cao)",
             "Phản xạ thăng bằng tốt hơn khi di chuyển nhanh.",
             "timed", {"sets": 3, "sec": 40}, "balance", per_side=True,
             gif=_gif("single_leg_eyes_closed"),
             form_cue="Như đứng một chân nhưng nhắm mắt; đứng cạnh tường để bám."),
    # --- upper body / wrist / mobility: TT-specific, all knee-safe (đứng/nằm) ---
    Exercise("wall_pushup", "Chống đẩy vào tường", "Ngực, vai, tay sau",
             "Sức & sức bền tay–vai cho cú đánh ổn định; đứng nên KHÔNG tải gối.",
             "reps", {"sets": 3, "reps": 12}, "balance",
             gif=_gif("wall_pushup"),
             form_cue="Đứng cách tường một tầm tay, chống tay ngang vai, hạ người vào tường rồi đẩy ra; "
                      "thân thẳng, gối thẳng. Muốn nặng hơn thì đứng xa tường hơn."),
    Exercise("wrist_curl", "Cuộn & xoay cổ tay (cẳng tay)", "Cẳng tay, cổ tay",
             "Cổ tay khoẻ & linh hoạt = ma sát/độ XOÁY tốt hơn ở cú giật, gò.",
             "reps", {"sets": 3, "reps": 15}, "balance", per_side=True,
             gif=_gif("wrist_curl"),
             form_cue="Ngồi, cẳng tay tựa đùi, cầm vật nhẹ (chai nước): cuộn cổ tay lên–xuống rồi "
                      "xoay trong–ngoài chậm rãi. Nhẹ nhàng, không đau cổ tay."),
    Exercise("scapular_yt", "Nằm sấp nâng tay (chữ Y–T)", "Vai sau, cơ bả vai, lưng trên",
             "Vai khoẻ & đúng tư thế → bền vai, ít chấn thương khi đánh nhiều.",
             "reps", {"sets": 3, "reps": 12}, "balance",
             gif=_gif("scapular_yt"),
             form_cue="Nằm sấp, trán tựa nhẹ, nâng hai tay khỏi sàn theo hình chữ Y rồi chữ T, "
                      "siết bả vai; KHÔNG nhún vai lên tai. Không tải gối."),
    Exercise("thoracic_rotation", "Xoay ngực (mở sách)", "Linh hoạt ngực – lườn",
             "Tăng biên độ xoay thân → cú giật/bạt vươn xa & mượt hơn.",
             "reps", {"sets": 2, "reps": 10}, "balance", per_side=True,
             gif=_gif("thoracic_rotation"),
             form_cue="Nằm nghiêng, hai gối co chồng nhau (KHÔNG tải lực), hai tay duỗi trước; mở tay "
                      "trên xoay ngực ra sau như mở trang sách, mắt theo tay. Nhẹ nhàng; ngồi xoay cũng được."),
    # --- warm-up (gentle knee mobility before the session; not counted) ---
    Exercise("knee_mobility", "Làm nóng gối (gập–duỗi nhẹ)", "Khớp gối (làm nóng)",
             "Làm trơn khớp gối trước khi tập, giảm cứng.",
             "timed", {"sets": 1, "sec": 60}, "warmup",
             gif=_gif("knee_mobility"),
             form_cue="Ngồi/đứng, gập–duỗi gối biên độ thoải mái + xoay cổ chân. Nhẹ nhàng."),
    Exercise("march_in_place", "Giậm chân tại chỗ nhẹ", "Toàn thân (làm nóng)",
             "Tăng tuần hoàn, làm nóng cơ trước khi tập.",
             "timed", {"sets": 1, "sec": 40}, "warmup",
             gif=_gif("march_in_place"),
             form_cue="Giậm chân nhẹ tại chỗ, không nhấc cao, không bật nhảy."),
]
EXERCISES: dict[str, Exercise] = {e.key: e for e in _EX}

# A short warm-up before, and a cool-down stretch after, every session. These are
# guidance only — shown in the UI / workout player but NOT tracked as items and
# NOT counted toward completion (they're the lead-in / wind-down, not "the work").
WARMUP_KEYS = ("knee_mobility", "march_in_place")
COOLDOWN_KEYS = ("quad_stretch", "hamstring_stretch")


def warmup_exercises() -> list[Exercise]:
    return [EXERCISES[k] for k in WARMUP_KEYS if k in EXERCISES]


def cooldown_exercises() -> list[Exercise]:
    return [EXERCISES[k] for k in COOLDOWN_KEYS if k in EXERCISES]


# Step-by-step "how to do it" for each exercise (Vietnamese), shown in the
# expandable "Hướng dẫn chi tiết" on the card. Kept here (not on the Exercise
# rows) so the dataclass calls stay readable and all instructions live together.
HOW_TO: dict[str, tuple[str, ...]] = {
    # --- legs ---
    "quad_set": (
        "Ngồi hoặc nằm, chân tập duỗi thẳng trên sàn.",
        "Siết cơ đùi trước, ép mặt sau gối xuống sàn.",
        "Giữ ~5 giây rồi thả lỏng. Lặp lại.",
    ),
    "short_arc_quad": (
        "Nằm/ngồi, kê cuộn khăn (hoặc gối ôm) dưới khoeo chân.",
        "Giữ đùi trên khăn, duỗi thẳng cẳng chân lên.",
        "Giữ 2 giây rồi hạ chậm. Biên độ NHỎ, không đau.",
    ),
    "straight_leg_raise": (
        "Nằm ngửa, một chân co (bàn chân đặt sàn), chân tập duỗi thẳng.",
        "Siết đùi, nâng chân thẳng lên ~30–40 cm.",
        "Giữ 1–2 giây, hạ chậm. Gối LUÔN thẳng.",
    ),
    "side_leg_raise": (
        "Nằm nghiêng, hai chân duỗi thẳng chồng lên nhau.",
        "Nâng chân trên thẳng lên (sang ngang), không gập gối.",
        "Hạ chậm. Không lăn người ra sau. Đổi bên.",
    ),
    "prone_leg_raise": (
        "Nằm sấp, hai chân duỗi.",
        "Siết mông, nâng một chân thẳng khỏi sàn biên độ nhỏ.",
        "Giữ 1–2 giây, hạ. Không ưỡn lưng. Đổi bên.",
    ),
    "wall_sit_shallow": (
        "Tựa lưng vào tường, hai chân bước ra trước.",
        "Trượt xuống cho gối cong NÔNG (không tới 90°).",
        "Giữ, thở đều. Đau gối thì đứng cao hơn.",
    ),
    "glute_bridge": (
        "Nằm ngửa, hai gối co, bàn chân đặt sàn rộng bằng hông.",
        "Siết mông nâng hông thành đường thẳng vai–hông–gối.",
        "Giữ 1–2 giây, hạ chậm. Không ưỡn lưng.",
    ),
    "calf_raise": (
        "Đứng thẳng, vịn ghế/tường nếu cần.",
        "Nhón cả hai gót lên cao hết mức.",
        "Hạ gót chậm. Lặp lại.",
    ),
    "mini_squat": (
        "Đứng chân rộng bằng vai, vịn ghế nếu cần.",
        "Đẩy mông ra sau, cong gối NÔNG ~30°.",
        "Đứng dậy siết mông. Gối không vượt mũi chân.",
    ),
    "lateral_toe_steps": (
        "Nhón nhẹ trên mũi chân, gối hơi mềm.",
        "Bước ngang sang phải vài bước rồi sang trái.",
        "Nhẹ nhàng, KHÔNG khuỵu gối sâu, không nhảy.",
    ),
    "single_leg_glute_bridge": (
        "Nằm ngửa như cầu mông, duỗi thẳng một chân lên.",
        "Siết mông nâng hông bằng chân trụ còn lại.",
        "Giữ hông NGANG (không lệch), hạ chậm. Đổi bên.",
    ),
    "lateral_lunge": (
        "Đứng chân rộng, vịn ghế nếu cần.",
        "Dồn trọng tâm sang một chân, đẩy mông ra sau, gối theo hướng mũi chân.",
        "Giữ NÔNG rồi đẩy về giữa. Không xuống sâu. Đổi bên.",
    ),
    "inner_thigh_raise": (
        "Nằm nghiêng, chân trên co gác ra trước mặt.",
        "Chân dưới duỗi thẳng, nâng lên khỏi sàn.",
        "Hạ chậm. Đổi bên.",
    ),
    "hip_hinge": (
        "Đứng chân rộng bằng vai, gối HƠI MỀM (không gập sâu).",
        "Đẩy MÔNG ra sau, gập người tới, lưng thẳng, tới khi căng đùi sau.",
        "Siết mông đứng dậy. Lực ở hông/đùi sau, KHÔNG ở gối.",
    ),
    # --- core ---
    "plank": (
        "Chống hai khuỷu tay xuống sàn (dưới vai), mũi chân chống.",
        "Siết bụng + mông, thân thẳng MỘT đường.",
        "Giữ, thở đều. Lưng không võng, mông không chổng.",
    ),
    "crunch": (
        "Nằm ngửa, gối co, tay đỡ nhẹ sau đầu (không đan chặt).",
        "Cuộn vai lên khỏi sàn bằng cơ bụng — KHÔNG kéo cổ.",
        "Hạ chậm. Lặp lại.",
    ),
    "dead_bug": (
        "Nằm ngửa, hai tay vươn lên trần, hai gối co 90° (tư thế cái bàn).",
        "Ép lưng SÁT sàn; hạ tay và chân ĐỐI DIỆN xuống gần sàn.",
        "Đưa về, đổi bên. Lưng luôn sát sàn.",
    ),
    "double_leg_lift_hold": (
        "Nằm ngửa, ép lưng sát sàn, hai tay xuôi cạnh người.",
        "Nâng hai chân thẳng khỏi sàn vài chục cm.",
        "GIỮ. Lưng cong/đau thì nâng chân cao hơn hoặc hơi co gối.",
    ),
    "side_plank": (
        "Nằm nghiêng, chống một khuỷu tay ngay dưới vai.",
        "Nâng hông lên, thân thẳng một đường.",
        "Giữ, hông không võng. Đổi bên.",
    ),
    "plank_knee_rotation": (
        "Vào plank cẳng tay, GỐI THẲNG, chân hơi rộng.",
        "Xoay hông cho hông/gối lật chạm về sàn một bên.",
        "Đổi bên, có kiểm soát. KHÔNG quỳ/dồn lên gối.",
    ),
    "plank_shoulder_tap": (
        "Vào plank CAO (chống hai tay), gối thẳng, chân mở rộng cho vững.",
        "Nhấc một tay chạm lên vai đối diện.",
        "Đặt xuống, đổi tay. Giữ HÔNG không lắc.",
    ),
    "bird_dog": (
        "Quỳ chống hai tay (KÊ ĐỆM dưới gối), lưng phẳng như mặt bàn.",
        "Duỗi thẳng tay và chân ĐỐI DIỆN ra ngang thân.",
        "Giữ 2 giây, thu về, đổi bên. Không võng lưng. (Cộm gối → đổi Dead Bug.)",
    ),
    "bicycle_crunch": (
        "Nằm ngửa, tay đỡ sau đầu, hai chân nâng khỏi sàn.",
        "Đưa khuỷu tay chạm gối ĐỐI DIỆN, chân kia duỗi ra.",
        "Đổi bên liên tục như đạp xe, chậm và có kiểm soát.",
    ),
    "russian_twist": (
        "Ngồi, gối co, hơi ngả người ra sau (lưng thẳng).",
        "Xoay thân sang một bên (tay/vật chạm cạnh hông).",
        "Xoay sang bên kia. Xoay từ LƯỜN, không giật cổ.",
    ),
    "standing_trunk_twist": (
        "Đứng vững, chân rộng bằng vai, gối thẳng tự nhiên.",
        "Hai tay đưa ngang, xoay thân sang trái.",
        "Xoay sang phải. Xoay từ hông/lườn, hông giữ ổn định.",
    ),
    "wood_chop": (
        "Đứng, hai tay nắm nhau (hoặc cầm vật nhẹ) đưa lên chéo một bên.",
        "Vung chéo xuống phía hông ĐỐI DIỆN, xoay lườn theo.",
        "Đưa lên lại, lặp; đổi bên. Gối chỉ hơi mềm, không khuỵu sâu.",
    ),
    # --- balance · upper body · wrist · mobility ---
    "single_leg_balance": (
        "Đứng thẳng cạnh điểm tựa (ghế/tường).",
        "Nhấc một chân khỏi sàn, siết hông giữ thăng bằng.",
        "Giữ. Bám tựa nếu loạng choạng. Đổi chân.",
    ),
    "single_leg_eyes_closed": (
        "Đứng một chân cạnh tường để sẵn sàng bám.",
        "Nhắm mắt, giữ thăng bằng bằng cảm nhận thân.",
        "Giữ. Mở mắt/bám khi mất thăng bằng. Đổi chân.",
    ),
    "toe_stand_hold": (
        "Đứng thẳng, vịn nếu cần.",
        "Nhón cả hai gót lên cao.",
        "GIỮ ở trên. Hạ chậm.",
    ),
    "gentle_bounce": (
        "Đứng trên mũi chân, gối hơi mềm.",
        "Nhún nhẹ tại chỗ, tiếp đất MỀM.",
        "Giữ nhịp đều. KHÔNG nhảy cao.",
    ),
    "wall_pushup": (
        "Đứng cách tường một tầm tay, chống hai tay lên tường ngang vai.",
        "Cong khuỷu hạ người vào tường, thân giữ thẳng.",
        "Đẩy người ra. Muốn nặng hơn thì đứng xa tường hơn.",
    ),
    "wrist_curl": (
        "Ngồi, cẳng tay tựa lên đùi, bàn tay thò khỏi gối, cầm vật nhẹ (chai nước).",
        "Cuộn cổ tay lên–xuống chậm vài lần.",
        "Rồi xoay cổ tay trong–ngoài. Nhẹ nhàng. Đổi tay.",
    ),
    "scapular_yt": (
        "Nằm sấp, trán tựa nhẹ, hai tay duỗi trước thành chữ Y.",
        "Nâng hai tay khỏi sàn (giữ chữ Y), siết bả vai, rồi hạ.",
        "Dang tay thành chữ T, nâng lên rồi hạ. KHÔNG nhún vai lên tai.",
    ),
    "thoracic_rotation": (
        "Nằm nghiêng, hai gối co chồng nhau, hai tay duỗi thẳng trước mặt (chồng nhau).",
        "Mở tay trên lên và ra sau, xoay NGỰC như mở trang sách, mắt theo tay.",
        "Đưa tay về. Lặp rồi đổi bên. Nhẹ nhàng. (Ngồi xoay cũng được.)",
    ),
    "hamstring_stretch": (
        "Ngồi/đứng, một chân duỗi thẳng.",
        "Gập TỪ HÔNG tới khi căng nhẹ đùi sau, lưng thẳng.",
        "Giữ, thở đều, KHÔNG nảy. Đổi bên.",
    ),
    "quad_stretch": (
        "Đứng vịn tường một tay.",
        "Gập một gối, tay kia kéo gót về phía mông NHẸ NHÀNG.",
        "Giữ tới căng nhẹ đùi trước. Đổi bên.",
    ),
    "groin_stretch": (
        "Ngồi, hai lòng bàn chân chạm nhau, kéo gần người.",
        "Ấn nhẹ hai gối xuống tới khi căng nhẹ háng.",
        "Giữ, thở đều, không nảy.",
    ),
    # --- warm-up ---
    "knee_mobility": (
        "Ngồi hoặc đứng vịn.",
        "Gập–duỗi gối nhẹ nhàng trong biên độ thoải mái.",
        "Xoay cổ chân vài vòng mỗi bên.",
    ),
    "march_in_place": (
        "Đứng thẳng.",
        "Giậm chân tại chỗ nhịp nhàng, nhấc đùi vừa phải.",
        "Đánh tay nhẹ theo nhịp. KHÔNG bật nhảy.",
    ),
}


def how_to_for(key: str) -> list[str]:
    """Step-by-step instructions for an exercise (empty list if none)."""
    return list(HOW_TO.get(key, ()))


# Per-level, per-day-type session templates (3–4 exercises each). Progression is
# by harder variants + more volume, never by adding impact.
DAY_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "foundation": {
        # Quad-first: quad/hip work; gentle intro of upper body on the balance day.
        "legs": ["quad_set", "straight_leg_raise", "short_arc_quad", "side_leg_raise",
                 "lateral_lunge"],
        "core": ["plank", "double_leg_lift_hold", "standing_trunk_twist", "crunch"],
        "balance": ["single_leg_balance", "wall_pushup", "wrist_curl", "thoracic_rotation"],
    },
    "explosive": {
        # Quad-led + posterior chain (hip hinge); core adds anti-rotation; upper body grows.
        "legs": ["short_arc_quad", "lateral_lunge", "glute_bridge", "wall_sit_shallow",
                 "hip_hinge"],
        "core": ["plank_shoulder_tap", "bird_dog", "plank_knee_rotation",
                 "standing_trunk_twist", "side_plank"],
        "balance": ["single_leg_balance", "wall_pushup", "scapular_yt", "wrist_curl",
                    "gentle_bounce"],
    },
    "tt_specific": {
        # Functional quad/hip + posterior chain + low-impact footwork; rotation-power core;
        # advanced balance + shoulder/wrist/mobility.
        "legs": ["short_arc_quad", "single_leg_glute_bridge", "lateral_lunge",
                 "lateral_toe_steps", "hip_hinge"],
        "core": ["russian_twist", "wood_chop", "plank_knee_rotation", "plank_shoulder_tap",
                 "standing_trunk_twist"],
        "balance": ["single_leg_eyes_closed", "scapular_yt", "wrist_curl",
                    "thoracic_rotation", "gentle_bounce"],
    },
}


def day_type_for(day_index: int) -> str:
    """The day-type of session `day_index` (1-based) via the micro-cycle."""
    return DAY_CYCLE[(day_index - 1) % len(DAY_CYCLE)]


def exercises_for(day_type: str, level: str) -> list[Exercise]:
    """The exercises of a session, from the per-level day template."""
    keys = DAY_TEMPLATES.get(level, {}).get(day_type, [])
    return [EXERCISES[k] for k in keys if k in EXERCISES]


@dataclass
class PlannedSession:
    level: str
    day_index: int
    day_type: str
    focus_vi: str
    exercises: list[Exercise] = field(default_factory=list)


def planned_session(level: str, day_index: int) -> PlannedSession:
    """Build the (static) prescription for one session of a level."""
    day_type = day_type_for(day_index)
    return PlannedSession(
        level=level,
        day_index=day_index,
        day_type=day_type,
        focus_vi=DAY_FOCUS_VI[day_type],
        exercises=exercises_for(day_type, level),
    )


def estimate_minutes(exs: list[Exercise]) -> int:
    """Rough session duration estimate (for the header), minutes."""
    secs = 0
    for e in exs:
        sets = e.target.get("sets", 1)
        sides = 2 if e.per_side else 1
        if e.kind == "timed":
            work = e.target.get("sec", 30)
        else:
            work = e.target.get("reps", 15) * 2  # ~2s per rep
        secs += sets * sides * work + sets * 20  # +20s rest between sets
    return max(1, round(secs / 60))


def next_level(level: str) -> str | None:
    """The level after `level`, or None if it is the last one."""
    i = LEVELS.index(level)
    return LEVELS[i + 1] if i + 1 < len(LEVELS) else None


# --------------------------------------------------- maintenance / progression
# After the last level is finished the program does NOT dead-end: it repeats the
# top (sport-specific) level in "cycles" (Vòng) with gentle progressive overload.
# Overload plateaus after a few cycles — for a knee-OA client we add time-under-
# tension / reps, never load or impact, and we cap it so it stays sensible. The
# Head Coach (Tier-2) is meant to take over the "what next" eventually.
MAINTENANCE_LEVEL = LEVELS[-1]  # the endless top level (tt_specific)
OVERLOAD_MAX_CYCLES = 3  # overload stops growing after this many maintenance cycles


def cycle_of(day_index: int) -> int:
    """0-based cycle a (1-based) session index falls in. 1..21 -> 0, 22..42 -> 1…"""
    return (day_index - 1) // SESSIONS_PER_LEVEL


OVERLOAD_BUMP_CAP = OVERLOAD_MAX_CYCLES + 2  # autoregulation can push a bit past


def scaled_target(ex: Exercise, cycle: int, bias: int = 0) -> dict:
    """Apply progressive overload + autoregulation to an exercise's target.

    Base overload = min(cycle, OVERLOAD_MAX_CYCLES). `bias` is the autoregulation
    adjustment from recent pain/RPE feedback (easy → +, hard/pain → −). The
    effective bump is clamped to [0, OVERLOAD_BUMP_CAP]: +5s per step for timed
    holds, +2 reps per step for rep work. Sets never change; knee-safe by design.
    """
    base = min(max(cycle, 0), OVERLOAD_MAX_CYCLES)
    bump = max(0, min(base + bias, OVERLOAD_BUMP_CAP))
    if bump == 0:
        return dict(ex.target)
    t = dict(ex.target)
    if ex.kind == "timed" and "sec" in t:
        t["sec"] = t["sec"] + 5 * bump
    elif "reps" in t:
        t["reps"] = t["reps"] + 2 * bump
    return t


def alternatives_for(key: str, exclude: set[str]) -> list[Exercise]:
    """Knee-safe substitutes for an exercise: same day-type, not already in the
    session. Used by the "đổi bài nếu đau" swap."""
    ex = EXERCISES.get(key)
    if ex is None:
        return []
    out = [
        e for e in _EX
        if e.day_type == ex.day_type and e.key != key and e.key not in exclude
        and e.key not in WARMUP_KEYS
    ]
    return out[:3]
