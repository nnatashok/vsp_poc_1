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
import pandas as pd

# Import classifier modules
from category_classifier import CATEGORY_PROMPT, CATEGORY_USER_PROMPT, CATEGORY_RESPONSE_FORMAT
from fitness_level_classifier import FITNESS_LEVEL_PROMPT, FITNESS_LEVEL_USER_PROMPT, FITNESS_LEVEL_RESPONSE_FORMAT
from vibe_classifier import VIBE_PROMPT, VIBE_USER_PROMPT, VIBE_RESPONSE_FORMAT
from spirit_classifier import SPIRIT_PROMPT, SPIRIT_USER_PROMPT, SPIRIT_RESPONSE_FORMAT
from equipment_classifier import EQUIPMENT_PROMPT, EQUIPMENT_USER_PROMPT, EQUIPMENT_RESPONSE_FORMAT
from db_transformer import transform_to_db_structure

def analyse_hydrow_workout(workout_json, openai_api_key,
                          cache_dir='cache', force_refresh=False, #!
                          enable_category=True, enable_fitness_level=True,
                          enable_vibe=True, enable_spirit=True, enable_equipment=True,
                          enable_image_in_meta=False):
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
    instructor_name = workout_json.get("instructors", {}).get("stroke", {}).get("name")
    if instructor_name == "No Athlete": instructor_name = "Unknown"
    combined_analysis = {
        "video_id": video_id,
        "video_url":  workout_json.get("shareUrl"),
        "video_title": workout_json.get("name"),
        "duration": workout_json.get("duration"),
        'video_metadata':workout_json,
        'video_metadata_cleaned': meta,
        "channel_title": instructor_name,
        "hydrow_category_name": workout_json.get("category", {}).get("name", "N/A"),
        "instructor_name": instructor_name,
        "duration_seconds": workout_json.get("duration"),
        "poster_uri": meta['image']
        }
    # with open("cats_map.txt",mode="a") as f:
    #     f.write(f'{workout_json.get("category", {}).get("id", "N/A")}: {workout_json.get("workoutTypes")[0].lower().strip()}')
    #     f.write("\n")

    if not enable_image_in_meta:
        del meta['image']

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
    # Flag to track if any classifier had an error
    has_errors = False
    review_comments = []

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
                    if not (classifier['name']=='fitness_level' or classifier['name']=='category') and \
                       not (classifier['name']=='vibe' and "Journey" in workout_json.get('category',{}).get('name',None)):
                        analysis = run_classifier(
                            oai_client,
                            meta,
                            classifier["system_prompt"],
                            classifier["user_prompt"],
                            classifier["response_format"]
                        )
                        cache_data(analysis, cache_path)
                    elif classifier['name']=='vibe' and "Journey" in workout_json.get('category',{}).get('name',None):
                        analysis = hardcoded_journey_vibe()
                        cache_data(analysis, cache_path)
                    elif classifier['name']=='category':
                        # ! we indroduce hardcoded mapping
                        workout_type = workout_json.get('workoutTypes')[0].lower().strip()
                        analysis = hardcoded_category_clf(workout_type=workout_type)
                        cache_data(analysis, cache_path)
                    else:
                        # ! now we proceed with fintess lvl, which is partially hardcoded
                        workout_type = workout_json.get('workoutTypes')[0].lower().strip()
                        fitness_base_schema = prefill_fitness_schema(workout_type, meta)
                        meta_f_lvl = meta
                        meta_f_lvl['text'] = meta_f_lvl['text'] + f"\nUser Fitness Level Requirements are {', '.join([e['level'] for e in fitness_base_schema.get('requiredFitnessLevel')])}"
                        analysis = run_classifier(
                                oai_client,
                                meta_f_lvl,
                                classifier["system_prompt"],
                                classifier["user_prompt"],
                                classifier["response_format"]
                            )
                        if len(fitness_base_schema.get("requiredFitnessLevel")) != 3:
                            analysis = enforce_prefilled_fields(analysis, fitness_base_schema) 
                        else:
                            analysis = enforce_prefilled_fields(analysis, 
                                                                fitness_base_schema,
                                                                keys_to_override = ["requiredFitnessLevel",
                                                                                    "requiredFitnessLevelConfidence",
                                                                                    "requiredFitnessLevelExplanation",
                                                                                    "techniqueDifficulty",
                                                                                    "techniqueDifficultyConfidence",
                                                                                    "techniqueDifficultyExplanation"]) 
                        cache_data(analysis, cache_path)
            else:
                if not (classifier['name']=='fitness_level' or classifier['name']=='category') and \
                   not (classifier['name']=='vibe' and "Journey" in workout_json.get('category',{}).get('name',None)):
                    analysis = run_classifier(
                        oai_client,
                        meta,
                        classifier["system_prompt"],
                        classifier["user_prompt"],
                        classifier["response_format"]
                    )
                    cache_data(analysis, cache_path)
                elif classifier['name']=='vibe' and "Journey" in workout_json.get('category',{}).get('name',None):
                        analysis = hardcoded_journey_vibe()
                        cache_data(analysis, cache_path) 
                elif classifier['name']=='category':
                    # ! we indroduce hardcoded mapping
                    workout_type = workout_json.get('workoutTypes')[0].lower().strip()
                    analysis = hardcoded_category_clf(workout_type=workout_type)
                    cache_data(analysis, cache_path)
                else:
                    # ! now we proceed with fintess lvl, which is partially hardcoded
                    workout_type = workout_json.get('workoutTypes')[0].lower().strip()
                    fitness_base_schema = prefill_fitness_schema(workout_type, meta)
                    meta_f_lvl = meta
                    meta_f_lvl['text'] = meta_f_lvl['text'] + f"\nUser Fitness Level Requirements are {', '.join([e['level'] for e in fitness_base_schema.get('requiredFitnessLevel')])}"
                    analysis = run_classifier(
                            oai_client,
                            meta_f_lvl,
                            classifier["system_prompt"],
                            classifier["user_prompt"],
                            classifier["response_format"]
                        )
                    if len(fitness_base_schema.get("requiredFitnessLevel")) != 3:
                        analysis = enforce_prefilled_fields(analysis, fitness_base_schema) 
                    else:
                        analysis = enforce_prefilled_fields(analysis, 
                                                            fitness_base_schema,
                                                            keys_to_override = ["requiredFitnessLevel",
                                                                                "requiredFitnessLevelConfidence",
                                                                                "requiredFitnessLevelExplanation",
                                                                                "techniqueDifficulty",
                                                                                "techniqueDifficultyConfidence",
                                                                                "techniqueDifficultyExplanation"]) 
                    cache_data(analysis, cache_path)                 
            # Check for errors in the classifier result
            if "error" in analysis:
                has_errors = True
                error_message = f"Error in {name} classifier: {analysis.get('error')}"
                review_comments.append(error_message)

                # Add review comment tag if present
                if "review_comment" in analysis:
                    if analysis["review_comment"] not in review_comments:
                        review_comments.append(analysis["review_comment"])
            
            combined_analysis[name] = analysis
        # Update reviewable status based on errors
        if has_errors:
            combined_analysis["reviewable"] = False
            combined_analysis["review_comment"] = "; ".join(review_comments)
        
        return combined_analysis

    except Exception as e:
        error_message = f"Failed to perform combined analysis: {str(e)}"
        return return_error_analysis(error_message, workout_json)

