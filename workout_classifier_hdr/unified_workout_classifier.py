from openai import OpenAI, OpenAIError
import json
import os
import re
import time
import random
import io
import base64
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any
from PIL import Image
import requests
from io import BytesIO

# Import classifier modules
from category_classifier import CATEGORY_PROMPT, CATEGORY_USER_PROMPT, CATEGORY_RESPONSE_FORMAT
from fitness_level_classifier import FITNESS_LEVEL_PROMPT, FITNESS_LEVEL_USER_PROMPT, FITNESS_LEVEL_RESPONSE_FORMAT
from vibe_classifier import VIBE_PROMPT, VIBE_USER_PROMPT, VIBE_RESPONSE_FORMAT
from spirit_classifier import SPIRIT_PROMPT, SPIRIT_USER_PROMPT, SPIRIT_RESPONSE_FORMAT
from equipment_classifier import EQUIPMENT_PROMPT, EQUIPMENT_USER_PROMPT, EQUIPMENT_RESPONSE_FORMAT
from db_transformer import transform_to_db_structure

def analyse_hydrow_workout(workout_json, openai_api_key,
                          cache_dir='cache', force_refresh=False,
                          enable_category=True, enable_fitness_level=True,
                          enable_vibe=True, enable_spirit=True, enable_equipment=True):
    """
    Analyzes a YouTube workout video and classifies it according to enabled dimensions:
    1. Category (e.g., Yoga, HIIT, Weight workout)
    2. Fitness level (technique difficulty, effort difficulty, required fitness level)
    3. Vibe (e.g., Warrior Workout, Zen Flow)
    4. Spirit (e.g., High-Energy & Intense, Flow & Rhythm)
    5. Equipment (e.g., Mat, Dumbbells, Resistance bands)

    Args:
        schema (str): hydrow json
        openai_api_key (str, optional): OpenAI API key for accessing OpenAI API
        cache_dir (str): Directory to store cached data
        force_refresh (bool): Whether to force fresh analysis even if cached data exists
        enable_category (bool): Whether to classify workout by category
        enable_fitness_level (bool): Whether to classify workout by fitness level
        enable_vibe (bool): Whether to classify workout by vibe
        enable_spirit (bool): Whether to classify workout by spirit
        enable_equipment (bool): Whether to identify required equipment

    Returns:
        dict: Combined workout analysis across all enabled dimensions
    """
    # API keys - use provided keys or default values
    # Initialize clients
    try:
        oai_client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        return {"error": f"Failed to initialize API clients: {str(e)}"}

    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)

    # extract image and textual summary
    meta = extract_hydrow_meta_from_json(workout_json)

    # Initialize combined analysis
    video_id = workout_json.get("id")
    combined_analysis = {
        "video_id": video_id,
        "video_url":  workout_json.get("shareUrl"),
        "video_title": workout_json.get("name"),
        "duration": workout_json.get("duration")}

    # Define classifier configurations
    classifiers = [
        {
            "name": "category",
            "enabled": enable_category,
            "cache_key": f"{video_id}_category_analysis.json",
            "system_prompt": CATEGORY_PROMPT,
            "user_prompt": CATEGORY_USER_PROMPT,
            "response_format": CATEGORY_RESPONSE_FORMAT
        },
        {
            "name": "fitness_level",
            "enabled": enable_fitness_level,
            "cache_key": f"{video_id}_fitness_level_analysis.json",
            "system_prompt": FITNESS_LEVEL_PROMPT,
            "user_prompt": FITNESS_LEVEL_USER_PROMPT,
            "response_format": FITNESS_LEVEL_RESPONSE_FORMAT
        },
        {
            "name": "equipment",
            "enabled": enable_equipment,
            "cache_key": f"{video_id}_equipment_analysis.json",
            "system_prompt": EQUIPMENT_PROMPT,
            "user_prompt": EQUIPMENT_USER_PROMPT,
            "response_format": EQUIPMENT_RESPONSE_FORMAT
        },
        {
            "name": "spirit",
            "enabled": enable_spirit,
            "cache_key": f"{video_id}_spirit_analysis.json",
            "system_prompt": SPIRIT_PROMPT,
            "user_prompt": SPIRIT_USER_PROMPT,
            "response_format": SPIRIT_RESPONSE_FORMAT
        },
        {
            "name": "vibe",
            "enabled": enable_vibe,
            "cache_key": f"{video_id}_vibe_analysis.json",
            "system_prompt": VIBE_PROMPT,
            "user_prompt": VIBE_USER_PROMPT,
            "response_format": VIBE_RESPONSE_FORMAT
        }
    ]

    # Run each enabled classifier
    try:
        for classifier in classifiers:
            if not classifier["enabled"]:
                continue

            name = classifier["name"]
            cache_path = os.path.join(cache_dir, classifier["cache_key"])

            # Check for cached analysis
            if os.path.exists(cache_path) and not force_refresh:
                try:
                    with open(cache_path, 'r') as f:
                        analysis = json.load(f)
                    print(f"Loaded {name} analysis from cache: {cache_path}")
                except Exception as e:
                    print(f"Error loading cached {name} analysis: {str(e)}. Running fresh analysis.")
                    if not (classifier['name']=='fitness_level'):
                        analysis = run_classifier(
                            oai_client,
                            meta,
                            classifier["system_prompt"],
                            classifier["user_prompt"],
                            classifier["response_format"]
                        )
                        cache_data(analysis, cache_path)
                    else:
                        # ! now we proceed with fintess lvl, which is partially hardcoded
                        fitness_base_schema = prefill_fitness_schema(workout_json.get('workoutTypes')[0])
                        analysis = run_classifier(
                                oai_client,
                                meta,
                                classifier["system_prompt"],
                                classifier["user_prompt"],
                                classifier["response_format"]
                            )
                        analysis = enforce_prefilled_fields(analysis, fitness_base_schema)                  
                        cache_data(analysis, cache_path)
            else:
                if not (classifier['name']=='fitness_level'):
                    analysis = run_classifier(
                        oai_client,
                        meta,
                        classifier["system_prompt"],
                        classifier["user_prompt"],
                        classifier["response_format"]
                    )
                    cache_data(analysis, cache_path)
                else:
                    # ! now we proceed with fintess lvl, which is partially hardcoded
                    fitness_base_schema = prefill_fitness_schema(workout_json.get('workoutTypes')[0])
                    analysis = run_classifier(
                            oai_client,
                            meta,
                            classifier["system_prompt"],
                            classifier["user_prompt"],
                            classifier["response_format"]
                        )
                    analysis = enforce_prefilled_fields(analysis, fitness_base_schema) 
                    cache_data(analysis, cache_path)                 

            combined_analysis[name] = analysis
        return combined_analysis

    except Exception as e:
        return {"error": f"Failed to perform combined analysis: {str(e)}"}


