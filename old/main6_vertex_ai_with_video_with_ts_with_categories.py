# main6_vertex_ai_with_video_with_ts_with_categories.py

import json
import os
import traceback
import math # Added for cosine similarity calculation
import isodate
from googleapiclient.discovery import build
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig, HarmCategory, HarmBlockThreshold

# Assume main6_prompt and main6_extract_utilities are in the same directory or accessible
# Use the updated prompt function that asks for the feature vector
from main6_prompt import create_classification_prompt_video
# Use the potentially updated extract_video_id if it handles googleusercontent better
from main6_extract_utilities import extract_video_id

# Configurations (Keep as before, ensure API keys are handled securely in production)
VERTEXAI_PROJECT_ID = 'norse-sector-250410'
VERTEXAI_LOCATION = 'us-central1'
# IMPORTANT: Handle API keys securely. Avoid hardcoding them directly in the script.
# Consider environment variables or a secrets management system.
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', 'AIzaSyCkpiTfTUvNVNmPcyw8ZO1NOn_0b_LV8RA') # Example using environment variable
VERTEXAI_MODEL_NAME = "gemini-2.5-pro-exp-03-25" # Confirm this model name is correct and supports video input

# Constants (Keep as before)
CACHE_DIR = 'cache_6'
MAX_DESC_LEN = 1500
MAX_COMMENT_LEN = 250
MAX_CHAN_DESC_LEN = 500
TARGET_SEGMENT_DURATION = 10 # Analyze central 10 seconds

