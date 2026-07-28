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
    "Prioritize the THIGH MUSCLES to take load off the knee joint (doctor's advice). "
    "No deep squats / lunges / hard jumping. The light quad work (quad sets, leg raises, "
    "short-arc) can be done daily. Stop immediately if the knee hurts."
)

# Day-types a session focuses on + the focus label shown in the header.
DAY_TYPES = ("legs", "core", "balance")
DAY_FOCUS_VI = {
    "legs": "Quads (priority) — strong thighs take load off the knee",
    "core": "Core: rotation & anti-rotation",
    "balance": "Balance · shoulders · wrists (TT support work, knee-gentle)",
}
# A 6-session micro-cycle that PRIORITISES quads: legs 3/6, core 2/6, balance 1/6.
# Quad-strengthening is the evidence-based priority for knee OA, so leg days come
# up every other session.
DAY_CYCLE = ("legs", "core", "legs", "balance", "legs", "core")

# Levels, in unlock order.
LEVELS = ("foundation", "explosive", "tt_specific")
LEVEL_VI = {
    "foundation": "Foundation",
    "explosive": "Endurance & Stability",
    "tt_specific": "TT-Specific (knee-friendly)",
}
LEVEL_GOAL_VI = {
    "foundation": "Activate quads/glutes/hips WITHOUT deep knee loading; get used to holding a stable base.",
    "explosive": "Build endurance in the muscles around the knee + core stability, still easy on the joint.",
    "tt_specific": "Simulate table-tennis movement at moderate intensity, low-impact, knee-protective.",
}
# Number of sessions ("Day" tiles) per level.
SESSIONS_PER_LEVEL = 21


@dataclass(frozen=True)
class Exercise:
    key: str
    name_vi: str
    muscle: str  # muscle group
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


# Exercises appended to EVERY session (the player asked to train these daily):
# the wrist powerball and the supine hip/core "thigh-over-bottle". Unlike the
# warm-up these ARE tracked and counted, and they carry their own progressive
# ramp (daily_target) instead of the level/day-type rotation.
DAILY_KEYS = ("gyro_ball", "thigh_lift_bottle")

# 1kg-dumbbell pool. The player trains with weights daily, but doing all of these
# every day would overload the shoulders and bloat the session, so we ROTATE: a
# different DUMBBELL_PER_DAY of them each day (~a 5-day cycle through the 10). The
# order interleaves shoulder/back work with core/rotation and the seated weighted-
# abs compounds so each day is balanced. Intensity still ramps via daily_target
# (reps), so "usage changes day to day AND load progresses week to week".
DUMBBELL_KEYS = (
    "db_trunk_twist",         # core / rotation
    "db_shoulder_press",      # shoulder
    "db_seated_leg_press",    # seated weighted abs (core + thigh + arm)
    "db_lateral_raise",       # shoulder
    "db_wood_chop",           # core / diagonal rotation
    "db_seated_overhead_tuck",  # seated weighted abs (core + thigh + shoulder)
    "db_shadow_swing",        # TT-specific shoulder/arm
    "db_seated_leg_spread",   # seated weighted abs (core + thigh + shoulder)
    "db_bent_row",            # upper back / posture
    "db_seated_pass_under",   # seated weighted abs (core + thigh + arm)
)
DUMBBELL_PER_DAY = 2


def daily_exercises() -> list[Exercise]:
    return [EXERCISES[k] for k in DAILY_KEYS if k in EXERCISES]


def daily_dumbbells(global_day: int) -> list[Exercise]:
    """The DUMBBELL_PER_DAY weighted exercises for this training day.

    Deterministic in `global_day` (so it's stable/idempotent per session): walks
    the pool DUMBBELL_PER_DAY at a time, wrapping around — different bias of the
    body each day, full pool covered every few days."""
    n = len(DUMBBELL_KEYS)
    if n == 0:
        return []
    take = min(DUMBBELL_PER_DAY, n)
    start = ((max(global_day, 1) - 1) * take) % n
    keys = [DUMBBELL_KEYS[(start + i) % n] for i in range(take)]
    return [EXERCISES[k] for k in keys if k in EXERCISES]


