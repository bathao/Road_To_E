"""The exercise catalogue (knee-safe, home equipment) + warm-up / cool-down lists.

Part of the static programme package (split 2026-10-16 from program.py;
see REFACTOR.md §4.2). Import names via ``app.features.training.program``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Exercise:
    key: str
    name_vi: str
    muscle: str  # muscle group
    tt_benefit: str  # why it helps table tennis (motivation, shown on the card)
    kind: str  # "reps" | "timed"
    # {"sets":3,"reps":20} or {"sets":3,"sec":45}; an optional "unit" (e.g.
    # "jumps") relabels a set-less rep target in the UI ("100 jumps").
    target: dict
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
    Exercise("quad_set", "Quad set (isometric squeeze)", "Quadriceps (isometric)",
             "The #1 foundation move for the knee: strong quads → less force on the knee joint.",
             "reps", {"sets": 3, "reps": 12}, "legs",
             gif=_gif("quad_set"),
             form_cue="Leg straight, SQUEEZE the thigh pressing the back of the knee down, HOLD ~5 seconds then release. No joint pain."),
    Exercise("short_arc_quad", "Short-arc quad (towel under knee)", "Quadriceps (VMO)",
             "Strengthens the quads in a PAIN-FREE range — directly protects the knee.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("short_arc_quad"),
             form_cue="Place a rolled towel under the back of the knee, straighten the lower leg then lower slowly; SMALL range."),
    Exercise("straight_leg_raise", "Straight leg raise (quads)", "Quadriceps",
             "Strong quads keep the knee stable when you strike.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("straight_leg_raise"),
             form_cue="Lie on your back, knee STRAIGHT, raise the leg ~30–40°, lower slowly. Stop if the knee hurts."),
    Exercise("side_leg_raise", "Side-lying leg raise (outer thigh/hip)", "Outer thigh, hips",
             "Strong hips for steady sideways steps without falling.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("side_leg_raise"),
             form_cue="Lie on your side, raise the straight leg sideways; don't roll backward."),
    Exercise("prone_leg_raise", "Prone leg raise (hamstrings)", "Hamstrings, glutes",
             "Balances the muscles around the knee, reducing joint load.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("prone_leg_raise"),
             form_cue="Lie face down, squeeze the glutes and raise the straight leg in a small range; don't arch the lower back."),
    Exercise("wall_sit_shallow", "Wall sit (shallow knee bend)", "Quadriceps (isometric)",
             "Thigh endurance to hold a low ready stance.",
             "timed", {"sets": 3, "sec": 30}, "legs",
             gif=_gif("wall_sit_shallow"),
             form_cue="Back against the wall, knees bent SHALLOW (not down to 90°). Pain means stop."),
    Exercise("glute_bridge", "Glute bridge", "Glutes, hamstrings",
             "Strong glutes stabilize the torso and take load off the knees.",
             "reps", {"sets": 3, "reps": 15}, "legs",
             gif=_gif("glute_bridge"),
             form_cue="Lie on your back, knees bent, lift the hips squeezing the glutes; don't over-arch the back."),
    Exercise("calf_raise", "Calf raise (on the toes)", "Calves, ankles",
             "Ankle/calf power for light push-off steps.",
             "reps", {"sets": 3, "reps": 20}, "legs",
             gif=_gif("calf_raise"),
             form_cue="Stand and rise up-down on the toes slowly; hold the wall if needed."),
    Exercise("mini_squat", "Mini squat (joint-friendly)", "Thighs, glutes",
             "Squat-pattern leg strength without deep knee loading.",
             "reps", {"sets": 3, "reps": 15}, "legs",
             gif=_gif("mini_squat"),
             form_cue="Bend the knees SHALLOW ~30°, knees not past the toes; hold a chair if needed."),
    Exercise("lateral_toe_steps", "Lateral steps on the toes", "Calves, hips (footwork)",
             "Mimics table-tennis side steps — done on the toes, so it's easy on the knees.",
             "timed", {"sets": 3, "sec": 30}, "legs",
             gif=_gif("lateral_toe_steps"),
             form_cue="Up on the toes, step gently side to side; do NOT bend the knees deep, no jumping."),
    Exercise("toe_stand_hold", "Toe stand (hold)", "Calves, ankles, balance",
             "Stable ankles + a gentle standing base, no knee load.",
             "timed", {"sets": 3, "sec": 30}, "balance",
             gif=_gif("toe_stand_hold"),
             form_cue="Lift both heels up and HOLD; hold the wall if you lose balance."),
    Exercise("single_leg_glute_bridge", "Single-leg glute bridge", "Glutes (one side)",
             "Single-leg strength, left/right balance.",
             "reps", {"sets": 3, "reps": 12}, "legs", per_side=True,
             gif=_gif("single_leg_glute_bridge"),
             form_cue="Glute bridge but with one leg extended; keep the hips level, no tilting."),
    Exercise("lateral_lunge", "Lateral lunge (shallow)", "Glutes, inner thigh, thighs",
             "Strong glutes + a wide sideways step to save balls. Strong glutes help unload the knee.",
             "reps", {"sets": 2, "reps": 8}, "legs", per_side=True,
             gif=_gif("lateral_lunge"),
             form_cue="Step wide to the side, shift your weight onto the standing leg, knee tracking over the toes; "
                      "do NOT go deep (stay shallow), hold a chair if needed. Stop if the knee hurts."),
    Exercise("inner_thigh_raise", "Inner-thigh leg raise", "Inner thigh",
             "The inner thighs keep your base stable on wide ball-saving steps.",
             "reps", {"sets": 3, "reps": 15}, "legs", per_side=True,
             gif=_gif("inner_thigh_raise"),
             form_cue="Lie on your side, top leg resting in front, raise the bottom leg up."),
    Exercise("hip_hinge", "Standing hip hinge", "Hamstrings, glutes, lower back",
             "Builds force from legs–hips up through the torso (posterior chain) for a powerful loop; knees stay straight so it's easy on the joint.",
             "reps", {"sets": 3, "reps": 12}, "legs",
             gif=_gif("hip_hinge"),
             form_cue="Feet shoulder-width, KNEES SLIGHTLY SOFT (no deep bend), push the HIPS back, back straight; "
                      "hinge forward until the hamstrings feel tight, then squeeze the glutes to stand up. Force in the hips/hamstrings, NOT the knees."),
    # --- core: rotational + anti-rotation + stability, no knee load ---
    Exercise("plank", "Plank", "Entire core",
             "The foundation of torso stability when striking.",
             "timed", {"sets": 3, "sec": 30}, "core",
             gif=_gif("plank"),
             form_cue="On the elbows, brace abs+glutes, don't let the back sag."),
    Exercise("crunch", "Crunch (short range)", "Upper abs",
             "Builds your ability to hold your center of gravity.",
             "reps", {"sets": 3, "reps": 20}, "core",
             gif=_gif("crunch"),
             form_cue="Curl the shoulders up, don't pull on the neck."),
    Exercise("dead_bug", "Dead bug", "Deep core (back/knee-safe)",
             "Core stability without loading the knee joint.",
             "reps", {"sets": 3, "reps": 16}, "core",
             gif=_gif("dead_bug"),
             form_cue="Lie on your back, lower the opposite arm & leg; press the lower back into the floor."),
    Exercise("double_leg_lift_hold", "Supine double-leg lift & hold", "Lower abs + quads (isometric)",
             "Braces the lower abs while the quads hold isometrically — knees straight, so no joint load.",
             "timed", {"sets": 3, "sec": 20}, "core",
             gif=_gif("double_leg_lift_hold"),
             form_cue="Raise both straight legs a few dozen centimeters off the floor and HOLD; PRESS the lower back into the floor. "
                      "If the back arches/hurts, raise the legs higher or bend the knees slightly."),
    Exercise("side_plank", "Side plank", "Obliques",
             "Keeps the body from tipping sideways when playing away from the table.",
             "timed", {"sets": 3, "sec": 25}, "core", per_side=True,
             gif=_gif("side_plank"),
             form_cue="Body in one straight line, don't let the hips sag."),
    Exercise("plank_knee_rotation", "Plank with hip rotation", "Obliques, rotational core, shoulders",
             "Core + shoulder rotation stability for loop spin. Done on the forearms, so the knees bear NO load.",
             "reps", {"sets": 2, "reps": 8}, "core", per_side=True,
             gif=_gif("plank_knee_rotation"),
             form_cue="Hold a solid forearm plank, KNEES STRAIGHT; rotate the hips so the hips/knees tip to each side, "
                      "slow and controlled. Weight on the forearms + toes, do NOT kneel or load the knees. "
                      "The shoulders carry significant load — stop if the shoulders or knees feel uncomfortable."),
    Exercise("plank_shoulder_tap", "Plank shoulder taps (anti-rotation)", "Anti-rotation core, shoulders",
             "Keeps the torso from rocking while the arms work — exactly the stability you need when swinging the racket.",
             "reps", {"sets": 3, "reps": 10}, "core", per_side=True,
             gif=_gif("plank_shoulder_tap"),
             form_cue="High plank (on the hands), KNEES STRAIGHT, feet wide for stability; tap each hand to the "
                      "opposite shoulder while the HIPS STAY STILL. Weight on the hands + toes, no knee loading."),
    Exercise("bird_dog", "Bird dog (opposite arm–leg)", "Deep core, glutes, back (posterior chain)",
             "Torso stability when reaching to save a ball; opposite arm–leg coordination.",
             "reps", {"sets": 3, "reps": 10}, "core", per_side=True,
             gif=_gif("bird_dog"),
             form_cue="On hands and knees (PAD the knees with a cushion/folded towel), extend the OPPOSITE arm and leg straight, "
                      "hold 2 seconds then switch sides; back flat, no sagging. If the knee is sore/uncomfortable, switch to Dead Bug."),
    Exercise("bicycle_crunch", "Bicycle crunch", "Abs + rotating obliques",
             "Continuous core-rotation coordination like in fast rallies.",
             "reps", {"sets": 3, "reps": 20}, "core",
             gif=_gif("bicycle_crunch"),
             form_cue="Touch elbow to opposite knee slowly; the knees don't need to bend deep."),
    Exercise("russian_twist", "Russian twist", "Rotational obliques",
             "This IS the rotation of the forehand/backhand loop.",
             "reps", {"sets": 3, "reps": 24}, "core",
             gif=_gif("russian_twist"),
             form_cue="Rotate from the obliques, don't jerk the neck; keep the lower back stable."),
    Exercise("standing_trunk_twist", "Standing trunk twist", "Obliques (standing)",
             "Trains the exact torso rotation of the loop; standing, so no knee load.",
             "reps", {"sets": 3, "reps": 24}, "core",
             gif=_gif("standing_trunk_twist"),
             form_cue="Stand firm (knees naturally straight), rotate the torso left–right from the hips/obliques."),
    Exercise("wood_chop", "Wood chop (diagonal twist)", "Diagonal obliques",
             "Transfers diagonal spin power like when looping/smashing.",
             "reps", {"sets": 3, "reps": 20}, "core", per_side=True,
             gif=_gif("wood_chop"),
             form_cue="Swing the arms diagonally from high to low, rotating the obliques; knees only slightly soft, do NOT bend deep."),
    # --- balance & recovery ---
    Exercise("single_leg_balance", "Single-leg stand", "Hips, ankles",
             "A stable base when you have to reach out to save a ball.",
             "timed", {"sets": 3, "sec": 30}, "balance", per_side=True,
             gif=_gif("single_leg_balance"),
             form_cue="Stand on one leg, brace the hips; grab a support if wobbly."),
    Exercise("hamstring_stretch", "Hamstring stretch", "Hamstrings",
             "Maintains stride range, prevents muscle strains.",
             "timed", {"sets": 2, "sec": 40}, "balance", per_side=True,
             gif=_gif("hamstring_stretch"),
             form_cue="Back straight, hinge from the hips; no bouncing."),
    Exercise("groin_stretch", "Groin stretch", "Groin",
             "Prevents injury during sideways movement.",
             "timed", {"sets": 2, "sec": 40}, "balance", per_side=True,
             gif=_gif("groin_stretch"),
             form_cue="Stretch to a gentle pull, no bouncing."),
    Exercise("gentle_bounce", "Gentle bounce on the toes", "Calves, rhythm (low-impact)",
             "Trains a gentle split-step rhythm without harming the knees.",
             "timed", {"sets": 3, "sec": 30}, "balance",
             gif=_gif("gentle_bounce"),
             form_cue="Bounce lightly on the toes, land soft; do NOT jump high."),
    Exercise("quad_stretch", "Quad stretch", "Quadriceps",
             "Stretches the thigh muscles around the knee, reducing joint stiffness.",
             "timed", {"sets": 2, "sec": 30}, "balance", per_side=True,
             gif=_gif("quad_stretch"),
             form_cue="Stand holding the wall, pull the heel toward the glutes GENTLY, don't force it."),
    Exercise("single_leg_eyes_closed", "Single-leg stand, eyes closed", "Hips, ankles (advanced)",
             "Better balance reflexes for fast movement.",
             "timed", {"sets": 3, "sec": 40}, "balance", per_side=True,
             gif=_gif("single_leg_eyes_closed"),
             form_cue="Like the single-leg stand but with eyes closed; stand next to a wall for support."),
    # --- upper body / wrist / mobility: TT-specific, all knee-safe (standing/lying) ---
    Exercise("wall_pushup", "Wall push-up", "Chest, shoulders, triceps",
             "Arm–shoulder strength & endurance for a steady stroke; standing, so NO knee load.",
             "reps", {"sets": 3, "reps": 12}, "balance",
             gif=_gif("wall_pushup"),
             form_cue="Stand an arm's length from the wall, hands at shoulder height, lower yourself to the wall then push back out; "
                      "body straight, knees straight. To make it harder, stand farther from the wall."),
    Exercise("wrist_curl", "Wrist curls & rotations (forearm)", "Forearms, wrists",
             "A strong & flexible wrist = better friction/SPIN on loops and pushes.",
             "reps", {"sets": 3, "reps": 15}, "balance", per_side=True,
             gif=_gif("wrist_curl"),
             form_cue="Sit, forearm resting on the thigh, holding a light object (water bottle): curl the wrist up–down then "
                      "rotate in–out slowly. Gentle, no wrist pain."),
    Exercise("scapular_yt", "Prone Y–T raises", "Rear delts, scapular muscles, upper back",
             "Strong shoulders & good posture → shoulder endurance, fewer injuries from heavy play.",
             "reps", {"sets": 3, "reps": 12}, "balance",
             gif=_gif("scapular_yt"),
             form_cue="Lie face down, forehead resting lightly, raise both arms off the floor in a Y then a T shape, "
                      "squeezing the shoulder blades; do NOT shrug the shoulders up to the ears. No knee load."),
    Exercise("thoracic_rotation", "Thoracic rotation (open book)", "Chest–oblique mobility",
             "More torso-rotation range → loops/smashes reach farther & flow smoother.",
             "reps", {"sets": 2, "reps": 10}, "balance", per_side=True,
             gif=_gif("thoracic_rotation"),
             form_cue="Lie on your side, knees bent and stacked (NO load on them), arms extended in front; open the top "
                      "arm rotating the chest back like opening a book page, eyes following the hand. Gentle; seated rotation works too."),
    # --- daily staples: done EVERY session, with their own progressive ramp ---
    # (see DAILY_KEYS / daily_target). Knee-safe; one targets the wrist/forearm
    # for spin, the other hip/core control for footwork.
    Exercise("gyro_ball", "Powerball (gyro ball) wrist work", "Forearms, wrists",
             "A strong, enduring wrist & forearm → MORE SPIN on loops/pushes, and the wrist "
             "doesn't fade in long counter-hitting rallies. Do it daily, gradually adding time.",
             "timed", {"sets": 2, "sec": 20}, "balance", per_side=True,
             gif=_gif("gyro_ball"),
             form_cue="Start the rotor spinning, then GRIP and circle the wrist steadily so the ball speeds up; "
                      "forearm braced, SHOULDER RELAXED. One round per hand. If the wrist/elbow hurts, slow down or cut the time."),
    Exercise("thigh_lift_bottle", "Supine thigh lift over a water bottle",
             "Hips, thighs (flexion/adduction–abduction), lower core",
             "Strong, mobile hips and a well-controlled core → fast sideways steps and a steady "
             "center of gravity. Lying down, so NO knee-joint load. Do it daily, gradually adding reps.",
             "reps", {"sets": 2, "reps": 8}, "core", per_side=True,
             gif=_gif("thigh_lift_bottle"),
             form_cue="Place a water bottle on the floor about midway between your feet. Lie on your back, PRESS the lower back "
                      "GENTLY into the floor; lift one thigh and carry the foot & thigh OVER the bottle to the other side and back, then switch. "
                      "Slow, controlled with the core; the knee doesn't need a deep bend. If the back/knee hurts, reduce the range."),
    # --- dumbbell pool (1kg pair): rotated 2-per-day as daily work, see
    #     DUMBBELL_KEYS / daily_dumbbells. Light load → high reps for endurance;
    #     all knee-safe (seated/standing, hip-hinge not knee load). ---
    Exercise("db_trunk_twist", "Seated dumbbell trunk twist", "Rotational obliques (loaded)",
             "Adds load to the exact rotation of the loop/smash → stronger, more enduring spin power.",
             "reps", {"sets": 2, "reps": 20}, "core",
             gif=_gif("db_trunk_twist"),
             form_cue="Sit (or stand) with a straight back, both hands hugging the dumbbell at the chest; rotate the torso "
                      "left–right from the OBLIQUES, hips stable, no neck jerking. Light weight — slow control."),
    Exercise("db_shoulder_press", "Seated overhead dumbbell press", "Shoulders, triceps",
             "Strong, enduring shoulders keep the arm steady the whole match, less fatigue in long sessions.",
             "reps", {"sets": 2, "reps": 15}, "balance",
             gif=_gif("db_shoulder_press"),
             form_cue="Sit up straight, dumbbells at shoulder height; press straight up overhead then lower slowly. "
                      "Brace the abs to stay stable, do NOT arch the back."),
    Exercise("db_wood_chop", "Dumbbell wood chop", "Diagonal obliques (loaded)",
             "Transfers diagonal spin power from the hips up to the arms like a hard loop/smash.",
             "reps", {"sets": 2, "reps": 12}, "core", per_side=True,
             gif=_gif("db_wood_chop"),
             form_cue="Hold one dumbbell with both hands, swing diagonally from high on one side down to the opposite hip, "
                      "rotating the obliques; knees only slightly soft, do NOT bend deep. Switch sides."),
    Exercise("db_lateral_raise", "Dumbbell lateral raise", "Shoulders (middle delts)",
             "Shoulder-joint stability → a solid racket path, fewer shoulder injuries from heavy swinging.",
             "reps", {"sets": 2, "reps": 15}, "balance",
             gif=_gif("db_lateral_raise"),
             form_cue="Standing/seated, dumbbells at the hips; raise the arms straight out to the sides up to shoulder height "
                      "(elbows slightly bent) then lower slowly. Do NOT shrug, no momentum."),
    Exercise("db_shadow_swing", "Weighted shadow stroke swings", "Shoulders, arms, obliques (TT-specific)",
             "Shadows the forehand/backhand stroke path against light resistance → the muscles learn the racket path, faster & stronger shots.",
             "reps", {"sets": 2, "reps": 12}, "balance", per_side=True,
             gif=_gif("db_shadow_swing"),
             form_cue="Hold one dumbbell and shadow the loop/smash SLOWLY & with proper technique (hip→torso→arm rotation), "
                      "no sloppy swinging. Do both forehand & backhand. Stop if the shoulder/elbow hurts."),
    Exercise("db_bent_row", "Bent-over dumbbell row", "Upper back, lats, back of arms",
             "A strong upper back → upright posture, quick racket recovery after each stroke; balances the pull–push muscles.",
             "reps", {"sets": 2, "reps": 15}, "balance",
             gif=_gif("db_bent_row"),
             form_cue="Hinge at the HIPS, knees slightly soft, back straight; row both dumbbells toward the hips squeezing "
                      "the shoulder blades, lower slowly. Force in the back/hips, do NOT load the knees; if the lower back hurts, reduce the hinge."),
    # Seated "weighted abs" trio (lean-back seated, 1kg dumbbells): compound abs +
    # thigh (hip flexion) + arm/shoulder, all knee-safe (seated, no knee load / flexion / impact).
    Exercise("db_seated_leg_press", "Seated thigh lift + dumbbell press-out (alternating)",
             "Abs/core, quads (hip flexion), shoulders/arms",
             "Braces the core while flexing the hip to lift the thigh and pressing the arms out — a strong "
             "core + mobile hips keep the center of gravity steady on the move, arms/shoulders build endurance.",
             "reps", {"sets": 2, "reps": 16}, "core",
             gif=_gif("db_seated_leg_press"),
             form_cue="Sit with knees bent, feet on the floor, lean back slightly keeping the back straight, both hands "
                      "holding one dumbbell at the chest. Lift one thigh WHILE pressing the dumbbell straight out in front; "
                      "return, switch legs, alternate. Brace the abs for balance; lean moderately, no lower-back/knee pain."),
    Exercise("db_seated_overhead_tuck", "Seated overhead press + rhythmic knee tuck",
             "Abs/core, quads (hip flexion), shoulders (overhead press)",
             "The core holds the torso steady while the shoulders press the weights and the hips tuck the knee — "
             "arm–torso–leg coordination like executing a stroke, shoulder endurance for heavy play.",
             "reps", {"sets": 2, "reps": 16}, "core",
             gif=_gif("db_seated_overhead_tuck"),
             form_cue="Sit leaning slightly back (back straight), both hands holding two dumbbells at shoulder height. Press "
                      "both dumbbells straight up overhead WHILE tucking one knee/thigh up in rhythm; lower the weights and the "
                      "leg, then switch sides. Brace the abs, do NOT arch the back; tuck the knee comfortably, no pain."),
    Exercise("db_seated_leg_spread", "Seated overhead dumbbell hold + leg spreads",
             "Abs/core, inner/outer thighs (abduction–adduction), shoulders (overhead hold)",
             "Strong inner/outer thighs for wide sideways ball-saving steps, the core keeps balance while the legs "
             "spread, the shoulders build endurance holding the weight overhead.",
             "reps", {"sets": 2, "reps": 20}, "core",
             gif=_gif("db_seated_leg_spread"),
             form_cue="Sit leaning back, both hands holding the dumbbell EXTENDED STRAIGHT overhead, held firm. Spread both "
                      "legs wide apart then bring them together in rhythm; the legs SLIDE lightly on the floor, knees comfortably "
                      "extended. Brace the abs to hold the torso; shoulders keep the weight steady, don't drop it behind the head."),
    Exercise("db_seated_pass_under", "Seated thigh lift, pass the dumbbell under (alternating)",
             "Abs/core, quads (hip flexion), arms/shoulders",
             "Lifting the thigh braces the lower core + flexes the hip while the hands pass the weight under the thigh, "
             "training arm–torso–leg coordination; a strong core & hips keep the center of gravity steady when twisting to save balls.",
             "reps", {"sets": 2, "reps": 16}, "core",
             gif=_gif("db_seated_pass_under"),
             form_cue="Sit leaning slightly back (back straight), both hands holding one dumbbell. Lift one thigh/knee up, "
                      "pass the dumbbell UNDERNEATH the lifted thigh and pull it back; lower the leg, switch sides, alternate. "
                      "Brace the abs for balance; tuck the knee comfortably, no hard pressure, no pain."),
    # --- warm-up (gentle knee mobility before the session; not counted) ---
    Exercise("knee_mobility", "Knee warm-up (gentle flexion–extension)", "Knee joint (warm-up)",
             "Lubricates the knee joint before training, reduces stiffness.",
             "timed", {"sets": 1, "sec": 60}, "warmup",
             gif=_gif("knee_mobility"),
             form_cue="Seated/standing, flex–extend the knees in a comfortable range + circle the ankles. Gentle."),
    Exercise("march_in_place", "Light march in place", "Full body (warm-up)",
             "Boosts circulation and warms the muscles before training.",
             "timed", {"sets": 1, "sec": 40}, "warmup",
             gif=_gif("march_in_place"),
             form_cue="March lightly in place, don't lift the knees high, no jumping."),
    # --- jump rope (2026-09-05): a DAILY staple like the two above, added on the
    # real coach's "nhún nhảy liên tục" advice (footwork "ì ạch"). The user's
    # rule: 100+ jumps in the day = the item is done — a FIXED target (see
    # NO_RAMP_KEYS), no count entry. It is the program's ONE impact move, hence
    # the cue and the swap exclusion (NO_SWAP_KEYS).
    Exercise("jump_rope", "Jump rope (100+ jumps in the day)", "Calves, ankles, footwork rhythm",
             "Continuous light bouncing → a livelier split-step and faster feet between shots "
             "(the coach's 04/09 note: the footwork is sluggish). Any time of day, in blocks; "
             "tick it once you pass 100.",
             "reps", {"reps": 100, "unit": "jumps"}, "balance",
             gif=_gif("jump_rope"),
             form_cue="LOW bounce, land soft on the toes, knees slightly soft — never lock or drop deep. "
                      "Soft floor or cushioned shoes. Any knee pain → stop and Skip the item for the day."),
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