# --- Vibe Vectors Definition ---
# Defined directly in the code based on new 1.txt
# In a real application, consider loading this from a separate config file (JSON, YAML)
WORKOUT_VIBE_VECTORS = {
    "the_warrior_workout": {
        "movement_speed": 0.9, "static_holds_presence": 0.1, "explosive_movements": 0.8,
        "use_of_external_weights": 0.3, "movements_to_rhythm_synchronization": 0.4,
        "outdoor_setting": 0.1, "group_performer": 0.5, "instructor_speaking": 0.7,
        "camera_stability": 0.5, "scene_brightness": 0.7, "visible_breathing_pace": 0.9,
        "floor_based_exercises": 0.4, "jumping_presence": 0.7, "punching_kicking_presence": 0.7,
        "close_up_shots": 0.6, "equipment_use": 0.4, "visible_sweat": 0.9,
        "music_loudness": 0.8, "voice_loudness": 0.6, "nature_sounds": 0.0,
        "audio_bpm": 0.8, "silence": 0.1, "cardio": 0.9, "flexibility": 0.4,
        "strength": 0.9, "body_weight_usage": 0.7, "breathing_exercises": 0.2,
        "elliptical": 0.0, "hiit": 0.9, "indoor_biking": 0.0, "indoor_rowing": 0.0,
        "mat": 0.3, "meditation": 0.0, "pilates": 0.0, "running": 0.7,
        "stretching": 0.4, "treadmill": 0.0, "walking": 0.2, "warm_up": 0.5,
        "weight_workout": 0.8, "yoga": 0.0
    },
    "the_firestarter": {
        "movement_speed": 0.95, "static_holds_presence": 0.05, "explosive_movements": 0.9,
        "use_of_external_weights": 0.4, "movements_to_rhythm_synchronization": 0.3,
        "outdoor_setting": 0.1, "group_performer": 0.4, "instructor_speaking": 0.6,
        "camera_stability": 0.5, "scene_brightness": 0.8, "visible_breathing_pace": 0.95,
        "floor_based_exercises": 0.3, "jumping_presence": 0.8, "punching_kicking_presence": 0.5,
        "close_up_shots": 0.5, "equipment_use": 0.4, "visible_sweat": 0.9,
        "music_loudness": 0.85, "voice_loudness": 0.5, "nature_sounds": 0.0,
        "audio_bpm": 0.9, "silence": 0.05, "cardio": 0.95, "flexibility": 0.3,
        "strength": 0.95, "body_weight_usage": 0.7, "breathing_exercises": 0.1,
        "elliptical": 0.0, "hiit": 1.0, "indoor_biking": 0.0, "indoor_rowing": 0.0,
        "mat": 0.2, "meditation": 0.0, "pilates": 0.0, "running": 0.8,
        "stretching": 0.3, "treadmill": 0.0, "walking": 0.1, "warm_up": 0.4,
        "weight_workout": 0.9, "yoga": 0.0
    },
    "the_nightclub_workout": {
         "movement_speed": 0.8, "static_holds_presence": 0.1, "explosive_movements": 0.5,
         "use_of_external_weights": 0.0, "movements_to_rhythm_synchronization": 1.0,
         "outdoor_setting": 0.0, "group_performer": 0.9, "instructor_speaking": 0.6,
         "camera_stability": 0.5, "scene_brightness": 0.4, "visible_breathing_pace": 0.6,
         "floor_based_exercises": 0.0, "jumping_presence": 0.4, "punching_kicking_presence": 0.0,
         "close_up_shots": 0.5, "equipment_use": 0.0, "visible_sweat": 0.6,
         "music_loudness": 1.0, "voice_loudness": 0.4, "nature_sounds": 0.0,
         "audio_bpm": 0.8, "silence": 0.0, "cardio": 0.8, "flexibility": 0.5,
         "strength": 0.3, "body_weight_usage": 0.6, "breathing_exercises": 0.2,
         "elliptical": 0.0, "hiit": 0.0, "indoor_biking": 0.0, "indoor_rowing": 0.0,
         "mat": 0.0, "meditation": 0.0, "pilates": 0.0, "running": 0.0,
         "stretching": 0.3, "treadmill": 0.0, "walking": 0.0, "warm_up": 0.2,
         "weight_workout": 0.0, "yoga": 0.0
     },
     "the_competitor": {
         "movement_speed": 0.85, "static_holds_presence": 0.2, "explosive_movements": 0.75,
         "use_of_external_weights": 0.5, "movements_to_rhythm_synchronization": 0.4,
         "outdoor_setting": 0.1, "group_performer": 0.6, "instructor_speaking": 0.6,
         "camera_stability": 0.6, "scene_brightness": 0.7, "visible_breathing_pace": 0.85,
         "floor_based_exercises": 0.4, "jumping_presence": 0.7, "punching_kicking_presence": 0.3,
         "close_up_shots": 0.6, "equipment_use": 0.5, "visible_sweat": 0.9,
         "music_loudness": 0.8, "voice_loudness": 0.6, "nature_sounds": 0.0,
         "audio_bpm": 0.8, "silence": 0.1, "cardio": 0.9, "flexibility": 0.4,
         "strength": 0.8, "body_weight_usage": 0.7, "breathing_exercises": 0.2,
         "elliptical": 0.0, "hiit": 0.8, "indoor_biking": 0.4, "indoor_rowing": 0.4,
         "mat": 0.3, "meditation": 0.0, "pilates": 0.2, "running": 0.7,
         "stretching": 0.4, "treadmill": 0.0, "walking": 0.2, "warm_up": 0.5,
         "weight_workout": 0.8, "yoga": 0.0
     },
     # ... Add ALL other 22 vibe vectors from new 1.txt here ...
     # Example for the last one:
     "the_nature_flow": {
         "movement_speed": 0.5, "static_holds_presence": 0.3, "explosive_movements": 0.2,
         "use_of_external_weights": 0.0, "movements_to_rhythm_synchronization": 0.8,
         "outdoor_setting": 0.9, "group_performer": 0.3, "instructor_speaking": 0.3,
         "camera_stability": 0.8, "scene_brightness": 0.7, "visible_breathing_pace": 0.5,
         "floor_based_exercises": 0.5, "jumping_presence": 0.1, "punching_kicking_presence": 0.0,
         "close_up_shots": 0.5, "equipment_use": 0.0, "visible_sweat": 0.5,
         "music_loudness": 0.7, "voice_loudness": 0.3, "nature_sounds": 0.9,
         "audio_bpm": 0.5, "silence": 0.3, "cardio": 0.5, "flexibility": 0.6,
         "strength": 0.4, "body_weight_usage": 0.5, "breathing_exercises": 0.8,
         "elliptical": 0.0, "hiit": 0.0, "indoor_biking": 0.0, "indoor_rowing": 0.0,
         "mat": 0.5, "meditation": 0.7, "pilates": 0.0, "running": 0.0,
         "stretching": 0.6, "treadmill": 0.0, "walking": 0.4, "warm_up": 0.3,
         "weight_workout": 0.0, "yoga": 0.7
     }
}
# Get the list of expected feature keys from one of the vectors
EXPECTED_FEATURES = list(WORKOUT_VIBE_VECTORS["the_warrior_workout"].keys())