# Other functions remain unchanged
def prefill_fitness_schema(workout_type: str, full_meta:str) -> dict:
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
    elif "beginner" in full_meta['text'].lower().strip():
        schema["requiredFitnessLevel"] = [
            {"level": "Beginner", "score": 1.0},
            {"level": "Intermediate", "score": 1.0},
        ]
        schema["requiredFitnessLevelConfidence"] = 1.0
        schema["requiredFitnessLevelExplanation"] = (
            f"Workout type '{workout_type}' is not one of the specialized Hydrow categories "
            f"(Breathe, Sweat, Drive, Distance). And workout description mentiones it is meant for beginners."
        )
        
        # If workout is suitable for all fitness levels, then technique ia also can be adgusted to any level
        schema["techniqueDifficulty"] = [
            {"level": "Beginner", "score": 1.0},
            {"level": "Intermediate", "score": 1.0}
        ]
        schema["techniqueDifficultyConfidence"] = 1.0
        schema["techniqueDifficultyExplanation"] = (
            f"Since the workout is marked as suitable for all fitness levels (Beginner, Intermediate, Advanced), "
            f"the technique difficulty is considered adaptable. Movements can be scaled in complexity, and users are "
            f"expected to modify techniques based on their capability. Therefore, all difficulty levels from Beginner "
            f"to Expert are assigned equal suitability with a score of 1.0."
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
        
        # If workout is suitable for all fitness levels, then technique ia also can be adgusted to any level
        schema["techniqueDifficulty"] = [
            {"level": "Beginner", "score": 1.0},
            {"level": "Intermediate", "score": 1.0}
        ]
        schema["techniqueDifficultyConfidence"] = 1.0
        schema["techniqueDifficultyExplanation"] = (
            f"Since the workout is marked as suitable for all fitness levels (Beginner, Intermediate, Advanced), "
            f"the technique difficulty is considered adaptable. Movements can be scaled in complexity, and users are "
            f"expected to modify techniques based on their capability. Therefore, all difficulty levels from Beginner "
            f"to Expert are assigned equal suitability with a score of 1.0."
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

def extract_video_id(raw_json: str, idx:int) -> str:
    schema = json.loads(raw_json)
    video_id = schema.get("id")
    if not video_id:
        video_id = f"manual_{idx}"
        schema['id']=video_id
    return video_id
               
def format_duration(seconds):
        if not seconds:
            return "Unknown duration"
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h:02}:{m:02}:{s:02}"

def extract_hydrow_meta_from_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and format metadata as per specific rules.
    Returns a dictionary with 'text' (string summary) and 'image' (url).
    """


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
        playlist = data.get("playlist") if data.get("playlist") else []
        playlist_str = "\nPlaylist played:\n"
        for element in playlist:
            song = element.get("song","")
            artist = element.get("artist","")
            playlist_str+= f"Song '{song}' by the atrist '{artist}';\n"
        if not len(playlist):
            return ""
        return playlist_str

    def get_intensity(data):
        level = data.get("intensityLevel")
        return f"Workout intensity level: {level} out of 3" if level else ""

    def get_instructor(data):
        instructor_name = data.get("instructors", {}).get("stroke", {}).get("name")
        if instructor_name == "No Athlete": instructor_name = "Unknown"
        
        # ! adding lookup for instructors bio
        file_path = 'workout_classifier_hydrow/hydrow_athletes_bio.csv' #'hydrow_athletes_bio.csv'
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            # Normalize column 0 for case-insensitive comparison
            match = df[df.iloc[:, 0].str.strip().str.lower() == instructor_name.strip().lower()]
            if not match.empty:
                bio = match.iloc[0, 1]
            else:
                print(f"No bio found for instructor: {instructor_name}")
                bio = ""
            return instructor_name+":\n"+bio+"\n"

        else:
            print(f"File not found: {file_path}")
            return instructor_name

    
    # Download poster image
    image_url = data.get("posterUri")

    # Format the final summary string
    summary = f"""
                Workout Name: {data.get("name", "N/A")}\n
                Workout Description: {data.get("description", "N/A")}\n
                Workout Type: {', '.join(data.get("workoutTypes", [])) or "N/A"}\n
                Category: {data.get("category", {}).get("name", "N/A")},{data.get("category", {}).get("categoryType", "N/A")},{data.get("category", {}).get("type", "N/A")}\n
                Equipment:{data.get("equipment", {})}\n
                Duration: {format_duration(data.get("duration"))}\n
                Instructor: {get_instructor(data)}\n
                {get_intensity(data)}\n
                Music Genre: {get_music_genre(data)}\n
                {get_playlist_summary(data)}\n
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

def hardcoded_category_clf(workout_type):
    mapping = { 'cool down':'Cool-down',
                'strength':'Body weight',
                'stretching':'Stretching',
                'warm-up':'Warm-up',
                'drive':'Indoor rowing',
                'sweat':'Indoor rowing',
                'flow':'Yoga',
                'breathe':'Indoor rowing',
                'pilates':'Pilates',
                'restore':'Yoga',
                'align':'Yoga',
                'mobility':'Stretching',
                'circuit':'Calisthenics',
                'journey':'Indoor rowing'}
    try:
        name = mapping[workout_type]
    except:
        raise ValueError
    
    out ={  "categories": [{
                            "name": name,
                            "score": 1
                        }],
            "categoriesConfidence": 1,
            "categoriesExplanation": "The Category is assigned by predefined mapping."
            }
    return out

def hardcoded_journey_vibe():    
    out = {
        "vibes": [
            {"name": "The Nature Flow",
            "score": 1},
            {"name": "The Mindful Walk",
            "score": 1}
        ],
        "vibesConfidence": 1,
        "vibesExplanation": "Hardcoded vibes."
        }
    return out


def return_error_analysis(error_message, workout_json=None):
    return {
            "error": error_message,
            "reviewable": False,
            "review_comment": f"processing_error {error_message}",
            "video_id": workout_json.get("id")  if workout_json else None,
            "video_url": workout_json.get("shareUrl") if workout_json else None,
            "video_title": workout_json.get("name") if workout_json else None,
            "duration": format_duration(workout_json.get("duration")) if workout_json else None,
            'video_metadata': workout_json,
            'video_metadata_cleaned': extract_hydrow_meta_from_json(workout_json) if workout_json else None,
            "channel_title": workout_json.get("instructors", {}).get("stroke", {}).get("name") if workout_json else None
        }