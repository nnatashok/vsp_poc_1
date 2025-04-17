from googleapiclient.discovery import build
from openai import OpenAI, OpenAIError
import json
import os
import re
import time
import random
from urllib.parse import urlparse, parse_qs
import isodate  # For parsing ISO 8601 duration format

# -----------------------------------------------------------------------------
# SCHEMAS AND PROMPTS FOR ALL CLASSIFIERS
# -----------------------------------------------------------------------------

# 1. CATEGORY CLASSIFICATION
CATEGORY_PROMPT = """You are a specialized AI fitness analyst. Your task is to analyze YouTube workout video metadata and classify the workout into specific categories. Examine the title, description, comments, tags, channel information, and any other available metadata to make your classification as accurate as possible.

WORKOUT CATEGORY DESCRIPTIONS:
- Elliptical: Workout involving an elliptical machine for low-impact cardio exercise.
- HIIT: High-Intensity Interval Training with alternating periods of intense exercise and rest.
- Indoor biking: Stationary cycling workouts, spin classes, or indoor cycling sessions.
- Mat: General floor exercises performed on an exercise mat, often without equipment.
- Treadmill: Running or walking workouts performed on a treadmill.
- Pilates: Exercise method focused on controlled movements, core strength, and body alignment.
- Stretching: Focused flexibility training to improve range of motion.
- Yoga: Mind-body practice combining physical postures, breathing techniques, and meditation.
- Breathing exercises: Focused practice of controlled breathing techniques for relaxation or performance.
- Meditation: Mental practices focused on mindfulness, awareness, and concentration.
- Body weight: Strength training exercises using only body weight as resistance.
- Calisthenics: Gymnastic exercises for strength and flexibility using bodyweight movements.
- Weight workout: Training with free weights, machines, or resistance equipment.

ANALYSIS GUIDELINES:
1. Examine the title, description, and tags carefully for explicit workout information.
2. Look for indicators of intensity, duration, and exercise types.
3. Consider the channel's focus and typical content style.
4. User comments may provide additional clues about the workout experience.
5. When confidence is low for a category, mark it appropriately.
6. For each workout, identify 1-3 most suitable categories that match the workout, with a score value (0-1) for each.
7. Provide a detailed explanation of why you assigned specific categories, citing evidence from the metadata.

CATEGORIES EXPLANATION GUIDELINES:
When writing the 'categoriesExplanation' field, provide a detailed and structured analysis that:
1. Explains why each selected category was chosen, with specific evidence from the metadata
2. Cites specific words, phrases, or terms from the title, description, or other metadata
3. Justifies the score assigned to each category
4. Mentions any uncertainty or ambiguity in the classification
5. Explains why other potential categories were excluded (if relevant)
6. Keep explanations concise but comprehensive (typically 100-200 words)

CONFIDENCE LEVELS EXPLANATION:
- 0.8-1.0: Very high confidence - Strong explicit indicators in title, description, or visuals
- 0.6-0.79: High confidence - Clear indicators or strong implicit evidence
- 0.4-0.59: Moderate confidence - Some indicators or reasonable inference from context
- 0.2-0.39: Low confidence - Minimal indicators or educated guess
- 0-0.19: Very low confidence - Extremely limited evidence, mostly guesswork

SCORE VALUES EXPLANATION:
- 0.8-1.0: Extremely strong presence, central defining characteristic
- 0.6-0.79: Strong presence, clearly evident
- 0.4-0.59: Moderate presence, noticeable element
- 0.2-0.39: Mild presence, somewhat evident
- 0-0.19: Slight presence, minor element

Your response must follow the JSON schema provided in the API call. If there's insufficient information for a particular category, use your best judgment and provide the most likely options based on available data.
"""

CATEGORY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "WorkoutAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "enum": [
                                    "Elliptical", "HIIT", "Indoor biking", "Mat", "Treadmill",
                                    "Pilates", "Stretching", "Yoga", "Breathing exercises",
                                    "Meditation", "Body weight", "Calisthenics", "Weight workout"
                                ]
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["name", "score"]
                    },
                    "minItems": 1,
                    "maxItems": 3
                },
                "categoriesConfidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "categoriesExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of why specific categories were assigned, with evidence from metadata."
                }
            },
            "required": ["categories", "categoriesConfidence", "categoriesExplanation"],
            "additionalProperties": False
        }
    }
}