# --- Cosine Similarity Function ---
def cosine_similarity(vec1, vec2, keys):
    """Calculates cosine similarity between two vectors (dicts) using specified keys."""
    # Use only the common keys that are expected features
    valid_keys = [k for k in keys if k in vec1 and k in vec2]
    if not valid_keys:
        print("Warning: No common keys found for similarity calculation.")
        return 0.0

    dot_product = sum(float(vec1[key]) * float(vec2[key]) for key in valid_keys)

    norm_vec1 = math.sqrt(sum(float(vec1[key])**2 for key in valid_keys))
    norm_vec2 = math.sqrt(sum(float(vec2[key])**2 for key in valid_keys))

    if norm_vec1 == 0 or norm_vec2 == 0:
        # Handle cases where one or both vectors are all zeros for the common keys
        return 0.0 if norm_vec1 == norm_vec2 else 0.0 # Or consider similarity undefined

    similarity = dot_product / (norm_vec1 * norm_vec2)
    # Clamp similarity to [0, 1] range, as features are non-negative.
    # Cosine similarity can be [-1, 1], but with 0-1 features, it should be [0, 1].
    # Small floating point errors might push it slightly outside.
    return max(0.0, min(1.0, similarity))


# Initialize services (Keep as before)
try:
    vertexai.init(project=VERTEXAI_PROJECT_ID, location=VERTEXAI_LOCATION)
    vertex_model = GenerativeModel(VERTEXAI_MODEL_NAME)
    youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
except Exception as e:
    print(f"Error initializing services: {e}")
    # Handle initialization failure appropriately (e.g., exit or raise)
    raise

# --- Core Functions (Modified) ---

def analyze_youtube_workout(youtube_url, cache_dir=CACHE_DIR, force_refresh=False):
    """
    Analyze a YouTube workout video: fetch metadata, extract features via Vertex AI,
    determine the closest vibe using cosine similarity, and cache results.
    Focuses on the central TARGET_SEGMENT_DURATION seconds.
    """
    video_id = extract_video_id(youtube_url)
    if not video_id:
        print(f"Could not extract video ID from URL: {youtube_url}")
        return {"error": "Invalid YouTube URL or failed to extract video ID."}
    print(f"Analyzing Video ID: {video_id}")
    os.makedirs(cache_dir, exist_ok=True)

    # Use a more descriptive cache filename including vibe logic
    analysis_cache_file = os.path.join(cache_dir, f"{video_id}_feature_vibe_analysis_center{TARGET_SEGMENT_DURATION}s.json")

    if os.path.exists(analysis_cache_file) and not force_refresh:
        try:
            with open(analysis_cache_file, 'r', encoding='utf-8') as f:
                print(f"Loading analysis from cache: {analysis_cache_file}")
                return json.load(f)
        except Exception as e:
            print(f"Cache load error for {analysis_cache_file}: {e}. Re-analyzing.")

    # --- Metadata Fetching (Keep as before, with error handling) ---
    metadata_cache = os.path.join(cache_dir, f"{video_id}_metadata.json")
    metadata = None
    if os.path.exists(metadata_cache) and not force_refresh:
        try:
            with open(metadata_cache, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"Loaded metadata from cache for {video_id}.")
        except Exception as e:
            print(f"Metadata cache load error for {video_id}: {e}. Fetching again.")
            metadata = None # Ensure metadata is fetched if cache fails

    if metadata is None:
        try:
            metadata = fetch_video_metadata(youtube_client, video_id)
            if "error" in metadata:
                print(f"Error fetching metadata for {video_id}: {metadata['error']}")
                return metadata # Return error if metadata fetch fails
            cache_data(metadata, metadata_cache)
        except Exception as e:
            print(f"Unhandled exception during metadata fetch for {video_id}: {e}")
            print(traceback.format_exc())
            return {"error": f"Failed to fetch metadata: {e}"}

    # --- Feature Extraction and Vibe Analysis ---
    print(f"Starting Vertex AI feature extraction for {video_id}...")
    try:
        # Pass the metadata and URL to the classification function
        feature_analysis_result = classify_workout_features_and_vibe(vertex_model, metadata, youtube_url)

        # Check if the analysis function returned an error
        if "error" in feature_analysis_result:
             print(f"Feature analysis failed for {video_id}: {feature_analysis_result['error']}")
             # Optionally return the metadata along with the error
             return {"metadata": metadata, **feature_analysis_result}

        # Combine metadata with the analysis results (features + vibe)
        final_result = {
            "metadata": metadata,
            "analysis": feature_analysis_result # Contains extracted_features and determined_vibe
        }
        cache_data(final_result, analysis_cache_file)
        print(f"Analysis complete for {video_id}. Vibe: {feature_analysis_result.get('determined_vibe', {}).get('name', 'N/A')}")
        return final_result

    except Exception as e:
        print(f"Unhandled exception during analysis pipeline for {video_id}: {e}")
        print(traceback.format_exc())
        # Return metadata along with the error if analysis fails mid-way
        return {"metadata": metadata, "error": f"Analysis pipeline failed: {e}"}


