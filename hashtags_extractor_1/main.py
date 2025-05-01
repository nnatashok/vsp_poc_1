import json
import os
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
from env_utils import load_api_keys

# Define the classifier prompts
HASHTAG_PROMPT = """You are a specialized AI fitness analyst. Your task is to analyze questionnaire data from a user and generate 1-10 personalized Instagram hashtags related to fitness that would interest this specific person.

ANALYSIS GUIDELINES:
1. Examine the user's workout preferences, goals, sports interests, and other fitness-related information.
2. Consider their fitness level, preferred workout types, and equipment they use.
3. Look for specific exercises, sports, or activities they enjoy.
4. Consider their workout goals (weight loss, strength, flexibility, etc.).
5. Generate hashtags that would help find motivational fitness content aligned with their interests.
6. For each hashtag, provide a score (0-1) indicating relevance to the user's interests.
7. Sort hashtags from highest to lowest score.
8. Provide a brief explanation of why these hashtags were selected, with specific evidence from the user data.
9. Only include English hashtags.
10. Ensure hashtags start with # and have no spaces.

Your response must follow the JSON schema provided.
"""

LOCATION_PROMPT = """You are a specialized AI location analyst. Your task is to analyze questionnaire data from a user and identify 0-3 real geographic locations that are personally relevant to this individual.

ANALYSIS GUIDELINES:
1. Identify actual geographic locations connected to the user's life history such as:
   - Cities/places mentioned in their college or education history
   - Locations where they grew up or have lived
   - Areas connected to their favorite sports teams
   - Places related to their hobbies or recreational activities
   - Locations of their favorite athletes or teams
2. Only include real, specific geographic locations (cities, towns, regions, etc.)
3. Do not suggest generic venue types like "gym" or "park" - only actual geographic places
4. If insufficient geographic information is available, return fewer suggestions or none
5. Each location should include a score (0-1) indicating confidence in the location's relevance to the user
6. Sort locations from highest to lowest score
7. Provide a brief explanation of why these locations were identified based on the data
8. Prioritize locations that might have fitness significance to the person

Your response must follow the JSON schema provided.
"""

HASHTAG_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "HashtagsAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "hashtags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string"
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
                    "maxItems": 10
                },
                "hashtagsExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of why specific hashtags were suggested"
                }
            },
            "required": ["hashtags", "hashtagsExplanation"],
            "additionalProperties": False
        }
    }
}

LOCATION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "LocationsAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "locations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string"
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["name", "score"]
                    },
                    "minItems": 0,
                    "maxItems": 3
                },
                "locationsExplanation": {
                    "type": "string",
                    "description": "Detailed explanation of why specific locations were suggested"
                }
            },
            "required": ["locations", "locationsExplanation"],
            "additionalProperties": False
        }
    }
}


def format_user_data_for_analysis(user_data: Dict[str, Any]) -> str:
    """Format user questionnaire data for analysis."""
    sections = []

    # Format each property in the user data
    for key, value in user_data.items():
        if value:
            # Convert lists to comma-separated strings
            if isinstance(value, list):
                formatted_value = ", ".join(value)
            else:
                formatted_value = str(value)

            # Add to sections
            sections.append(f"{key}: {formatted_value}")

    return "\n".join(sections)


def analyze_with_openai(
        client: OpenAI,
        user_data_formatted: str,
        system_prompt: str,
        response_format: Dict[str, Any]
) -> Dict[str, Any]:
    """Send data to OpenAI for analysis."""
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",
             "content": f"Analyze this user data and provide appropriate recommendations:\n\n{user_data_formatted}"}
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format=response_format
        )

        response_content = response.choices[0].message.content
        return json.loads(response_content)

    except Exception as e:
        print(f"Error with OpenAI analysis: {str(e)}")
        if "hashtags" in response_format.get("json_schema", {}).get("schema", {}).get("properties", {}):
            return {"hashtags": [], "hashtagsExplanation": f"Error analyzing data: {str(e)}"}
        else:
            return {"locations": [], "locationsExplanation": f"Error analyzing data: {str(e)}"}


def process_questionnaire_data(input_file: str, output_file: str, api_key: str) -> None:
    """Process questionnaire data and generate hashtags and locations."""
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Read input data
        with open(input_file, 'r') as f:
            lines = f.readlines()

        # Process each user's data
        results = []
        for i, line in enumerate(lines):
            try:
                print(f"Processing user {i + 1}/{len(lines)}...")
                user_data = json.loads(line.strip())

                # Format user data for analysis
                user_data_formatted = format_user_data_for_analysis(user_data)

                # Analyze for hashtags
                hashtags_analysis = analyze_with_openai(
                    client,
                    user_data_formatted,
                    HASHTAG_PROMPT,
                    HASHTAG_RESPONSE_FORMAT
                )

                # Analyze for locations
                locations_analysis = analyze_with_openai(
                    client,
                    user_data_formatted,
                    LOCATION_PROMPT,
                    LOCATION_RESPONSE_FORMAT
                )

                # Combine results with original data
                result = {
                    "instagramHashtags": hashtags_analysis.get("hashtags", []),
                    "instagramHashtagsExplanation": hashtags_analysis.get("hashtagsExplanation", ""),
                    "Locations": locations_analysis.get("locations", []),
                    "LocationsExplanation": locations_analysis.get("locationsExplanation", "")
                }

                results.append(result)

            except json.JSONDecodeError:
                print(f"Error parsing JSON for user {i + 1}")
                continue
            except Exception as e:
                print(f"Error processing user {i + 1}: {str(e)}")
                continue

        # Write results to output file
        with open(output_file, 'w') as f:
            for result in results:
                f.write(json.dumps(result) + '\n')

        print(f"Processing complete. Results saved to {output_file}")

    except Exception as e:
        print(f"Error in processing: {str(e)}")


def main():
    """Main function."""
    # Load API keys
    api_keys = load_api_keys()
    openai_api_key = api_keys.get('OPENAI_API_KEY')

    if not openai_api_key:
        print("Error: OpenAI API key not found in environment variables.")
        return

    # Define input and output files
    input_file = "onboarding_anwers.jsonl"
    output_file = "user_recommendations.jsonl"

    # Process data
    process_questionnaire_data(input_file, output_file, openai_api_key)


if __name__ == "__main__":
    main()