# 2. FITNESS LEVEL CLASSIFICATION
FITNESS_LEVEL_PROMPT = """You are a specialized AI fitness analyst. Your task is to analyze YouTube workout video metadata and classify the workout based on three key metrics:
1. Technique Difficulty: How complex and challenging the exercises are to perform correctly
2. Effort Difficulty: How physically demanding the workout is based on duration and energy expenditure
3. Required Fitness Level: The fitness level needed to complete the workout (derived from the first two metrics)

Examine the title, description, comments, tags, channel information, and any other available metadata to make your classification as accurate as possible.

CLASSIFICATION METRICS DESCRIPTIONS:

1. TECHNIQUE DIFFICULTY:
   This measures how complex the movements are to execute with proper form.
   - Beginner: Simple, straightforward movements with minimal coordination required (e.g., basic squats, simple stretches)
   - Intermediate: Moderately complex movements requiring some coordination (e.g., lunges with rotation, intermediate yoga poses)
   - Advanced: Complex movements requiring significant coordination and body awareness (e.g., Olympic lifts, advanced yoga inversions)
   - Expert: Highly technical movements requiring extensive practice and specialized skills (e.g., complex gymnastics, advanced calisthenics)

2. EFFORT DIFFICULTY:
   This measures how physically demanding the workout is, dependent on:
   - Duration of training (longer workouts typically require more effort)
   - Energy expenditure of each exercise (high-intensity exercises consume more energy)
   - Rest periods (shorter rest periods increase effort difficulty)
   - Volume and intensity of work (more sets/reps at higher intensity increase difficulty)

   Levels:
   - Light: Low energy expenditure, suitable for recovery days or beginners (e.g., walking, gentle stretching)
   - Moderate: Medium energy expenditure, moderately challenging (e.g., light jogging, bodyweight circuit)
   - Challenging: High energy expenditure, requires significant effort (e.g., HIIT workouts, heavy weightlifting)
   - Extreme: Very high energy expenditure, pushes physical limits (e.g., intense CrossFit WODs, marathon training)

3. REQUIRED FITNESS LEVEL:
   This is a derived metric based on both technique difficulty and effort difficulty:
   - Beginner: Suitable for people new to exercise or returning after long breaks
   - Intermediate: Appropriate for those with some consistent exercise experience (3-6 months)
   - Advanced: Designed for dedicated fitness enthusiasts with solid experience (6+ months)
   - Elite: Created for highly trained individuals, athletes, or fitness professionals

ANALYSIS GUIDELINES:
1. Examine the title, description, and tags carefully for explicit difficulty indicators.
2. Look for keywords suggesting intensity, complexity, and target audience.
3. Consider the channel's typical audience and content style.
4. User comments may provide insights about perceived difficulty.
5. For each metric, assign scores to all applicable levels based on their relevance to the workout. Include multiple levels when:
   - Different intensity and complexity options are suggested (e.g. weight variations or alternate exercises)
   - The workout is designed to be accessible to athletes of multiple fitness levels (e.g., "suitable for beginners through advanced")
6. Provide a detailed explanation of your classification, citing evidence from the metadata.
7. Do not include levels with a score of 0 in your response. Only include levels that have a score greater than 0.

DETAILED ASSESSMENT FACTORS:

For Technique Difficulty, consider:
- Complexity of movements described
- Required coordination and balance
- Number of simultaneous movement patterns
- Stability requirements
- Range of motion demands
- References to form, technique, or proper execution
- Instructor cues about form correction

For Effort Difficulty, analyze:
- Stated workout duration
- Energy expenditure indicators (e.g., "high burn," "intense," "sweat")
- Rest periods mentioned (shorter = harder)
- Exercise tempos (faster typically = harder)
- Repetition ranges or time under tension
- Cardiovascular demands
- References to fatigue, exhaustion, or challenge

For Required Fitness Level, evaluate the combination of the above plus:
- Explicit targeting ("beginner-friendly," "advanced athletes only")
- Progression options mentioned
- Modification suggestions
- Prerequisites mentioned
- Community feedback about accessibility

SCORE VALUES EXPLANATION:
- 0.8-1.0: Extremely strong alignment with this level, definitive classification
- 0.6-0.79: Strong alignment, clearly fits this level
- 0.4-0.59: Moderate alignment, fits this level with some caveats
- 0.2-0.39: Mild alignment, somewhat fits this level
- 0-0.19: Minimal alignment, barely fits this level

CONFIDENCE LEVELS EXPLANATION:
- 0.8-1.0: Very high confidence - Strong explicit indicators in metadata
- 0.6-0.79: High confidence - Clear indicators or strong implicit evidence
- 0.4-0.59: Moderate confidence - Some indicators or reasonable inference from context
- 0.2-0.39: Low confidence - Minimal indicators or educated guess
- 0-0.19: Very low confidence - Extremely limited evidence, mostly guesswork

EXPLANATION GUIDELINES:
When writing explanation fields, provide detailed analysis that:
1. Explains why each level was assigned, with specific evidence from the metadata
2. Cites specific words, phrases, or terms from the title, description, or other metadata
3. Justifies the score assigned to each level
4. Explains relationships between technique difficulty, effort difficulty, and required fitness level
5. Mentions any uncertainty or ambiguity in the classification
6. Keep explanations concise but comprehensive (typically 100-200 words per metric)

Analyze the workout video metadata provided and classify its technique difficulty, effort difficulty, and required fitness level according to the schema.
"""

FITNESS_LEVEL_USER_PROMPT = "Analyze this workout video metadata and classify its technique difficulty, effort difficulty, and required fitness level according to the schema:"