def classify_workout_features_and_vibe(model, metadata, youtube_url):
    """
    Classifies workout features using Vertex AI, then determines the closest vibe.
    """
    sys_prompt = create_classification_prompt_video() # Use the updated prompt
    formatted_metadata = format_metadata_for_analysis(metadata) # Still useful context
    total_duration = metadata.get('duration', 0)
    video_part = None

    # --- Video Segment Logic (Keep as before) ---
    if total_duration > 0:
        # Calculate start/end for the target segment duration around the midpoint
        half_seg = TARGET_SEGMENT_DURATION / 2.0
        midpoint = total_duration / 2.0
        start = max(0.0, midpoint - half_seg)
        end = min(total_duration, midpoint + half_seg)

        # Adjust if segment duration is less than target (for short videos or near ends)
        if end - start < TARGET_SEGMENT_DURATION and total_duration >= TARGET_SEGMENT_DURATION:
            if start == 0.0: # Near beginning
                end = min(total_duration, TARGET_SEGMENT_DURATION)
            elif end == total_duration: # Near end
                start = max(0.0, total_duration - TARGET_SEGMENT_DURATION)

        # Handle edge case where start might equal end for very short videos
        if start >= end:
             # Use a tiny segment from the start if calculation fails
             start, end = 0.0, min(total_duration, 0.1)

        # Create segment metadata for Vertex AI
        start_int, end_int = int(start), int(end)
        start_nanos = int((start - start_int) * 1e9)
        end_nanos = int((end - end_int) * 1e9)
        seg_metadata = {"start_offset": {"seconds": start_int, "nanos": start_nanos},
                        "end_offset": {"seconds": end_int, "nanos": end_nanos}}
        print(f"Analyzing segment: {start:.1f}s to {end:.1f}s")
        try:
            # Attempt to create Part with segment metadata
            video_part = Part.from_uri(uri=youtube_url, mime_type="video/youtube", video_metadata=seg_metadata)
        except TypeError: # Handle if model/SDK version doesn't support video_metadata
            print("Warning: Video segmentation metadata not supported by SDK/model version. Analyzing full video.")
            video_part = Part.from_uri(uri=youtube_url, mime_type="video/youtube")
        except Exception as e:
            print(f"Error creating video part with segments: {e}. Analyzing full video.")
            video_part = Part.from_uri(uri=youtube_url, mime_type="video/youtube")

    else:
        print("Video duration unknown or zero; analyzing full video.")
        video_part = Part.from_uri(uri=youtube_url, mime_type="video/youtube")

    # --- Vertex AI Call (Keep structure, adjust expectations) ---
    # Combine prompt parts: System Prompt, Formatted Metadata (Context), Video Part
    prompt_parts = [
        Part.from_text(sys_prompt + "\n\n--- Video Context ---\n" + formatted_metadata),
        video_part
    ]
    gen_config = GenerationConfig(
        temperature=0.2, # Low temp for deterministic feature extraction
        max_output_tokens=8192, # Ensure enough tokens for the JSON
        response_mime_type="application/json", # Expect JSON directly
    )
    safety = { # Keep safety settings
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }
    print("Sending request to Vertex AI for feature extraction...")
    try:
        response = model.generate_content(prompt_parts, generation_config=gen_config, safety_settings=safety, stream=False)

        # --- Process Response: Extract Features & Calculate Vibe ---
        try:
            # Directly access the text part assuming JSON response
            extracted_features = json.loads(response.text)
            if not isinstance(extracted_features, dict):
                raise json.JSONDecodeError("LLM response is not a JSON object.", response.text, 0)

            # Validate extracted features (optional but recommended)
            # Check if all expected keys are present, values are numbers between 0-1, etc.
            # For now, we assume the LLM follows the prompt correctly.
            print("Successfully extracted features from LLM.")

            # Calculate similarities and find the best vibe
            best_vibe = None
            max_similarity = -1.0 # Initialize with value lower than any possible similarity

            for vibe_name, vibe_vector in WORKOUT_VIBE_VECTORS.items():
                similarity = cosine_similarity(extracted_features, vibe_vector, EXPECTED_FEATURES)
                # print(f"  Similarity with '{vibe_name}': {similarity:.4f}") # Optional: print all similarities
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_vibe = vibe_name

            determined_vibe_info = {
                "name": best_vibe,
                "similarity_score": round(max_similarity, 4) # Store score
            }
            print(f"Determined vibe: '{best_vibe}' with similarity {max_similarity:.4f}")

            # Return both extracted features and the determined vibe
            return {
                "extracted_features": extracted_features,
                "determined_vibe": determined_vibe_info
            }

        except json.JSONDecodeError as je:
            error_msg = f"Failed to decode JSON response from LLM: {je}. Response text (start): '{response.text[:200]}...'"
            print(error_msg)
            return {"error": error_msg, "raw_response": response.text}
        except Exception as e_process:
            error_msg = f"Error processing LLM response or calculating vibe: {e_process}"
            print(error_msg)
            print(traceback.format_exc())
            # Include raw features if extraction worked but vibe calculation failed
            raw_features = {}
            try:
                 raw_features = json.loads(response.text)
            except:
                 pass # Ignore if parsing failed earlier
            return {"error": error_msg, "extracted_features_raw": raw_features}

    except Exception as e_vertex:
        error_msg = f"Vertex AI API call failed: {e_vertex}"
        print(error_msg)
        print(traceback.format_exc())
        # Attempt to include any partial response info if available (e.g., from specific Vertex AI exceptions)
        return {"error": error_msg}


