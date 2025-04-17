# main6_prompt.py

from urllib.parse import parse_qs, urlparse

def extract_video_id(youtube_url):
    """Extract YouTube video ID from URL."""
    if not youtube_url:
        return None
    try:
        parsed_url = urlparse(youtube_url)
        if "youtube.com" in parsed_url.netloc:
            if parsed_url.path == "/watch":
                return parse_qs(parsed_url.query).get("v", [None])[0]
            elif parsed_url.path.startswith("/embed/"):
                return parsed_url.path.split('/embed/')[1].split('?')[0]
            elif parsed_url.path.startswith("/shorts/"):
                return parsed_url.path.split('/shorts/')[1].split('?')[0]
            elif parsed_url.path.startswith("/v/"):
                return parsed_url.path.split('/v/')[1].split('?')[0]
        elif "youtu.be" in parsed_url.netloc:
            return parsed_url.path[1:]
        # Handle potential googleusercontent URLs if necessary, assuming structure like before
        elif "googleusercontent.com/youtube.com/" in youtube_url: # Adapt based on actual usercontent URL structure if needed
            # This part might need adjustment based on the exact format of googleusercontent URLs
             if "v=" in parsed_url.query:
                 return parse_qs(parsed_url.query).get("v", [None])[0]
             else: # Attempt to extract from path if not in query
                 parts = parsed_url.path.split('/')
                 potential_id = parts[-1].split('?')[0]
                 # Basic validation for a typical video ID format
                 if len(potential_id) >= 11 and all(c.isalnum() or c in ['_', '-'] for c in potential_id):
                     print(f"Extracted potential ID from googleusercontent path: {potential_id}")
                     return potential_id
                 return None # Fallback if no ID found

    except Exception as e:
        print(f"URL parse error: {e} for URL: {youtube_url}")
    return None

def create_classification_prompt_video():
    """
    Creates the system prompt for Vertex AI to extract workout features from a video.
    """
    # Feature definitions based on new 1.txt
    # [cite: 3-25, 31-84]
    prompt = """
Analyze the provided video segment (visuals and audio). Based *only* on the video content, generate a JSON object representing the workout's features. Each feature should be scaled from 0.0 to 1.0, where 0 means 'none or very little' of the quality and 1 means 'extremely pronounced'.

Ensure the output is ONLY a valid JSON object with the following keys and your estimated values between 0.0 and 1.0:

{
  "movement_speed": <value_between_0_and_1>, /* 0: Almost no movement, 1: Extremely fast */
  "static_holds_presence": <value_between_0_and_1>, /* 0: No static poses, 1: Constantly holding poses */
  "explosive_movements": <value_between_0_and_1>, /* 0: No sudden movements, 1: Frequent explosive actions */
  "use_of_external_weights": <value_between_0_and_1>, /* 0: No weights, 1: Heavy use of weights */
  "movements_to_rhythm_synchronization": <value_between_0_and_1>, /* 0: Not coordinated to music, 1: Fully synchronized */
  "outdoor_setting": <value_between_0_and_1>, /* 0: Fully indoor, 1: Fully outdoors */
  "group_performer": <value_between_0_and_1>, /* 0: Solo performer, 1: Large group */
  "instructor_speaking": <value_between_0_and_1>, /* 0: No instructor cues, 1: Constant guidance */
  "camera_stability": <value_between_0_and_1>, /* 0: Highly shaky camera, 1: Fully stable camera */
  "scene_brightness": <value_between_0_and_1>, /* 0: Very dim lighting, 1: Very bright lighting */
  "visible_breathing_pace": <value_between_0_and_1>, /* 0: No heavy breathing visible, 1: Obvious rapid breathing */
  "floor_based_exercises": <value_between_0_and_1>, /* 0: No floor exercises, 1: Predominantly floor-based */
  "jumping_presence": <value_between_0_and_1>, /* 0: No jumping, 1: Frequent jumps */
  "punching_kicking_presence": <value_between_0_and_1>, /* 0: No combat moves, 1: Frequent punches/kicks */
  "close_up_shots": <value_between_0_and_1>, /* 0: No close-ups, 1: Predominantly close-ups */
  "equipment_use": <value_between_0_and_1>, /* 0: No special equipment, 1: Heavy equipment use */
  "visible_sweat": <value_between_0_and_1>, /* 0: No visible sweat, 1: Heavy sweat */
  "music_loudness": <value_between_0_and_1>, /* 0: Quiet/no music, 1: Loud dominant music */
  "voice_loudness": <value_between_0_and_1>, /* 0: No voice, 1: Prominent spoken cues */
  "nature_sounds": <value_between_0_and_1>, /* 0: No natural sounds, 1: Dominant natural sounds */
  "audio_bpm": <value_between_0_and_1>, /* 0: Very slow tempo, 1: Extremely high BPM */
  "silence": <value_between_0_and_1>, /* 0: Continuous sound, 1: Nearly complete silence */
  "cardio": <value_between_0_and_1>, /* 0: No emphasis, 1: Maximum emphasis */
  "strength": <value_between_0_and_1>, /* 0: No emphasis, 1: Maximum emphasis */
  "flexibility": <value_between_0_and_1>, /* 0: No emphasis, 1: Maximum emphasis */
  "body_weight_usage": <value_between_0_and_1>, /* Emphasis on body weight exercises */
  "breathing_exercises": <value_between_0_and_1>, /* Emphasis on breathing exercises */
  "elliptical": <value_between_0_and_1>, /* Use of elliptical machine */
  "hiit": <value_between_0_and_1>, /* High-Intensity Interval Training structure */
  "indoor_biking": <value_between_0_and_1>, /* Use of stationary bike */
  "indoor_rowing": <value_between_0_and_1>, /* Use of rowing machine */
  "mat": <value_between_0_and_1>, /* Use of exercise mat */
  "meditation": <value_between_0_and_1>, /* Emphasis on meditation */
  "pilates": <value_between_0_and_1>, /* Pilates style movements */
  "running": <value_between_0_and_1>, /* Running or jogging present */
  "stretching": <value_between_0_and_1>, /* Emphasis on stretching */
  "treadmill": <value_between_0_and_1>, /* Use of treadmill */
  "walking": <value_between_0_and_1>, /* Walking present */
  "warm_up": <value_between_0_and_1>, /* Segment appears to be a warm-up */
  "weight_workout": <value_between_0_and_1>, /* Use of free weights or machines */
  "yoga": <value_between_0_and_1> /* Yoga style movements/poses */
}

Do not add any explanations, comments (except inside the JSON structure as shown), or introductory text outside the JSON object itself. The output must start with `{` and end with `}`.
"""
    return prompt

# Example usage (optional, for testing)
if __name__ == "__main__":
    # Test URL extraction
    test_urls = [
        "youtube.com/watch?v=dQw4w9WgXcQ",
        "youtu.be//dQw4w9WgXcQ",
        "youtube.com/embed//dQw4w9WgXcQ?si=example",
        "youtube.com/shorts//shorts/abcdefghijk",
        "youtube.com/v//v/dQw4w9WgXcQ?fs=1&hl=en_US",
        "https://www.youtube.com/watch?v=xzqexC11dEM/dQw4w9WgXcQ", # Assuming this format might exist
        "https://www.youtube.com/watch?v=xzqexC11dEM" # Example of missing ID
    ]
    for url in test_urls:
        print(f"URL: {url} -> ID: {extract_video_id(url)}")

    # Print the generated prompt
    # print("\nGenerated Prompt:")
    # print(create_classification_prompt_video())