FITNESS_LEVEL_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "WorkoutAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "techniqueDifficulty": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "enum": ["Beginner", "Intermediate", "Advanced", "Expert"]
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["level", "score"]
                    },
                    "minItems": 1,
                    "maxItems": 4
                },
                "techniqueDifficultyConfidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "techniqueDifficultyExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of technique difficulty classification with evidence from metadata."
                },
                "effortDifficulty": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "enum": ["Light", "Moderate", "Challenging", "Extreme"]
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["level", "score"]
                    },
                    "minItems": 1,
                    "maxItems": 4
                },
                "effortDifficultyConfidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "effortDifficultyExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of effort difficulty classification with evidence from metadata."
                },
                "requiredFitnessLevel": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "enum": ["Beginner", "Intermediate", "Advanced", "Elite"]
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["level", "score"]
                    },
                    "minItems": 1,
                    "maxItems": 4
                },
                "requiredFitnessLevelConfidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "requiredFitnessLevelExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of required fitness level classification with justification of how it was derived from technique and effort difficulty."
                }
            },
            "required": [
                "techniqueDifficulty", "techniqueDifficultyConfidence", "techniqueDifficultyExplanation",
                "effortDifficulty", "effortDifficultyConfidence", "effortDifficultyExplanation",
                "requiredFitnessLevel", "requiredFitnessLevelConfidence", "requiredFitnessLevelExplanation"
            ],
            "additionalProperties": False
        }
    }
}

# 3. VIBE CLASSIFICATION
VIBE_PROMPT = """You are a specialized AI fitness vibe analyst. Your task is to analyze YouTube workout video metadata and classify the workout into specific "workout vibes" - the emotional and experiential qualities of the workout. Examine the title, description, comments, tags, channel information, and any other available metadata to make your classification as accurate as possible.

WORKOUT VIBE DESCRIPTIONS:
- The Warrior Workout: Unleash your inner beast. Sweat-dripping, heart-pounding, primal energy. (Examples: HIIT, boxing, bootcamp, heavy strength training.)
- The Firestarter: Fast, explosive, and electrifying. Short but devastating. (Examples: Tabata, sprint intervals, powerlifting bursts.)
- The Nightclub Workout: Lights down, music up, full-body euphoria. (Examples: Dance cardio, rhythm boxing, cycle party rides.)
- The Competitor: Gamified, leaderboard-driven, full-send energy. (Examples: Live cycling, rowing races, CrossFit, esports-style fitness.)
- The Adrenaline Rush: Heart-racing, full-body intensity, unpredictable challenges. (Examples: Obstacle course training, parkour, extreme bootcamps.)
- The Groove Session: Fun, fluid, expressive, completely in the moment. (Examples: Dance-based workouts, shadowboxing, flow yoga.)
- The Meditative Grind: Zone in, lock down, let repetition take over. (Examples: Rowing, long-distance cycling, endurance running.)
- The Zen Flow: Grounding, intentional, breath-centered, unhurried. (Examples: Slow-flow yoga, tai chi, mobility training.)
- The Rhythmic Powerhouse: Beat-driven, strong but fluid, music-infused. (Examples: Power yoga, dance strength, cardio boxing.)
- The Endorphin Wave: Elevated energy, feel-good movement, steady build. (Examples: Cycling climbs, endurance rowing, plyometric flows.)
- The Progression Quest: Methodical, incremental, long-term improvement. (Examples: Strength cycles, hypertrophy training, marathon training plans.)
- The Masterclass Workout: Technique-driven, focused, skill-building. (Examples: Pilates, kettlebell training, Olympic lifting, mobility drills.)
- The Disciplined Grind: No excuses, no distractions, just execute. (Examples: Classic bodybuilding, strength endurance, functional fitness.)
- The Tactical Athlete: Military-inspired, performance-focused, strategic. (Examples: Ruck training, tactical fitness, functional circuits.)
- The Foundation Builder: Strengthen weak points, rebuild, perfect the basics. (Examples: Stability, corrective exercise, injury prevention.)
- The Reboot Workout: Deep stretch, low stress, total-body refresh. (Examples: Gentle yoga, mobility drills, foam rolling.)
- The Comfort Moves: Safe, cozy, feel-good movement. (Examples: Chair workouts, senior fitness, prenatal/postnatal movement.)
- The Mindful Walk: Meditative, story-driven, immersive. (Examples: Guided outdoor walks, treadmill hikes.)
- The Deep Recharge: Nervous system reset, ultra-gentle movement. (Examples: Yoga Nidra, breathwork, passive stretching.)
- The Sleep Prep: Wind down, ease tension, prepare for rest. (Examples: Bedtime yoga, deep breathing, progressive relaxation.)
- The Athlete's Circuit: Explosive power, agility, game-ready fitness. (Examples: Sprint drills, plyometrics, sport-specific agility.)
- The Speed & Power Sprint: Short, high-speed, maximal power output. (Examples: Sprint workouts, fast-twitch training, overspeed drills.)
- The Fight Camp: Grit, intensity, combat-ready fitness. (Examples: MMA training, heavy bag work, footwork drills.)
- The Explorer's Workout: Adventurous, scenic, open-air challenge. (Examples: Trail running, outdoor HIIT, sand dune sprints.)
- The Ruck Challenge: Weighted backpack, functional endurance. (Examples: Rucking, weighted hikes, uphill treks.)
- The Nature Flow: Breath-centered, full-body, outdoor rhythm. (Examples: Beach workouts, rock climbing drills, park workouts.)

ANALYSIS GUIDELINES:
1. Examine the title, description, and tags carefully for clues about the workout's emotional quality and experience.
2. Look for indicators of intensity, duration, music style, coaching approach, and exercise types.
3. Consider the channel's focus and typical content style.
4. User comments may provide additional clues about the emotional experience of the workout.
5. When confidence is low for a vibe, mark it appropriately.
6. For each workout, identify 1-3 most suitable vibes that match the workout, with a score value (0-1) for each.
7. Provide a detailed explanation of why you assigned specific vibes, citing evidence from the metadata.

VIBES EXPLANATION GUIDELINES:
When writing the 'vibesExplanation' field, provide a detailed and structured analysis that:
1. Explains why each selected vibe was chosen, with specific evidence from the metadata
2. Cites specific words, phrases, or terms from the title, description, or other metadata
3. Justifies the score assigned to each vibe
4. Mentions any uncertainty or ambiguity in the classification
5. Explains why other potential vibes were excluded (if relevant)
6. Keep explanations concise but comprehensive (typically 100-200 words)

CONFIDENCE LEVELS EXPLANATION:
- 0.8-1.0: Very high confidence - Strong explicit indicators in title, description, or visuals
- 0.6-0.79: High confidence - Clear indicators or strong implicit evidence
- 0.4-0.59: Moderate confidence - Some indicators or reasonable inference from context
- 0.2-0.39: Low confidence - Minimal indicators or educated guess
- 0-0.19: Very low confidence - Extremely limited evidence, mostly guesswork

SCORE VALUES EXPLANATION:
- 0.8-1.0: Extremely strong match, perfect embodiment of the vibe
- 0.6-0.79: Strong match, clearly fits this vibe
- 0.4-0.59: Moderate match, noticeable elements of this vibe
- 0.2-0.39: Mild match, somewhat fits this vibe
- 0-0.19: Slight match, minor elements of this vibe

Your response must follow the JSON schema provided in the API call. If there's insufficient information for a particular vibe, use your best judgment and provide the most likely options based on available data.
"""

