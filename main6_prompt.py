def create_classification_prompt_video():
    """Create a detailed prompt for Vertex AI Gemini to classify workout videos using video content and metadata."""
    # Updated prompt emphasizing video analysis AND specifying segment if provided
    prompt = """You are a specialized AI fitness analyst. Your task is to analyze the **content of the provided YouTube video segment**, along with its **metadata** (title, description, tags, channel info, comments, full duration), and classify the workout based *primarily on what happens within the specified time segment*.

**IMPORTANT: You will be given a specific time segment (e.g., start/end offsets) for the video. Focus your analysis of exercises, intensity, pace, etc., solely on what occurs within that segment.** Use the full video metadata (like title, description) only as secondary context if the segment itself is ambiguous.

**Within the specified video segment, pay close attention to**:
* What exercises are being performed?
* What is the intensity level demonstrated (speed, effort)?
* What equipment is used (if any)?
* What is the instructor's style and instructions during this segment?
* What is the pace and flow during this segment?
* Does the music or tone during this segment suggest a particular mood?

Combine these observations *from the segment* with the overall textual metadata to make your classification as accurate as possible for the *activity within the segment*.

Aerobic Metabolic Functions:
- Zone 1 (recovery): Very light intensity, conversational pace, primarily fat burning, perfect for active recovery.
- Zone 2 (mitochondrial improvement): Moderate intensity where you can still talk but with some effort. Builds base endurance and improves mitochondrial function.
- Functional Threshold: Challenging intensity that can be sustained for 12-25 minutes, improves lactate threshold.
- HIIT: Short, intense bursts followed by rest periods. Improves VO2 max and anaerobic capacity.

Strength Metabolic Functions:
- Functional strength: Movements that mimic real-life activities, improves movement patterns and daily life capabilities.
- Hypertrophy: Moderate weights with higher rep ranges (8-12), focuses on muscle growth.
- Maximal strength: Heavy weights with low reps (1-5), focuses on strength development.
- Muscle endurance: Light to moderate weights with high reps (15+), improves ability to sustain effort.
- Power: Explosive movements combining speed and strength, improves rate of force development.

Flexibility Metabolic Functions:
- Range of motion: Improves joint mobility and muscle flexibility.
- Balance: Improves proprioception, stability, and body control.

BODY PART FOCUS EXPLANATION:
- Arms: Biceps, triceps, forearms, shoulders, deltoids
- Back: Lats, traps, rhomboids, spinal erectors, rear deltoids
- Chest: Pectorals, anterior deltoids, serratus anterior
- Legs: Quadriceps, hamstrings, glutes, calves, hip flexors, adductors, abductors

For body part focus, provide a percentage focus for each body part (Arms, Back, Chest, Legs). The values should sum to 1.0 (100%). For a balanced full-body workout, use equal distribution (0.25 for each part). For targeted workouts, allocate higher percentages to the primary focus areas. Additionally, provide an overall confidence level for your body part focus analysis.

Include confidence levels for "vibes" and "spirits" to indicate your overall certainty in the analysis of these aspects of the workout.

WORKOUT SPIRIT EXPLANATIONS:
- High-Energy & Intense: Fast-paced, heart-pumping, sweat-dripping sessions focused on pushing limits and maximum effort.
- Flow & Rhythm: Smooth, continuous movement patterns that emphasize coordination, music-driven pacing, and mind-body connection.
- Structured & Disciplined: Methodical, progressive training following specific protocols and technical precision.
- Soothing & Restorative: Gentle, healing-focused sessions emphasizing recovery, relaxation, and stress reduction.
- Sport & Agility: Athletic, performance-based training focused on speed, reflexes, coordination, and sports-specific skills.
- Outdoor & Adventure: Nature-based workouts that leverage terrain, environmental challenges, and exploration.

WORKOUT VIBE DETAILS:
1. The Warrior Workout: Unleash your inner beast. Sweat-dripping, heart-pounding, primal energy.  
   - Example Workouts: HIIT, boxing, bootcamp, heavy strength training.  
   - Platforms: Peloton Bootcamp, Les Mills BodyCombat, Beachbody Insanity, iFit HIIT.  
   - Best For: Days when you want to destroy stress and feel invincible.
2. The Firestarter: Fast, explosive, and electrifying. Short but devastating.  
   - Example Workouts: Tabata, sprint intervals, powerlifting bursts.  
   - Platforms: Peloton HIIT Rides, iFit Sprint Workouts, Nike Training Club Quick HIIT.  
   - Best For: When you only have 10-20 minutes but want to give 1000%.
3. The Nightclub Workout: Lights down, music up, full-body euphoria.  
   - Example Workouts: Dance cardio, rhythm boxing, cycle party rides.  
   - Platforms: Peloton EDM Rides, Les Mills Sh’Bam, Apple Fitness+ Dance, Zumba.  
   - Best For: When you want to move like no one’s watching and feel amazing.
4. The Competitor: Gamified, leaderboard-driven, full-send energy.  
   - Example Workouts: Live cycling, rowing races, CrossFit, esports-style fitness.  
   - Platforms: Peloton Leaderboard, Zwift Races, Hydrow Competitive Rows.  
   - Best For: Those who need to chase a score or beat their own record.
5. The Adrenaline Rush: Heart-racing, full-body intensity, unpredictable challenges.  
   - Example Workouts: Obstacle course training, parkour, extreme bootcamps.  
   - Platforms: Tough Mudder Training, Spartan Race Workouts, Freeletics.  
   - Best For: Those who crave challenge, variety, and adrenaline.
6. The Groove Session: Fun, fluid, expressive, completely in the moment.  
   - Example Workouts: Dance-based workouts, shadowboxing, flow yoga.  
   - Platforms: Apple Fitness+ Dance, Peloton Boxing, Barre3, Les Mills BodyBalance.  
   - Best For: Days when you want to move intuitively and just vibe.
7. The Meditative Grind: Zone in, lock down, let repetition take over.  
   - Example Workouts: Rowing, long-distance cycling, endurance running.  
   - Platforms: Hydrow Endurance Rows, Peloton Endurance Rides, iFit Scenic Runs.  
   - Best For: Those who love a slow burn and rhythmic intensity.
8. The Zen Flow: Grounding, intentional, breath-centered, unhurried.  
   - Example Workouts: Slow-flow yoga, tai chi, mobility training.  
   - Platforms: Alo Moves, Peloton Yoga, iFit Recovery Workouts.  
   - Best For: When you need balance, mindfulness, and release.
9. The Rhythmic Powerhouse: Beat-driven, strong but fluid, music-infused.  
   - Example Workouts: Power yoga, dance strength, cardio boxing.  
   - Platforms: Les Mills BodyJam, Peloton Boxing, Barre3.  
   - Best For: When you want strength and rhythm to blend seamlessly.
10. The Endorphin Wave: Elevated energy, feel-good movement, steady build.  
    - Example Workouts: Cycling climbs, endurance rowing, plyometric flows.  
    - Platforms: Peloton Power Zone Rides, iFit Rowing Journeys.  
    - Best For: When you want a challenging but steady burn.
11. The Progression Quest: Methodical, incremental, long-term improvement.  
    - Example Workouts: Strength cycles, hypertrophy training, marathon training plans.  
    - Platforms: iFit Progressive Strength, Tonal Programs, Peloton Strength Plans.  
    - Best For: Anyone who loves tracking progress and leveling up.
12. The Masterclass Workout: Technique-driven, focused, skill-building.  
    - Example Workouts: Pilates, kettlebell training, Olympic lifting, mobility drills.  
    - Platforms: Les Mills Core, Kettlebell Workouts on YouTube, Ready State Mobility.  
    - Best For: Those who love precision and mastery in movement.
13. The Disciplined Grind: No excuses, no distractions, just execute.  
    - Example Workouts: Classic bodybuilding, strength endurance, functional fitness.  
    - Platforms: Fitness Blender Strength, iFit Gym Workouts, Peloton Power Zones.  
    - Best For: When you want pure focus and efficiency.
14. The Tactical Athlete: Military-inspired, performance-focused, strategic.  
    - Example Workouts: Ruck training, tactical fitness, functional circuits.  
    - Platforms: Mountain Tactical Institute, Navy SEAL Workouts, Tactical Barbell.  
    - Best For: Those who want military-grade training and real-world capability.
15. The Foundation Builder: Strengthen weak points, rebuild, perfect the basics.  
    - Example Workouts: Stability, corrective exercise, injury prevention.  
    - Platforms: GOWOD, Ready State Mobility, Foundation Training.  
    - Best For: Those coming back from injury or refining fundamentals.
16. The Reboot Workout: Deep stretch, low stress, total-body refresh.  
    - Example Workouts: Gentle yoga, mobility drills, foam rolling.  
    - Platforms: Peloton Recovery, GOWOD, iFit Mobility.  
    - Best For: Recovery days, stress relief, post-travel stiffness.
17. The Comfort Moves: Safe, cozy, feel-good movement.  
    - Example Workouts: Chair workouts, senior fitness, prenatal/postnatal movement.  
    - Platforms: SilverSneakers, Fitness Blender Low-Impact, YouTube Chair Workouts.  
    - Best For: Those who want to move but need it to feel easy and accessible.
18. The Mindful Walk: Meditative, story-driven, immersive.  
    - Example Workouts: Guided outdoor walks, treadmill hikes.  
    - Platforms: Apple Fitness+ Time to Walk, iFit Outdoor Walks.  
    - Best For: When you need fresh air, a change of pace, and mental clarity.
19. The Deep Recharge: Nervous system reset, ultra-gentle movement.  
    - Example Workouts: Yoga Nidra, breathwork, passive stretching.  
    - Platforms: Yoga with Adriene, Headspace Yoga, iRest Meditation.  
    - Best For: Times of extreme stress, fatigue, or mental overload.
20. The Sleep Prep: Wind down, ease tension, prepare for rest.  
    - Example Workouts: Bedtime yoga, deep breathing, progressive relaxation.  
    - Platforms: Calm App, Peloton Sleep Yoga, Yoga Nidra.  
    - Best For: When you need the best possible night’s sleep.
21. The Athlete’s Circuit: Explosive power, agility, game-ready fitness.  
    - Example Workouts: Sprint drills, plyometrics, sport-specific agility.  
    - Platforms: Nike Training Club, Vertimax Workouts, P90X.  
    - Best For: Those training for sports or improving athleticism.
22. The Speed & Power Sprint: Short, high-speed, maximal power output.  
    - Example Workouts: Sprint workouts, fast-twitch training, overspeed drills.  
    - Platforms: Peloton Tread Intervals, Sprint Workouts, EXOS Training.  
    - Best For: Those improving speed, acceleration, and fast reactions.
23. The Fight Camp: Grit, intensity, combat-ready fitness.  
    - Example Workouts: MMA training, heavy bag work, footwork drills.  
    - Platforms: FightCamp, Bas Rutten Workouts, Les Mills BodyCombat.  
    - Best For: Those who want to train like a fighter.
24. The Explorer’s Workout: Adventurous, scenic, open-air challenge.  
    - Example Workouts: Trail running, outdoor HIIT, sand dune sprints.  
    - Platforms: iFit Outdoor Series, Trail Running Workouts.  
    - Best For: When you want nature, challenge, and adventure.
25. The Ruck Challenge: Weighted backpack, functional endurance.  
    - Example Workouts: Rucking, weighted hikes, uphill treks.  
    - Platforms: GoRuck Programs, Tactical Training Workouts.  
    - Best For: Those who want real-world endurance and strength.
26. The Nature Flow: Breath-centered, full-body, outdoor rhythm.  
    - Example Workouts: Beach workouts, rock climbing drills, park workouts.  
    - Platforms: iFit Beach Sessions, Outdoor Bootcamps.  
    - Best For: When you want fresh air, nature, and full-body movement.

ANALYSIS GUIDELINES:
1.  **Prioritize the video content within the specified time segment**.
2.  Use metadata (title, description, tags, comments) as **secondary supporting context**.
3.  Infer intensity, duration (of exercises *in the segment*), exercise types from the video segment.
4.  When confidence is low for a category based on the short segment, mark it "low". If a category doesn't apply (e.g., strength functions in a pure cardio segment), provide an empty array `[]` for list properties or use reasonable defaults. Ensure bodyPartFocus percentages sum to 1.0.
5.  For 'vibes' and 'spirits', identify up to 3 most suitable entries reflecting the segment, with a prominence value (0.0 to 1.0) for each. Sum of prominence is not restricted.
6.  Adhere strictly to the JSON output format and schema.

CONFIDENCE LEVELS EXPLANATION: (Based on clarity within the segment)
- "very high": Obvious and central focus clearly demonstrated within the segment.
- "high": Clearly identifiable component, strong evidence within the segment.
- "moderate": Reasonable inference from the segment's context, likely present but not the sole focus.
- "low": Minimal indicators within the segment, educated guess, uncertain.

RESPONSE FORMAT:
Your entire response MUST be a single, valid JSON object conforming to the schema described below. Do not include any text, explanations, or markdown formatting before or after the JSON object.

TARGET JSON SCHEMA:
{
  "type": "object",
  "properties": {
    "category": { "type": "string", "enum": ["Cardio", "Cool-down", "Flexibility", "Rest", "Strength", "Warm-up"] },
    "categoryConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "subcategory": { "type": "string", "enum": ["Body weight", "Breathing exercises", "Calisthenics", "Cool-down", "Elliptical", "HIIT", "Indoor biking", "Indoor rowing", "Mat", "Meditation", "Pilates", "Running", "Stretching", "Treadmill", "Walking", "Warm-up", "Weight workout", "Yoga"] },
    "subcategoryConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "aerobicMetabolicFunction": {
      "type": "array",
      "items": { "type": "string", "enum": ["Zone 1 (recovery)", "Zone 2 (mitochondrial improvement)", "Functional Threshold (or anaerobic threshold training) - 12-25 minutes", "HIIT - High Intensity Interval Training (30s to 10m reps and rest)"] },
      "uniqueItems": true
    },
    "aerobicMetabolicFunctionConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "strengthMetabolicFunction": {
      "type": "array",
      "items": { "type": "string", "enum": ["Functional strength", "Hypertrophy", "Maximal strength", "Muscle endurance", "Power"] },
      "uniqueItems": true
    },
    "strengthMetabolicFunctionConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "flexibilityMetabolicFunction": {
      "type": "array",
      "items": { "type": "string", "enum": ["Range of motion", "Balance"] },
      "uniqueItems": true
    },
    "flexibilityMetabolicFunctionConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "bodyPartFocus": {
      "type": "object",
      "properties": {
        "Arms": {"type": "number", "minimum": 0, "maximum": 1},
        "Back": {"type": "number", "minimum": 0, "maximum": 1},
        "Chest": {"type": "number", "minimum": 0, "maximum": 1},
        "Legs": {"type": "number", "minimum": 0, "maximum": 1}
      },
      "required": ["Arms", "Back", "Chest", "Legs"],
      "additionalProperties": false
    },
     "bodyPartFocusConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "vibes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          # Make sure to list ALL 26 vibe names in the enum below
          "name": {"type": "string", "enum": ["The Warrior Workout", "The Firestarter", "The Zen Master", "The Power Builder", "The Enduro Champ", "The Agility Ace", "The Recovery Ritual", "The Morning Energizer", "The Lunchtime Lift", "The Evening Unwind", "The Dance Fusion", "The Core Crusher", "The Flexibility Flow", "The Strength Circuit", "The Cardio Blast", "The Mindful Mover", "The Body Sculptor", "The Athletic Performer", "The Calisthenics King/Queen", "The Pilates Pro", "The Yoga Guru", "The Boxing Powerhouse", "The Runner's High", "The Cyclist's Climb", "The Swimmer's Glide", "The Nature Flow"]},
          "prominence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["name", "prominence"]
      },
      "minItems": 0, "maxItems": 3
    },
    "vibesConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "spirits": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "enum": ["High-Energy & Intense", "Flow & Rhythm", "Structured & Disciplined", "Soothing & Restorative", "Sport & Agility", "Outdoor & Adventure"]},
          "prominence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["name", "prominence"]
      },
      "minItems": 0, "maxItems": 3
    },
    "spiritsConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] }
  },
  "required": [
      "category", "categoryConfidence", "subcategory", "subcategoryConfidence",
      "aerobicMetabolicFunction", "aerobicMetabolicFunctionConfidence",
      "strengthMetabolicFunction", "strengthMetabolicFunctionConfidence",
      "flexibilityMetabolicFunction", "flexibilityMetabolicFunctionConfidence",
      "bodyPartFocus", "bodyPartFocusConfidence",
      "vibes", "vibesConfidence",
      "spirits", "spiritsConfidence"
   ],
  "additionalProperties": false
}

Now, analyze the following video segment and its associated metadata:
"""
    # The actual metadata text and video Part (with segment info) will be appended after this prompt text
    return prompt
