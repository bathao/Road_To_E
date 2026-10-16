"""Step-by-step instructions per exercise (shown in the expandable card).

Part of the static programme package (split 2026-10-16 from program.py;
see REFACTOR.md §4.2). Import names via ``app.features.training.program``.
"""
from __future__ import annotations

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
    "jump_rope": (
        "Rope length: handles reach the armpits when you stand on the middle of the rope.",
        "Elbows close to the body, turn the rope from the WRISTS, not the shoulders.",
        "Bounce LOW (a few cm), land softly on the toes with the knees slightly soft.",
        "Go in short blocks (e.g. 30–50 jumps), rest, repeat — any time of day counts.",
        "Past 100 jumps in total → tick the item. Knee pain during or after → stop and Skip it.",
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