VIBE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "WorkoutVibeAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "vibes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "enum": [
                                    "The Warrior Workout", "The Firestarter", "The Nightclub Workout", "The Competitor",
                                    "The Adrenaline Rush", "The Groove Session", "The Meditative Grind", "The Zen Flow",
                                    "The Rhythmic Powerhouse", "The Endorphin Wave", "The Progression Quest",
                                    "The Masterclass Workout", "The Disciplined Grind", "The Tactical Athlete",
                                    "The Foundation Builder", "The Reboot Workout", "The Comfort Moves",
                                    "The Mindful Walk", "The Deep Recharge", "The Sleep Prep", "The Athlete's Circuit",
                                    "The Speed & Power Sprint", "The Fight Camp", "The Explorer's Workout",
                                    "The Ruck Challenge", "The Nature Flow"
                                ]
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["name", "score"]
                    },
                    "minItems": 1,
                    "maxItems": 3
                },
                "vibesConfidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "vibesExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of why specific vibes were assigned, with evidence from metadata."
                }
            },
            "required": ["vibes", "vibesConfidence", "vibesExplanation"],
            "additionalProperties": False
        }
    }
}

# 4. SPIRIT CLASSIFICATION
SPIRIT_PROMPT = """You are a specialized AI fitness spirit analyst. Your task is to analyze YouTube workout video metadata and classify the workout into specific "workout spirits" - the fundamental energetic qualities of the workout. Examine the title, description, comments, tags, channel information, and any other available metadata to make your classification as accurate as possible.

WORKOUT SPIRIT EXPLANATIONS:
- High-Energy & Intense: Fast-paced, heart-pumping, sweat-dripping sessions focused on pushing limits and maximum effort.
- Flow & Rhythm: Smooth, continuous movement patterns that emphasize coordination, music-driven pacing, and mind-body connection.
- Structured & Disciplined: Methodical, progressive training following specific protocols and technical precision.
- Soothing & Restorative: Gentle, healing-focused sessions emphasizing recovery, relaxation, and stress reduction.
- Sport & Agility: Athletic, performance-based training focused on speed, reflexes, coordination, and sports-specific skills.
- Outdoor & Adventure: Nature-based workouts that leverage terrain, environmental challenges, and exploration.

ANALYSIS GUIDELINES:
1. Examine the title, description, and tags carefully for clues about the workout's fundamental energy and approach.
2. Look for indicators of intensity, flow, structure, recovery focus, sports-specificity, and environment.
3. Consider the channel's focus and typical content style.
4. User comments may provide additional clues about the spirit of the workout.
5. When confidence is low for a spirit, mark it appropriately.
6. For each workout, identify 1-3 most suitable spirits that match the workout, with a score value (0-1) for each.
7. Provide a detailed explanation of why you assigned specific spirits, citing evidence from the metadata.

SPIRITS EXPLANATION GUIDELINES:
When writing the 'spiritsExplanation' field, provide a detailed and structured analysis that:
1. Explains why each selected spirit was chosen, with specific evidence from the metadata
2. Cites specific words, phrases, or terms from the title, description, or other metadata
3. Justifies the score assigned to each spirit
4. Mentions any uncertainty or ambiguity in the classification
5. Explains why other potential spirits were excluded (if relevant)
6. Keep explanations concise but comprehensive (typically 100-200 words)

CONFIDENCE LEVELS EXPLANATION:
- 0.8-1.0: Very high confidence - Strong explicit indicators in title, description, or visuals
- 0.6-0.79: High confidence - Clear indicators or strong implicit evidence
- 0.4-0.59: Moderate confidence - Some indicators or reasonable inference from context
- 0.2-0.39: Low confidence - Minimal indicators or educated guess
- 0-0.19: Very low confidence - Extremely limited evidence, mostly guesswork

SCORE VALUES EXPLANATION:
- 0.8-1.0: Extremely strong match, perfect embodiment of the spirit
- 0.6-0.79: Strong match, clearly fits this spirit
- 0.4-0.59: Moderate match, noticeable elements of this spirit
- 0.2-0.39: Mild match, somewhat fits this spirit
- 0-0.19: Slight match, minor elements of this spirit

Your response must follow the JSON schema provided in the API call. If there's insufficient information for a particular spirit, use your best judgment and provide the most likely options based on available data.
"""