# Other functions remain unchanged
def prefill_fitness_schema(workout_type: str) -> dict:
    """
    Pre-fills the fitness level response schema based on hardcoded rules for workoutType.

    - Breathe → Beginner
    - Sweat → Intermediate
    - Drive → Advanced
    - Distance → Do not classify fitness level (leave it empty, explanation only)
    - Other types → Suitable for all fitness levels (Beginner, Intermediate, Advanced) with score 1.0

    Returns a structured but partially filled schema.
    """
    workout_type = workout_type.lower().strip()
    schema = {
        "techniqueDifficulty": [],
        "techniqueDifficultyConfidence": None,
        "techniqueDifficultyExplanation": "",

        "effortDifficulty": [],
        "effortDifficultyConfidence": None,
        "effortDifficultyExplanation": "",

        "requiredFitnessLevel": [],
        "requiredFitnessLevelConfidence": None,
        "requiredFitnessLevelExplanation": ""
    }

    if workout_type == "distance":
        schema["requiredFitnessLevelExplanation"] = (
            "Workout type is 'Distance'. Platform guidance states these workouts are not classified for fitness level."
        )
        return schema

    level_map = {
        "breathe": "Beginner",
        "sweat": "Intermediate",
        "drive": "Advanced"
    }

    if workout_type in level_map:
        level = level_map[workout_type]
        schema["requiredFitnessLevel"] = [{"level": level, "score": 1.0}]
        schema["requiredFitnessLevelConfidence"] = 1.0
        schema["requiredFitnessLevelExplanation"] = (
            f"The workoutType is '{workout_type.capitalize()}', which is explicitly defined as a {level} workout "
            f"based on platform rules. No further inference needed."
        )
    else:
        # For all other workout types, mark as suitable for all levels
        schema["requiredFitnessLevel"] = [
            {"level": "Beginner", "score": 1.0},
            {"level": "Intermediate", "score": 1.0},
            {"level": "Advanced", "score": 1.0}
        ]
        schema["requiredFitnessLevelConfidence"] = 1.0
        schema["requiredFitnessLevelExplanation"] = (
            f"Workout type '{workout_type}' is not one of the specialized Hydrow categories "
            f"(Breathe, Sweat, Drive, Distance). It is treated as suitable for all fitness levels."
        )

    return schema

