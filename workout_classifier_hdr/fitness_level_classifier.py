# Classification prompt for fitness level analysis
FITNESS_LEVEL_PROMPT = """You are a specialized AI fitness analyst. Your task is to analyze workout video metadata and classify the workout based on three key metrics:

1. Technique Difficulty: How complex and challenging the exercises are to perform correctly
2. Effort Difficulty: How physically demanding the workout is based on duration and energy expenditure

The platform you are analyzing focuses heavily on rowing-based workouts.

CLASSIFICATION METRICS DESCRIPTIONS:

1. TECHNIQUE DIFFICULTY:
   This measures how complex the movements are to execute with proper form.

   - Beginner: Simple, straightforward movements with minimal coordination required
   - Intermediate: Moderately complex movements requiring some coordination
   - Advanced: Complex movements requiring significant coordination and body awareness
   - Expert: Highly technical movements requiring extensive practice and specialized skills

2. EFFORT DIFFICULTY:
   This measures how physically demanding the workout is, based on:

   - Duration
   - Energy expenditure per movement
   - Rest period frequency and length
   - Volume and intensity of work (sets/reps, rhythm, etc.)

   Levels:

   - Light: Suitable for recovery or warm-ups
   - Moderate: Requires steady effort, manageable intensity
   - Challenging: Requires sustained focus and high energy
   - Extreme: Pushes physical limits, often competitive or elite-level

ANALYSIS GUIDELINES:

1. Always examine workoutType, title, description, intensity cues, and rhythm data.
2. Prioritize Hydrow-specific rules where applicable (e.g., Drive = Advanced).
3. For other workouts, use technique and effort difficulty to determine fitness level.
4. Assign scores (0–1) to applicable levels. Do not include levels with a score of 0.
5. Provide a clear explanation justifying your scores for each metric with references to metadata.

---

EXPLANATION GUIDELINES:

- Cite keywords like "challenging", "intense", "beginner-friendly", etc.
- Justify how movement complexity and intensity lead to a particular fitness level
- Mention if Hydrow's workoutType rule overrides typical classification
- If a Distance workout is marked not for classification, explain that too
- Be concise but detailed (100–200 words per metric)

---

SCORE VALUES EXPLANATION:

- 0.8–1.0: Extremely strong alignment with this level
- 0.6–0.79: Strong alignment
- 0.4–0.59: Moderate alignment
- 0.2–0.39: Weak or partial fit
- 0–0.19: Minimal alignment

CONFIDENCE LEVELS EXPLANATION:

- 0.8–1.0: Very high confidence – Strong metadata indicators
- 0.6–0.79: High confidence – Clear contextual signals
- 0.4–0.59: Moderate confidence – Inferred from some evidence
- 0.2–0.39: Low confidence – Weak signals or partial data
- 0–0.19: Very low confidence – Highly speculative

Analyze the workout video metadata provided and classify its technique difficulty, effort difficulty, and required fitness level according to the schema.
"""


# User prompt for fitness level classification
FITNESS_LEVEL_USER_PROMPT = "Analyze this workout video metadata and classify its technique difficulty, effort difficulty, and required fitness level according to the schema:"

# JSON schema for fitness level classification
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
                    "maxItems": 4 #? you have 4 difficulties together, so you allow to return them all?
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
                    "maxItems": 4 #? same here ^^^^
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
                    "maxItems": 4 #? same here ^^^^
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