SPIRIT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "WorkoutSpiritAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "spirits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "enum": [
                                    "High-Energy & Intense", 
                                    "Flow & Rhythm", 
                                    "Structured & Disciplined", 
                                    "Soothing & Restorative", 
                                    "Sport & Agility", 
                                    "Outdoor & Adventure"
                                ]
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["name", "score"]
                    },
                    "minItems": 1,
                    "maxItems": 3
                },
                "spiritsConfidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "spiritsExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of why specific spirits were assigned, with evidence from metadata."
                }
            },
            "required": ["spirits", "spiritsConfidence", "spiritsExplanation"],
            "additionalProperties": False
        }
    }
}

# 5. EQUIPMENT CLASSIFICATION
EQUIPMENT_PROMPT = """You are a specialized AI fitness equipment analyst. Your task is to analyze YouTube workout video metadata and identify what equipment is needed to perform the workout effectively.

Examine the title, description, comments, tags, channel information, and any other available metadata to make your classification as accurate as possible.

EQUIPMENT OPTIONS:
1. Mat - Used for floor exercises, yoga, pilates
2. Dumbbells - Hand weights of various sizes
3. Chair - Used for support, step-ups, or as a workout prop
4. Blocks - Yoga blocks or similar supportive equipment
5. Exercise bike - Stationary cycling equipment
6. Rowing machine - Indoor rowing equipment
7. Treadmill - Running/walking machine
8. Elliptical - Low-impact cardio machine
9. Resistance bands - Versatile elastic bands for strength training
10. Kettlebells - Cast iron or steel weights for ballistic exercises
11. Medicine balls - Weighted balls for strength and rehabilitation
12. Jump ropes - For cardio and coordination
13. Pull-up bars - For upper body strength development
14. Stability/Swiss balls - For core training and balance
15. TRX/Suspension trainers - For bodyweight resistance training
16. Weight bench - Platform for various strength exercises
17. Barbell - For compound movements
18. Battle ropes - Heavy ropes for high-intensity training
19. Ankle/wrist weights - For adding resistance to movements
20. Foam roller - For myofascial release and recovery
21. Other - Any equipment not listed above (specify in explanation)

ANALYSIS GUIDELINES:
1. Examine the title, description, and tags carefully for explicit equipment mentions.
2. Look for keywords suggesting what equipment is used or needed.
3. Consider the type of workout and what equipment would typically be used.
4. User comments may provide insights about equipment used or alternatives.
5. For each equipment type, assign confidence scores based on how likely it is that the equipment is required.
6. Provide a detailed explanation of your classification, citing evidence from the metadata.
7. Do not include equipment with a confidence score of 0 in your response. Only include equipment that has a score greater than 0.
8. If you identify equipment that isn't on the list, include it under "Other" and specify what it is in your explanation.
9. If the workout appears to require no equipment (bodyweight only), return an empty array for requiredEquipment.

CONFIDENCE LEVELS EXPLANATION:
- 0.8-1.0: Very high confidence - Equipment is explicitly mentioned as required and central to the workout
- 0.6-0.79: High confidence - Equipment is mentioned or strongly implied as needed for most exercises
- 0.4-0.59: Moderate confidence - Equipment is mentioned or implied for some exercises or as an option
- 0.2-0.39: Low confidence - Equipment is mentioned as optional or for a small portion of the workout
- 0-0.19: Very low confidence - Equipment is barely mentioned or only suggested as a possible alternative

EXPLANATION GUIDELINES:
When writing the required equipment explanation, provide detailed analysis that:
1. Explains why each equipment item was identified, with specific evidence from the metadata
2. Cites specific words, phrases, or terms from the title, description, or other metadata
3. Justifies the confidence score assigned to each equipment item
4. Mentions any uncertainty or ambiguity in the classification
5. For "Other" equipment, clearly specify what equipment was identified
6. If no equipment is required, explicitly state that the workout appears to be bodyweight only
7. Keep explanations concise but comprehensive (typically 100-200 words)

Analyze the workout video metadata provided and identify what equipment is needed according to the schema.
"""