# --- Helper Functions (Mostly from main6_extract_utilities.py, keep relevant ones) ---
# Ensure these are defined correctly, potentially importing from main6_extract_utilities if preferred

def fetch_video_metadata(youtube_client, video_id):
    """Fetch metadata for the video (Simplified version from original)."""
    print(f"Fetching metadata for {video_id}")
    try:
        video_response = youtube_client.videos().list(
            part='snippet,contentDetails,statistics,player', id=video_id
        ).execute()

        if not video_response.get('items'):
            return {"error": f"Video not found (ID: {video_id})"}
        video_data = video_response['items'][0]

        # --- Extract relevant fields ---
        snippet = video_data.get('snippet', {})
        content_details = video_data.get('contentDetails', {})
        statistics = video_data.get('statistics', {})
        player = video_data.get('player', {})

        # Fetch Channel Info (Optional but useful context)
        channel_id = snippet.get('channelId')
        channel_snippet, channel_stats = {}, {}
        if channel_id:
            try:
                channel_response = youtube_client.channels().list(
                    part='snippet,statistics', id=channel_id
                ).execute()
                if channel_response.get('items'):
                    channel_data = channel_response['items'][0]
                    channel_snippet = channel_data.get('snippet', {})
                    channel_stats = channel_data.get('statistics', {})
            except Exception as e_chan:
                 print(f"Warning: Could not fetch channel details for {channel_id}: {e_chan}")

        # Fetch Comments (Optional but useful context)
        comments = []
        try:
            comments_response = youtube_client.commentThreads().list(
                part='snippet', videoId=video_id, order='relevance',
                textFormat='plainText', maxResults=5 # Limit results
            ).execute()
            comments = [item['snippet']['topLevelComment']['snippet']['textDisplay']
                        for item in comments_response.get('items', [])]
        except Exception as e_com:
            # Handle potential errors like comments disabled
            print(f"Warning: Could not fetch comments for {video_id}: {e_com}")
            comments = ["Error fetching comments."] if "disabled" in str(e_com).lower() else []


        # Parse Duration
        duration_seconds = 0
        duration_iso = content_details.get('duration', 'PT0S')
        try:
            duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
        except Exception as e_dur:
            print(f"Warning: Could not parse duration '{duration_iso}': {e_dur}")


        # --- Construct Metadata Dictionary ---
        metadata = {
            'video_id': video_id,
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''), # Keep full desc for potential later use
            'channelTitle': snippet.get('channelTitle', ''),
            'channelDescription': channel_snippet.get('description', ''), # Keep full desc
            'tags': snippet.get('tags', []),
            'publishedAt': snippet.get('publishedAt', ''),
            'duration': duration_seconds,
            'durationFormatted': format_duration(duration_seconds), # Use helper
            'viewCount': int(statistics.get('viewCount', 0)),
            # Handle missing like/comment counts gracefully
            'likeCount': int(statistics['likeCount']) if 'likeCount' in statistics else None,
            'commentCount': int(statistics['commentCount']) if 'commentCount' in statistics else None,
            'thumbnails': snippet.get('thumbnails', {}), # Keep thumbnail info
            'embedHtml': player.get('embedHtml', ''), # Keep embed info
            'topComments': comments, # Keep fetched comments
            # Handle missing subscriber counts gracefully
            'channelSubscriberCount': int(channel_stats['subscriberCount']) if channel_stats.get('subscriberCount') and not channel_stats.get('hiddenSubscriberCount', False) else None,
            'channelVideoCount': int(channel_stats.get('videoCount', 0))
        }
        print(f"Metadata fetched successfully for {video_id}.")
        return metadata

    except Exception as e:
        print(f"Error during metadata fetch API call for {video_id}: {e}")
        print(traceback.format_exc())
        return {"error": f"API call failed during metadata fetch: {e}"}