def daily_for(global_day: int) -> list[Exercise]:
    """All exercises that should be appended to a session at this training age:
    the fixed daily staples + today's rotating dumbbell picks."""
    return daily_exercises() + daily_dumbbells(global_day)


# Step-by-step "how to do it" for each exercise, shown in the expandable
# "Detailed instructions" on the card. Kept here (not on the Exercise
# rows) so the dataclass calls stay readable and all instructions live together.
HOW_TO: dict[str, tuple[str, ...]] = {
    # --- legs ---
    "quad_set": (
        "Sit or lie down, working leg extended straight on the floor.",
        "Squeeze the quads, pressing the back of the knee down into the floor.",
        "Hold ~5 seconds then relax. Repeat.",
    ),
    "short_arc_quad": (
        "Lie/sit with a rolled towel (or small pillow) under the back of the knee.",
        "Keep the thigh on the towel and straighten the lower leg up.",
        "Hold 2 seconds then lower slowly. SMALL range, no pain.",
    ),
    "straight_leg_raise": (
        "Lie on your back, one knee bent (foot on the floor), working leg straight.",
        "Squeeze the thigh and raise the straight leg ~30–40 cm.",
        "Hold 1–2 seconds, lower slowly. Knee ALWAYS straight.",
    ),
    "side_leg_raise": (
        "Lie on your side, both legs straight and stacked.",
        "Raise the top leg straight up (sideways), without bending the knee.",
        "Lower slowly. Don't roll backward. Switch sides.",
    ),
    "prone_leg_raise": (
        "Lie face down, both legs extended.",
        "Squeeze the glutes and raise one straight leg off the floor in a small range.",
        "Hold 1–2 seconds, lower. Don't arch the lower back. Switch sides.",
    ),
    "wall_sit_shallow": (
        "Lean your back against the wall, feet stepped out in front.",
        "Slide down until the knees bend SHALLOW (not to 90°).",
        "Hold, breathe steadily. If the knee hurts, stand up higher.",
    ),
    "glute_bridge": (
        "Lie on your back, knees bent, feet on the floor hip-width apart.",
        "Squeeze the glutes and lift the hips into a straight shoulder–hip–knee line.",
        "Hold 1–2 seconds, lower slowly. Don't arch the back.",
    ),
    "calf_raise": (
        "Stand tall, hold a chair/wall if needed.",
        "Rise up on both toes as high as you can.",
        "Lower the heels slowly. Repeat.",
    ),
    "mini_squat": (
        "Stand feet shoulder-width apart, hold a chair if needed.",
        "Push the hips back, bending the knees SHALLOW ~30°.",
        "Stand up squeezing the glutes. Knees don't pass the toes.",
    ),
    "lateral_toe_steps": (
        "Rise lightly onto the toes, knees slightly soft.",
        "Step sideways to the right a few steps, then to the left.",
        "Gently — do NOT bend the knees deep, no jumping.",
    ),
    "single_leg_glute_bridge": (
        "Lie on your back as for a glute bridge, extend one leg straight up.",
        "Squeeze the glutes and lift the hips with the remaining support leg.",
        "Keep the hips LEVEL (no tilting), lower slowly. Switch sides.",
    ),
    "lateral_lunge": (
        "Stand with a wide stance, hold a chair if needed.",
        "Shift your weight onto one leg, push the hips back, knee tracking over the toes.",
        "Stay SHALLOW then push back to center. Don't go deep. Switch sides.",
    ),
    "inner_thigh_raise": (
        "Lie on your side, top leg bent and resting in front of you.",
        "Keep the bottom leg straight and raise it off the floor.",
        "Lower slowly. Switch sides.",
    ),
    "hip_hinge": (
        "Stand feet shoulder-width apart, knees SLIGHTLY SOFT (no deep bend).",
        "Push the HIPS back and hinge forward, back straight, until the hamstrings feel tight.",
        "Squeeze the glutes to stand up. Force in the hips/hamstrings, NOT the knees.",
    ),
    # --- core ---
    "plank": (
        "Place both elbows on the floor (under the shoulders), up on the toes.",
        "Brace abs + glutes, body in ONE straight line.",
        "Hold, breathe steadily. Back doesn't sag, hips don't pike up.",
    ),
    "crunch": (
        "Lie on your back, knees bent, hands lightly supporting the head (not clasped tight).",
        "Curl the shoulders off the floor using the abs — do NOT pull on the neck.",
        "Lower slowly. Repeat.",
    ),
    "dead_bug": (
        "Lie on your back, arms reaching to the ceiling, knees bent 90° (tabletop position).",
        "Press the back FLAT into the floor; lower the OPPOSITE arm and leg toward the floor.",
        "Return, switch sides. Back always flat on the floor.",
    ),
    "double_leg_lift_hold": (
        "Lie on your back, press the lower back into the floor, arms by your sides.",
        "Raise both straight legs a few dozen centimeters off the floor.",
        "HOLD. If the back arches/hurts, raise the legs higher or bend the knees slightly.",
    ),
    "side_plank": (
        "Lie on your side, prop up on one elbow directly under the shoulder.",
        "Lift the hips, body in one straight line.",
        "Hold, hips don't sag. Switch sides.",
    ),
    "plank_knee_rotation": (
        "Get into a forearm plank, KNEES STRAIGHT, feet slightly wide.",
        "Rotate the hips so the hips/knees tip toward the floor on one side.",
        "Switch sides, with control. Do NOT kneel or load the knees.",
    ),
    "plank_shoulder_tap": (
        "Get into a HIGH plank (on the hands), knees straight, feet wide for stability.",
        "Lift one hand and tap the opposite shoulder.",
        "Place it down, switch hands. Keep the HIPS from rocking.",
    ),
    "bird_dog": (
        "On hands and knees (PAD under the knees), back flat like a tabletop.",
        "Extend the OPPOSITE arm and leg straight out in line with the torso.",
        "Hold 2 seconds, return, switch sides. No sagging back. (Knee discomfort → switch to Dead Bug.)",
    ),
    "bicycle_crunch": (
        "Lie on your back, hands behind the head, both legs lifted off the floor.",
        "Bring one elbow to the OPPOSITE knee while extending the other leg.",
        "Keep alternating like pedaling a bicycle, slow and controlled.",
    ),
    "russian_twist": (
        "Sit, knees bent, leaning slightly back (back straight).",
        "Rotate the torso to one side (hands/object touching beside the hip).",
        "Rotate to the other side. Rotate from the OBLIQUES, don't jerk the neck.",
    ),
    "standing_trunk_twist": (
        "Stand firm, feet shoulder-width apart, knees naturally straight.",
        "Arms out level, rotate the torso to the left.",
        "Rotate to the right. Rotate from the hips/obliques, hips staying stable.",
    ),
    "wood_chop": (
        "Stand, hands clasped together (or holding a light object) raised diagonally to one side.",
        "Swing diagonally down toward the OPPOSITE hip, rotating the obliques.",
        "Bring it back up, repeat; switch sides. Knees only slightly soft, no deep bend.",
    ),
    # --- balance · upper body · wrist · mobility ---
    "single_leg_balance": (
        "Stand tall next to a support (chair/wall).",
        "Lift one foot off the floor, brace the hips to balance.",
        "Hold. Grab the support if wobbly. Switch legs.",
    ),
    "single_leg_eyes_closed": (
        "Stand on one leg next to a wall, ready to grab it.",
        "Close your eyes and balance using body awareness.",
        "Hold. Open your eyes / grab support if you lose balance. Switch legs.",
    ),
    "toe_stand_hold": (
        "Stand tall, hold on if needed.",
        "Rise up high on both toes.",
        "HOLD at the top. Lower slowly.",
    ),
    "gentle_bounce": (
        "Stand on the toes, knees slightly soft.",
        "Bounce lightly in place, landing SOFT.",
        "Keep an even rhythm. Do NOT jump high.",
    ),
    "wall_pushup": (
        "Stand an arm's length from the wall, hands on the wall at shoulder height.",
        "Bend the elbows lowering yourself to the wall, body kept straight.",
        "Push back out. To make it harder, stand farther from the wall.",
    ),
    "wrist_curl": (
        "Sit, forearm resting on the thigh, hand hanging past the knee, holding a light object (water bottle).",
        "Curl the wrist up–down slowly a few times.",
        "Then rotate the wrist in–out. Gently. Switch hands.",
    ),
    "scapular_yt": (
        "Lie face down, forehead resting lightly, arms extended forward in a Y shape.",
        "Raise both arms off the floor (keeping the Y), squeeze the shoulder blades, then lower.",
        "Spread the arms into a T, raise and lower. Do NOT shrug the shoulders up to the ears.",
    ),
    "thoracic_rotation": (
        "Lie on your side, knees bent and stacked, arms extended straight in front (stacked).",
        "Open the top arm up and back, rotating the CHEST like opening a book page, eyes following the hand.",
        "Bring the arm back. Repeat, then switch sides. Gentle. (Seated rotation works too.)",
    ),
    "hamstring_stretch": (
        "Sit/stand with one leg extended straight.",
        "Hinge FROM THE HIPS until you feel a gentle stretch in the hamstrings, back straight.",
        "Hold, breathe steadily, do NOT bounce. Switch sides.",
    ),
    "quad_stretch": (
        "Stand holding the wall with one hand.",
        "Bend one knee and GENTLY pull the heel toward the glutes with the other hand.",
        "Hold at a gentle stretch in the quads. Switch sides.",
    ),
    "groin_stretch": (
        "Sit, soles of the feet together, pulled close to the body.",
        "Gently press the knees down until you feel a light stretch in the groin.",
        "Hold, breathe steadily, no bouncing.",
    ),
    # --- daily staples ---
    "gyro_ball": (
        "Pull the starter cord (or wind the rotor) so the rotor inside the ball starts spinning.",
        "Once it spins, GRIP firmly and circle the wrist evenly so the ball speeds up & keeps going.",
        "Keep it going for the full time, then switch hands. Shoulder relaxed, only the forearm works.",
    ),
    "thigh_lift_bottle": (
        "Place a water bottle on the floor, about midway between your feet.",
        "Lie on your back, arms by your sides, GENTLY PRESS the lower back into the floor.",
        "Lift one leg/thigh, carry the foot & thigh OVER the bottle to the other side, then back to the start.",
        "Switch legs. Control with the core, slowly; don't use momentum from the back.",
    ),
    # --- dumbbell pool (1kg) ---
    "db_trunk_twist": (
        "Sit with a straight back on a chair/the floor (or stand feet shoulder-width), hands hugging the dumbbell at the chest.",
        "Rotate the torso to one side from the OBLIQUES, keeping the hips stable.",
        "Rotate to the other side. Slow, controlled; don't jerk the neck/back.",
    ),
    "db_shoulder_press": (
        "Sit with a straight back, dumbbells raised to shoulder height, palms facing forward.",
        "Press both dumbbells straight up overhead, bracing the abs.",
        "Lower slowly back to shoulder height. Don't arch the back.",
    ),
    "db_wood_chop": (
        "Stand with a wide stance, both hands holding one dumbbell raised diagonally over one shoulder.",
        "Swing the dumbbell diagonally down toward the OPPOSITE hip, rotating the obliques.",
        "Bring it back up, repeat; switch sides. Knees only slightly soft, no deep bend.",
    ),
    "db_lateral_raise": (
        "Stand/sit tall, dumbbells at the hips, elbows slightly bent.",
        "Raise the arms straight out to the sides up to shoulder height.",
        "Lower slowly. No shrugging, no momentum from the torso.",
    ),
    "db_shadow_swing": (
        "Hold one dumbbell in your playing hand, get into the ready position as if playing.",
        "Shadow the loop/smash SLOWLY, with proper technique: rotate hips → torso → arm.",
        "Repeat, then switch to shadowing the backhand. Keep form, no sloppy swinging.",
    ),
    "db_bent_row": (
        "Hinge at the HIPS (push the hips back), knees slightly soft, back straight, dumbbells hanging straight down.",
        "Row both dumbbells toward the hips, squeezing the shoulder blades together.",
        "Lower slowly. Force in the back/hips, don't load the knees.",
    ),
    # --- seated weighted-abs trio + pass-under (lean-back seated, 1kg dumbbells) ---
    "db_seated_leg_press": (
        "Sit on the floor, knees bent with feet on the ground, leaning slightly back (back straight), both hands holding one dumbbell at the chest.",
        "Brace the abs for balance; lift one thigh/leg WHILE pressing the dumbbell straight out in front.",
        "Bring the dumbbell back to the chest and lower the leg, switch to the other leg.",
        "Alternate legs, slow and controlled; knee extended comfortably, no pain.",
    ),
    "db_seated_overhead_tuck": (
        "Sit leaning slightly back (back straight), both hands holding two dumbbells raised to shoulder height.",
        "Press both dumbbells straight up overhead WHILE tucking one knee/thigh up in rhythm.",
        "Lower the dumbbells to shoulder height and lower the leg, then switch legs.",
        "Brace the abs to stay stable, do NOT arch the back; tuck the knee comfortably.",
    ),
    "db_seated_leg_spread": (
        "Sit leaning back (back straight), both hands holding one dumbbell EXTENDED STRAIGHT overhead, held firm.",
        "Spread both legs wide apart (legs sliding lightly on the floor).",
        "Bring the legs back together in rhythm. Repeat.",
        "Brace the abs to hold the torso; shoulders keep the weight steady, knees extended comfortably.",
    ),
    "db_seated_pass_under": (
        "Sit leaning slightly back (back straight), both hands holding one dumbbell.",
        "Lift one thigh/knee up, pass the dumbbell UNDERNEATH the lifted thigh, then pull it back.",
        "Lower the leg, switch to the other leg.",
        "Alternate, bracing the abs for balance; tuck the knee comfortably, no hard pressure.",
    ),
    # --- warm-up ---
    "knee_mobility": (
        "Sit, or stand holding a support.",
        "Gently flex–extend the knees in a comfortable range.",
        "Circle the ankles a few times each way.",
    ),
    "march_in_place": (
        "Stand tall.",
        "March in place rhythmically, lifting the thighs moderately.",
        "Swing the arms lightly with the rhythm. Do NOT jump.",
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
# top (sport-specific) level in "cycles" with gentle progressive overload.
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


# --------------------------------------------------- daily-staple progression
# The daily exercises are done from day 1 and must ramp on the FINITE levels too
# (the level/cycle overload above only kicks in on the endless maintenance level).
# We drive their intensity off a monotonic "training-age" day number that never
# resets between levels, bumping ~weekly and capping so it stays knee/tendon-safe.
DAILY_STEP_DAYS = 7   # advance one intensity step roughly every week of daily work
DAILY_STEP_CAP = 5    # stop ramping after this many steps (sensible ceiling)
DAILY_BUMP_SEC = 8    # +8s per step for timed holds (20s → 60s at the cap)
DAILY_BUMP_REPS = 2   # +2 reps per step for rep work (8 → 18 at the cap)


def global_day_number(level: str, day_index: int) -> int:
    """A monotonic session number across all levels (never resets between them).

    Foundation 1..21 → 1..21, Explosive → 22..42, the top/maintenance level →
    43+ (its day_index already keeps growing across cycles). Used only to pace
    the daily staples, so they keep getting harder regardless of level."""
    try:
        base = LEVELS.index(level) * SESSIONS_PER_LEVEL
    except ValueError:
        base = 0
    return base + day_index


def daily_target(ex: Exercise, global_day: int, bias: int = 0) -> dict:
    """Progressive target for a daily-staple exercise at a given training age.

    Steps up ~weekly (capped), then `bias` applies the same pain/RPE
    autoregulation as the rest of the program (hard/pain → ease off)."""
    step = min(max(global_day - 1, 0) // DAILY_STEP_DAYS, DAILY_STEP_CAP)
    step = max(0, min(step + bias, DAILY_STEP_CAP + 2))
    t = dict(ex.target)
    if step == 0:
        return t
    if ex.kind == "timed" and "sec" in t:
        t["sec"] = t["sec"] + DAILY_BUMP_SEC * step
    elif "reps" in t:
        t["reps"] = t["reps"] + DAILY_BUMP_REPS * step
    return t


def alternatives_for(key: str, exclude: set[str]) -> list[Exercise]:
    """Knee-safe substitutes for an exercise: same day-type, not already in the
    session. Used by the "swap if it hurts" substitution."""
    ex = EXERCISES.get(key)
    if ex is None:
        return []
    out = [
        e for e in _EX
        if e.day_type == ex.day_type and e.key != key and e.key not in exclude
        and e.key not in WARMUP_KEYS
    ]
    return out[:3]