EQUIPMENT_USER_PROMPT = "Analyze this workout video metadata and identify what equipment is needed according to the schema:"

EQUIPMENT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "WorkoutEquipmentAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "requiredEquipment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "equipment": {
                                "type": "string",
                                "enum": [
                                    "Mat", "Dumbbells", "Chair", "Blocks", "Exercise bike", 
                                    "Rowing machine", "Treadmill", "Elliptical", "Resistance bands", 
                                    "Kettlebells", "Medicine balls", "Jump ropes", "Pull-up bars", 
                                    "Stability/Swiss balls", "TRX/Suspension trainers", "Weight bench", 
                                    "Barbell", "Battle ropes", "Ankle/wrist weights", "Foam roller", 
                                    "Other"
                                ]
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["equipment", "confidence"]
                    }
                },
                "requiredEquipmentExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of equipment classification with evidence from metadata."
                }
            },
            "required": [
                "requiredEquipment", "requiredEquipmentExplanation"
            ],
            "additionalProperties": False
        }
    }
}

# -----------------------------------------------------------------------------
# MAIN UNIFIED CLASSIFIER CODE
# -----------------------------------------------------------------------------

def analyze_youtube_workout(youtube_url, cache_dir='cache_unified', force_refresh=False):
    """
    Analyzes a YouTube workout video and classifies it according to multiple dimensions:
    1. Category (e.g., Yoga, HIIT, Weight workout)
    2. Fitness level (technique difficulty, effort difficulty, required fitness level)
    3. Vibe (e.g., Warrior Workout, Zen Flow)
    4. Spirit (e.g., High-Energy & Intense, Flow & Rhythm)
    5. Equipment (e.g., Mat, Dumbbells, Resistance bands)

    Args:
        youtube_url (str): URL of the YouTube workout video
        cache_dir (str): Directory to store cached data
        force_refresh (bool): Whether to force fresh analysis even if cached data exists

    Returns:
        dict: Combined workout analysis across all dimensions
    """
    # API keys
    YOUTUBE_API_KEY = 'AIzaSyCkpiTfTUvNVNmPcyw8ZO1NOn_0b_LV8RA'
    OPENAI_API_KEY = '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'

    # Initialize clients
    try:
        oai_client = OpenAI(api_key=OPENAI_API_KEY)
        youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        return {"error": f"Failed to initialize API clients: {str(e)}"}

    # Extract video ID
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return {"error": "Invalid YouTube URL. Could not extract video ID."}

    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)

    # Check for cached combined analysis results
    combined_analysis_cache_path = os.path.join(cache_dir, f"{video_id}_combined_analysis.json")
    if os.path.exists(combined_analysis_cache_path) and not force_refresh:
        try:
            with open(combined_analysis_cache_path, 'r') as f:
                combined_analysis = json.load(f)
            print(f"Loaded combined analysis from cache: {combined_analysis_cache_path}")
            return combined_analysis
        except Exception as e:
            print(f"Error loading cached combined analysis: {str(e)}. Proceeding with fresh analysis.")

    # Fetch or load metadata
    metadata_cache_path = os.path.join(cache_dir, f"{video_id}_metadata.json")
    if os.path.exists(metadata_cache_path) and not force_refresh:
        try:
            with open(metadata_cache_path, 'r') as f:
                metadata = json.load(f)
            print(f"Loaded metadata from cache: {metadata_cache_path}")
        except Exception as e:
            print(f"Error loading cached metadata: {str(e)}. Fetching fresh metadata.")
            metadata = fetch_video_metadata(youtube_client, video_id)
            cache_data(metadata, metadata_cache_path)
    else:
        metadata = fetch_video_metadata(youtube_client, video_id)
        cache_data(metadata, metadata_cache_path)

    # Format metadata for analysis
    formatted_metadata = format_metadata_for_analysis(metadata)

    # Initialize combined analysis
    combined_analysis = {
        "video_id": video_id,
        "video_url": youtube_url,
        "video_title": metadata.get('title', ''),
        "channel_title": metadata.get('channelTitle', ''),
        "duration": metadata.get('durationFormatted', ''),
    }

    # Run each classifier in the specified order
    try:
        # 1. Category classifier
        category_analysis = classify_workout_category(oai_client, formatted_metadata)
        combined_analysis.update({"category": category_analysis})

        # 2. Fitness level classifier
        fitness_level_analysis = classify_workout_fitness_level(oai_client, formatted_metadata)
        combined_analysis.update({"fitness_level": fitness_level_analysis})

        # 3. Vibe classifier
        vibe_analysis = classify_workout_vibe(oai_client, formatted_metadata)
        combined_analysis.update({"vibe": vibe_analysis})

        # 4. Spirit classifier
        spirit_analysis = classify_workout_spirit(oai_client, formatted_metadata)
        combined_analysis.update({"spirit": spirit_analysis})

        # 5. Equipment classifier
        equipment_analysis = classify_workout_equipment(oai_client, formatted_metadata)
        combined_analysis.update({"equipment": equipment_analysis})

        # Cache the combined analysis
        cache_data(combined_analysis, combined_analysis_cache_path)

        return combined_analysis
    
    except Exception as e:
        return {"error": f"Failed to perform combined analysis: {str(e)}"}

