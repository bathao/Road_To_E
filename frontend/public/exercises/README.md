# Exercise media (Training Center)

Drop one image/GIF per exercise here, named `<key>.gif` (or `.png`/`.jpg` — but
the code requests `.gif`, so prefer that). They are served at `/exercises/<key>.gif`
and shown on each exercise card. Until a file exists, the card shows a 🏋️
placeholder — nothing breaks.

Keep them small (the repo is local-only, no CDN). A short looping GIF or a single
clear demo frame is enough.

## ⚠️ Knee-safe program

The program is designed for grade-1 knee osteoarthritis: NO deep squats, lunges,
or jumping. Exercises are low-load quad/glute/hip/calf work + rotational core +
balance. Keep any demo media consistent with that (shallow angles, no impact).

## Filenames expected (from `backend/app/features/training/program.py`)

Legs (ƯU TIÊN cơ đùi; mông / hông / bắp chân — nhẹ khớp):
- `quad_set.gif`             (gồng cơ đùi — đẳng trường, tập hằng ngày)
- `short_arc_quad.gif`       (duỗi gối biên độ ngắn, kê khăn — VMO)
- `straight_leg_raise.gif`   (nâng chân thẳng — đùi trước)
- `side_leg_raise.gif`       (nâng chân ngang — đùi/hông ngoài)
- `prone_leg_raise.gif`      (nằm sấp nâng chân — đùi sau)
- `wall_sit_shallow.gif`     (wall sit gối nông)
- `glute_bridge.gif`         (cầu mông)
- `calf_raise.gif`           (nhón gót)
- `lateral_toe_steps.gif`    (di chuyển ngang nhón chân)
- `mini_squat.gif`           (squat nông)
- `single_leg_glute_bridge.gif`
- `inner_thigh_raise.gif`    (nâng chân trong — đùi trong)

Core (lõi + xoay lườn):
- `plank.gif`
- `crunch.gif`
- `dead_bug.gif`
- `double_leg_lift_hold.gif` (nằm ngửa nâng hai chân & giữ — đùi + bụng)
- `side_plank.gif`
- `bicycle_crunch.gif`
- `russian_twist.gif`
- `standing_trunk_twist.gif` (đứng xoay lườn)
- `wood_chop.gif`            (xoay chéo lườn — đốn củi)

Balance & recovery:
- `single_leg_balance.gif`   (đứng một chân)
- `toe_stand_hold.gif`       (đứng nhón chân giữ)
- `single_leg_eyes_closed.gif`
- `gentle_bounce.gif`        (nhún nhẹ trên mũi chân)
- `groin_stretch.gif`
- `hamstring_stretch.gif`
- `quad_stretch.gif`

If you add a new exercise to `program.py`, add its `<key>.gif` here too.