def enforce_prefilled_fields(gpt_result: dict, prefilled: dict, keys_to_override = ["requiredFitnessLevel","requiredFitnessLevelConfidence","requiredFitnessLevelExplanation"]) -> dict:
    """
    Replace selected fields in GPT output with your prefilled values.

    Args:
        gpt_result: Full GPT response (dictionary)
        prefilled: Your prefilled fields (dictionary)
        keys_to_override: List of keys to force from prefill

    Returns:
        A merged schema dictionary
    """
    final = gpt_result.copy()
    for key in keys_to_override:
        if key in prefilled:
            final[key] = prefilled[key]
    return final

def cache_data(data, cache_path):
    """Cache data to a JSON file."""
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Cached data to: {cache_path}")
    except Exception as e:
        print(f"Error caching data: {str(e)}")

def extract_hydrow_meta_from_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and format metadata as per specific rules.
    Returns a dictionary with 'text' (string summary) and 'image' (url).
    """

    def format_duration(seconds):
        if not seconds:
            return "Unknown duration"
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h} hours {m} minutes {s} seconds"

    def get_music_genre(data):
        genre = data.get("MusicGenre")
        if not genre:
            genre = "MusicGenre is not specified."
        backup = data.get("backupStations", [])
        station_names = [s.get("stationName") for s in backup if s.get("stationName")]
        if station_names:
            genre += f" | Radio Stations Played: {', '.join(station_names)}"
        return genre

    def get_playlist_summary(data):
        playlist = data.get("playlist", [])
        playlist_str = "\nPlaylist played:\n"
        for element in playlist:
            song = element.get("song","")
            artist = element.get("artist","")
            playlist_str+= f"Song '{song}' by the atrist '{artist}';\n"
        if not playlist:
            return ""
        return playlist_str

    def get_intensity(data):
        level = data.get("intensityLevel")
        return f"Workout intensity level: {level} out of 3" if level else ""

    def get_instructor(data):
        instructor_name = data.get("instructors", {}).get("stroke", {}).get("name")
        if instructor_name == "No Athlete": instructor_name = "Unknown"
        return instructor_name
    
    # Download poster image
    image_url = data.get("posterUri")

    # Format the final summary string
    summary = f"""
                Workout Name: {data.get("name", "N/A")}
                Workout Description: {data.get("description", "N/A")}
                Workout Type: {', '.join(data.get("workoutTypes", [])) or "N/A"}
                Category: {data.get("category", {}).get("name", "N/A")},{data.get("category", {}).get("categoryType", "N/A")},{data.get("category", {}).get("type", "N/A")}
                Duration: {format_duration(data.get("duration"))}
                Instructor: {get_instructor(data)}
                {get_intensity(data)}
                Music Genre: {get_music_genre(data)}
                {get_playlist_summary(data)}
              """.strip()

    return {"text": summary, "image": image_url}

def run_classifier(oai_client, meta, system_prompt, user_prompt, response_format):
    """
    Generic function to run a classifier through OpenAI API with optional image input.

    Args:
        oai_client: OpenAI client
        meta: dictionary with 'text' and optional 'image' (url)
        system_prompt: System prompt for the classifier
        user_prompt: User prompt for the classifier
        response_format: Expected response format

    Returns:
        dict: Classification results
    """
    try:
        # Base message (text-based)
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add image if present
        if meta.get("image"):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{user_prompt}\n\n{meta['text']}"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"{meta.get('image')}"
                        }
                    }
                ]
            })
        else:
            # Only text
            messages.append({
                "role": "user",
                "content": f"{user_prompt}\n\n{meta['text']}"
            })

        return openai_call_with_retry(oai_client, "gpt-4o", messages, response_format)

    except Exception as e:
        return {"error": f"Error with classifier: {str(e)}"}


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
