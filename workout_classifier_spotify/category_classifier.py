# Classification prompt for category analysis
CATEGORY_PROMPT = """You are a specialized AI fitness analyst. 
Your task is to analyze Spotify playlist metadata and classify the playlist into specific categories. 
The playlists you are analyzing are designed exclusively for running (treadmill or outdoors) and walking. 
You must evaluate how the musical content supports categories below.

WORKOUT CATEGORY DESCRIPTIONS:
- Running: Outdoor or indoor running workouts not limited to treadmill use.
- Treadmill: Running or walking workouts performed on a treadmill.
- Walking: Moderate to brisk walking workouts, often for beginners or recovery.

ANALYSIS GUIDELINES:
1. Examine the title, description, and tags carefully for explicit workout information.
2. Look for indicators of intensity, duration, and exercise types.
3. Consider the channel's focus and typical content style.
4. User comments may provide additional clues about the workout experience.
5. When confidence is low for a category, mark it appropriately.
6. For each workout, identify 1-2 most suitable categories that match the workout, with a score value (0-1) for each.
7. If no category clearly applies, use the "Other" category.
8. Provide a detailed explanation of why you assigned specific categories, citing evidence from the metadata.

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

# User prompt for category classification
CATEGORY_USER_PROMPT = "Analyze this workout video metadata and classify it according to the schema:"

# JSON schema for category classification
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
                                    "Running", "Treadmill", "Walking"]
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
                    "maxItems": 3 #? why three?
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