def format_duration(seconds):
    """Convert seconds to HH:MM:SS or MM:SS."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "Invalid Duration"
    seconds = int(round(seconds)) # Round to nearest second
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def cache_data(data, cache_path):
    """Cache data to a JSON file."""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data successfully cached to {cache_path}")
    except Exception as e:
        print(f"Error caching data to {cache_path}: {e}")
        # Decide if this should raise an error or just warn

def format_metadata_for_analysis(metadata):
    """Format metadata for the LLM prompt context (Simplified)."""
    parts = []
    parts.append(f"- Title: {metadata.get('title', 'N/A')}")
    parts.append(f"- Channel: {metadata.get('channelTitle', 'N/A')}")
    parts.append(f"- Duration: {metadata.get('durationFormatted', 'N/A')}")
    # Keep description concise for prompt
    desc = metadata.get('description', '')
    parts.append(f"- Description (truncated): {desc[:MAX_DESC_LEN]}{'...' if len(desc) > MAX_DESC_LEN else ''}")
    if metadata.get('tags'):
         parts.append(f"- Tags: {', '.join(metadata['tags'][:10])}{'...' if len(metadata['tags']) > 10 else ''}") # Limit tags in prompt

    # Add top comments if available
    comments = metadata.get('topComments', [])
    if comments and comments != ["Error fetching comments."]:
        parts.append("- Top Comments:")
        for i, comment in enumerate(comments[:3], 1): # Limit comments in prompt
            cmt = str(comment)
            parts.append(f"  {i}. {cmt[:MAX_COMMENT_LEN]}{'...' if len(cmt)>MAX_COMMENT_LEN else ''}")

    return "\n".join(parts)


# --- Main Execution Block ---
if __name__ == "__main__":
    # Use a test URL likely to contain a workout
    # Replace with a real YouTube URL for actual testing
    test_url = "https://www.youtube.com/watch?v=xzqexC11dEM" # Example - replace with a real workout video URL for testing

    print(f"\n--- Analyzing YouTube URL: {test_url} ---")
    # Set force_refresh=True to ignore cache for this run
    analysis_result = analyze_youtube_workout(test_url, force_refresh=False) # Set to True to ignore cache

    print("\n--- Analysis Result ---")
    print(json.dumps(analysis_result, indent=2, ensure_ascii=False))

    # Example of accessing specific parts of the result
    if "error" in analysis_result:
        print(f"\nAnalysis failed: {analysis_result['error']}")
    elif "analysis" in analysis_result and "determined_vibe" in analysis_result["analysis"]:
        vibe_name = analysis_result["analysis"]["determined_vibe"].get("name")
        vibe_score = analysis_result["analysis"]["determined_vibe"].get("similarity_score")
        print(f"\nDetermined Vibe: {vibe_name} (Score: {vibe_score})")
        # print("\nExtracted Features:")
        # print(json.dumps(analysis_result["analysis"].get("extracted_features"), indent=2))
    else:
         print("\nAnalysis completed, but vibe information might be missing in the result structure.")