def extract_video_id(youtube_url):
    """Extract YouTube video ID from URL."""
    if not youtube_url:
        return None

    # Handle mobile URLs (youtu.be)
    if 'youtu.be' in youtube_url:
        return youtube_url.split('/')[-1].split('?')[0]

    # Handle standard YouTube URLs
    parsed_url = urlparse(youtube_url)
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query).get('v', [None])[0]
        elif parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2]
        elif parsed_url.path.startswith('/v/'):
            return parsed_url.path.split('/')[2]

    return None

def fetch_video_metadata(youtube_client, video_id):
    """Fetch comprehensive metadata for a YouTube video."""
    try:
        # Get video details
        video_response = youtube_client.videos().list(
            part='snippet,contentDetails,statistics,player',
            id=video_id
        ).execute()

        if not video_response.get('items'):
            return {"error": "Video not found"}

        video_data = video_response['items'][0]

        # Get channel details
        channel_id = video_data['snippet']['channelId']
        channel_response = youtube_client.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()

        channel_data = channel_response['items'][0] if channel_response.get('items') else {}

        # Get comments (top 5)
        try:
            comments_response = youtube_client.commentThreads().list(
                part='snippet',
                videoId=video_id,
                order='relevance',
                maxResults=5
            ).execute()
            comments = [item['snippet']['topLevelComment']['snippet']['textDisplay']
                        for item in comments_response.get('items', [])]
        except Exception:
            comments = []

        # Parse duration
        duration_iso = video_data.get('contentDetails', {}).get('duration', 'PT0S')
        duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())

        # Compile metadata
        metadata = {
            'video_id': video_id,
            'title': video_data['snippet'].get('title', ''),
            'description': video_data['snippet'].get('description', ''),
            'channelTitle': video_data['snippet'].get('channelTitle', ''),
            'channelDescription': channel_data.get('snippet', {}).get('description', ''),
            'tags': video_data['snippet'].get('tags', []),
            'publishedAt': video_data['snippet'].get('publishedAt', ''),
            'duration': duration_seconds,
            'durationFormatted': format_duration(duration_seconds),
            'viewCount': int(video_data.get('statistics', {}).get('viewCount', 0)),
            'likeCount': int(video_data.get('statistics', {}).get('likeCount', 0)),
            'thumbnails': video_data['snippet'].get('thumbnails', {}),
            'embedHtml': video_data.get('player', {}).get('embedHtml', ''),
            'comments': comments,
            'channelSubscriberCount': int(channel_data.get('statistics', {}).get('subscriberCount', 0)),
            'channelVideoCount': int(channel_data.get('statistics', {}).get('videoCount', 0))
        }

        return metadata

    except Exception as e:
        return {"error": f"Error fetching video metadata: {str(e)}"}

