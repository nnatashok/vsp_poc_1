# Classification prompt for fitness level analysis
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