def format_duration(seconds):
    """Format seconds into HH:MM:SS format."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def cache_data(data, cache_path):
    """Cache data to a JSON file."""
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Cached data to: {cache_path}")
    except Exception as e:
        print(f"Error caching data: {str(e)}")

def format_metadata_for_analysis(metadata):
    """
    Format metadata in a structured, readable way with explanatory sections
    instead of just dumping the JSON.
    """
    sections = []

    # Video basic information
    sections.append("## VIDEO INFORMATION")
    sections.append(f"Title: {metadata.get('title', 'N/A')}")
    sections.append(f"Channel: {metadata.get('channelTitle', 'N/A')}")
    sections.append(f"Duration: {metadata.get('durationFormatted', 'N/A')} ({metadata.get('duration', 0)} seconds)")
    sections.append(f"Published: {metadata.get('publishedAt', 'N/A')}")
    sections.append(f"Views: {metadata.get('viewCount', 0):,}")
    sections.append(f"Likes: {metadata.get('likeCount', 0):,}")

    # Tags
    tags = metadata.get('tags', [])
    if tags:
        sections.append("\n## TAGS")
        sections.append(", ".join(tags))

    # Description
    if metadata.get('description'):
        sections.append("\n## DESCRIPTION")
        # Truncate very long descriptions to first 3000 chars
        description = metadata.get('description', '')
        if len(description) > 3000:
            sections.append(f"{description[:3000]}...(truncated)")
        else:
            sections.append(description)

    # Channel information
    sections.append("\n## CHANNEL INFORMATION")
    sections.append(f"Channel: {metadata.get('channelTitle', 'N/A')}")
    sections.append(f"Subscribers: {metadata.get('channelSubscriberCount', 0):,}")
    sections.append(f"Total videos: {metadata.get('channelVideoCount', 0):,}")

    if metadata.get('channelDescription'):
        sections.append(f"Channel description: {metadata.get('channelDescription', 'N/A')}")

    # Comments
    comments = metadata.get('comments', [])
    if comments:
        sections.append("\n## TOP COMMENTS")
        for i, comment in enumerate(comments, 1):
            # Truncate very long comments
            if len(comment) > 300:
                comment = comment[:300] + "...(truncated)"
            sections.append(f"{i}. {comment}")

    return "\n".join(sections)

def openai_call_with_retry(oai_client, model, messages, response_format):
    """
    Helper function to make OpenAI API calls with retry for rate limits.
    """
    # Maximum number of retries
    max_retries = 5
    # Initial retry delay in seconds
    retry_delay = 2

    for retry_attempt in range(max_retries):
        try:
            response = oai_client.chat.completions.create(
                model=model,
                response_format=response_format,
                messages=messages
            )
            
            return json.loads(response.choices[0].message.content)

        except OpenAIError as e:
            # Check if it's a rate limit error
            error_str = str(e)
            if "rate_limit_exceeded" in error_str or "Rate limit reached" in error_str:
                # Try to extract suggested wait time if available
                wait_time_match = re.search(r'try again in (\d+\.\d+)s', error_str)

                if wait_time_match:
                    # Use the recommended wait time from the error message
                    wait_time = float(wait_time_match.group(1))
                    # Add a small buffer to ensure we're past the rate limit window
                    wait_time += 0.5
                else:
                    # Use exponential backoff with jitter
                    wait_time = retry_delay * (2 ** retry_attempt) + random.uniform(0, 1)

                print(
                    f"Rate limit reached. Waiting for {wait_time:.2f} seconds before retry ({retry_attempt + 1}/{max_retries})...")
                time.sleep(wait_time)

                # If this is the last retry attempt, raise the error
                if retry_attempt == max_retries - 1:
                    raise Exception(f"Error with OpenAI API after {max_retries} retries: {str(e)}")
            else:
                # If it's not a rate limit error, don't retry
                raise Exception(f"Error with OpenAI API: {str(e)}")

    # This should only happen if we exhaust all retries
    raise Exception("Failed after maximum retry attempts")

def classify_workout_category(oai_client, formatted_metadata):
    """
    Classify the workout video into categories (e.g., Yoga, HIIT, Weight workout)
    """
    try:
        messages = [
            {"role": "system", "content": CATEGORY_PROMPT},
            {"role": "user", "content": f"Analyze this workout video metadata and classify it according to the schema:\n\n{formatted_metadata}"}
        ]
        
        return openai_call_with_retry(oai_client, "gpt-4o", messages, CATEGORY_RESPONSE_FORMAT)
    
    except Exception as e:
        return {"error": f"Error classifying workout category: {str(e)}"}

def classify_workout_fitness_level(oai_client, formatted_metadata):
    """
    Classify the workout video by fitness level (technique difficulty, effort difficulty, required fitness level)
    """
    try:
        messages = [
            {"role": "system", "content": FITNESS_LEVEL_PROMPT},
            {"role": "user", "content": f"{FITNESS_LEVEL_USER_PROMPT}\n\n{formatted_metadata}"}
        ]
        
        return openai_call_with_retry(oai_client, "gpt-4o", messages, FITNESS_LEVEL_RESPONSE_FORMAT)
    
    except Exception as e:
        return {"error": f"Error classifying workout fitness level: {str(e)}"}

def classify_workout_vibe(oai_client, formatted_metadata):
    """
    Classify the workout video by vibe (e.g., Warrior Workout, Zen Flow)
    """
    try:
        messages = [
            {"role": "system", "content": VIBE_PROMPT},
            {"role": "user", "content": f"Analyze this workout video metadata and classify its vibe according to the schema:\n\n{formatted_metadata}"}
        ]
        
        return openai_call_with_retry(oai_client, "gpt-4o", messages, VIBE_RESPONSE_FORMAT)
    
    except Exception as e:
        return {"error": f"Error classifying workout vibe: {str(e)}"}

def classify_workout_spirit(oai_client, formatted_metadata):
    """
    Classify the workout video by spirit (e.g., High-Energy & Intense, Flow & Rhythm)
    """
    try:
        messages = [
            {"role": "system", "content": SPIRIT_PROMPT},
            {"role": "user", "content": f"Analyze this workout video metadata and classify its spirit according to the schema:\n\n{formatted_metadata}"}
        ]
        
        return openai_call_with_retry(oai_client, "gpt-4o", messages, SPIRIT_RESPONSE_FORMAT)
    
    except Exception as e:
        return {"error": f"Error classifying workout spirit: {str(e)}"}

def classify_workout_equipment(oai_client, formatted_metadata):
    """
    Identify the equipment needed for the workout (e.g., Mat, Dumbbells, Resistance bands)
    """
    try:
        messages = [
            {"role": "system", "content": EQUIPMENT_PROMPT},
            {"role": "user", "content": f"{EQUIPMENT_USER_PROMPT}\n\n{formatted_metadata}"}
        ]
        
        return openai_call_with_retry(oai_client, "gpt-4o", messages, EQUIPMENT_RESPONSE_FORMAT)
    
    except Exception as e:
        return {"error": f"Error identifying workout equipment: {str(e)}"}

# Usage example
if __name__ == "__main__":
    # Add force_refresh=True to ignore cache and create a new analysis
    result = analyze_youtube_workout("https://www.youtube.com/watch?v=zZD1H7XTTKc", force_refresh=True)
    print(json.dumps(result, indent=2))
