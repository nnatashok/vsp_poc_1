import base64
import json
import os
import requests
from urllib.parse import urlparse, parse_qs
import isodate  # For parsing ISO 8601 duration format
from googleapiclient.discovery import build
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig, HarmCategory, HarmBlockThreshold

# --- Configuration ---
# Replace with your actual Google Cloud project ID and region
VERTEXAI_PROJECT_ID = 'norse-sector-250410'
VERTEXAI_LOCATION = 'us-central1' # e.g., 'us-central1'
# Replace with your actual YouTube API Key
YOUTUBE_API_KEY = 'AIzaSyCkpiTfTUvNVNmPcyw8ZO1NOn_0b_LV8RA'
# Specify the Gemini model to use (ensure it supports multimodal input)
VERTEXAI_MODEL_NAME = "gemini-1.5-pro-preview-0409"
# --- End Configuration ---

# Global variable for the initialized model (optional, could also be passed around)
vertex_model = None

def initialize_vertexai():
    """Initializes Vertex AI and the Generative Model."""
    global vertex_model
    if vertex_model is None:
        try:
            print(f"Initializing Vertex AI for project '{VERTEXAI_PROJECT_ID}' in location '{VERTEXAI_LOCATION}'...")
            vertexai.init(project=VERTEXAI_PROJECT_ID, location=VERTEXAI_LOCATION)
            vertex_model = GenerativeModel(VERTEXAI_MODEL_NAME)
            print(f"Vertex AI initialized successfully. Using model: {VERTEXAI_MODEL_NAME}")
        except Exception as e:
            print(f"FATAL: Failed to initialize Vertex AI: {str(e)}")
            raise  # Re-raise the exception to stop execution if initialization fails

def analyze_youtube_workout(youtube_url, cache_dir='cache_3', force_refresh=False):
    """
    Analyzes a YouTube workout video using Vertex AI Gemini and categorizes it.

    Args:
        youtube_url (str): URL of the YouTube workout video
        cache_dir (str): Directory to store cached data
        force_refresh (bool): Whether to force fresh analysis even if cached data exists

    Returns:
        dict: Categorized workout information or an error dictionary.
    """
    # Initialize API clients (Vertex AI is initialized globally or on first call)
    try:
        initialize_vertexai() # Ensure Vertex AI is initialized
        youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        return {"error": f"Failed to initialize API clients: {str(e)}"}

    # Extract video ID
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return {"error": "Invalid YouTube URL. Could not extract video ID."}

    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)

    # Check for cached analysis results
    analysis_cache_path = os.path.join(cache_dir, f"{video_id}_vertex_analysis.json") # Changed cache filename
    if os.path.exists(analysis_cache_path) and not force_refresh:
        try:
            with open(analysis_cache_path, 'r') as f:
                analysis = json.load(f)
            print(f"Loaded analysis from cache: {analysis_cache_path}")
            return analysis
        except Exception as e:
            print(f"Error loading cached analysis: {str(e)}. Proceeding with fresh analysis.")

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
            if "error" in metadata: return metadata # Propagate error
            cache_data(metadata, metadata_cache_path)
    else:
        metadata = fetch_video_metadata(youtube_client, video_id)
        if "error" in metadata: return metadata # Propagate error
        cache_data(metadata, metadata_cache_path)

    # Get thumbnail image URL from metadata (prefer high resolution)
    thumbnail_url = metadata.get('thumbnails', {}).get('maxres', metadata.get('thumbnails', {}).get('high', {})).get('url')
    thumbnail_base64 = None
    if thumbnail_url:
        thumbnail_base64 = get_thumbnail_base64(thumbnail_url, cache_dir, video_id, force_refresh)
        if thumbnail_base64 is None:
             print("Warning: Could not obtain thumbnail image.")
             # Decide if you want to proceed without the image or return an error


    # Now send the metadata (and image if available) to Vertex AI for workout classification
    try:
        if not vertex_model:
             return {"error": "Vertex AI model not initialized."}
        print("Starting workout classification with Vertex AI...")
        analysis = classify_workout_with_vertexai(vertex_model, metadata, thumbnail_base64)
        print("Classification successful.")
        cache_data(analysis, analysis_cache_path)
        return analysis
    except Exception as e:
        import traceback
        print(f"Detailed classification error: {traceback.format_exc()}")
        return {"error": f"Failed to classify workout using Vertex AI: {str(e)}"}


def extract_video_id(youtube_url):
    """Extract YouTube video ID from URL."""
    if not youtube_url:
        return None
    try:
        # Handle various URL formats
        parsed_url = urlparse(youtube_url)
        if 'youtu.be' in parsed_url.netloc:
            return parsed_url.path[1:]
        if 'youtube.com' in parsed_url.netloc:
            if parsed_url.path == '/watch':
                return parse_qs(parsed_url.query).get('v', [None])[0]
            elif parsed_url.path.startswith('/embed/'):
                return parsed_url.path.split('/')[2]
            elif parsed_url.path.startswith('/v/'):
                return parsed_url.path.split('/')[2]
            elif parsed_url.path.startswith('/shorts/'):
                 return parsed_url.path.split('/')[2]
        # Handle googleusercontent links (less common now, but kept for compatibility)
        if 'googleusercontent.com' in youtube_url:
             # This specific format might be outdated or need adjustment
             # Example: https://www.youtube.com/watch?v=xzqexC11dEM -> might need specific parsing logic if encountered
             print(f"Warning: Handling potentially ambiguous googleusercontent URL: {youtube_url}")
             # Attempt a simple split, may need refinement based on actual URL structure
             parts = youtube_url.split('/')
             if len(parts) > 2 and parts[-2] == 'youtube.com':
                 return parts[-1].split('?')[0]

    except Exception as e:
        print(f"Error parsing URL {youtube_url}: {e}")
        return None

    return None


def fetch_video_metadata(youtube_client, video_id):
    """Fetch comprehensive metadata for a YouTube video."""
    print(f"Fetching metadata for video ID: {video_id}")
    try:
        # Get video details
        video_request = youtube_client.videos().list(
            part='snippet,contentDetails,statistics,player',
            id=video_id
        )
        video_response = video_request.execute()

        if not video_response.get('items'):
            return {"error": f"Video not found (ID: {video_id})"}

        video_data = video_response['items'][0]

        # Get channel details
        channel_id = video_data['snippet']['channelId']
        channel_request = youtube_client.channels().list(
            part='snippet,statistics',
            id=channel_id
        )
        channel_response = channel_request.execute()
        channel_data = channel_response['items'][0] if channel_response.get('items') else {}

        # Get comments (top 5) - This can fail if comments are disabled
        comments = []
        try:
            comments_request = youtube_client.commentThreads().list(
                part='snippet',
                videoId=video_id,
                order='relevance', # 'time' might also be useful
                textFormat='plainText', # Request plain text
                maxResults=5
            )
            comments_response = comments_request.execute()
            comments = [item['snippet']['topLevelComment']['snippet']['textDisplay']
                        for item in comments_response.get('items', [])]
        except Exception as comment_error:
            # Check if it's specifically because comments are disabled
            if 'commentsDisabled' in str(comment_error):
                print(f"Comments are disabled for video ID: {video_id}")
                comments = ["Comments disabled for this video."]
            else:
                print(f"Warning: Could not fetch comments for video ID {video_id}: {comment_error}")
                comments = ["Could not retrieve comments."]

        # Parse duration
        duration_iso = video_data.get('contentDetails', {}).get('duration', 'PT0S')
        duration_seconds = 0
        try:
             duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())
        except isodate.ISO8601Error:
             print(f"Warning: Could not parse ISO 8601 duration '{duration_iso}'. Setting duration to 0.")


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
            # Likes might not be available publicly for all videos anymore
            'likeCount': int(video_data.get('statistics', {}).get('likeCount', 0)) if 'likeCount' in video_data.get('statistics', {}) else None,
            'thumbnails': video_data['snippet'].get('thumbnails', {}),
            'embedHtml': video_data.get('player', {}).get('embedHtml', ''),
            'comments': comments,
            'channelSubscriberCount': int(channel_data.get('statistics', {}).get('subscriberCount', 0)) if channel_data.get('statistics', {}).get('hiddenSubscriberCount') is False else None,
            'channelVideoCount': int(channel_data.get('statistics', {}).get('videoCount', 0))
        }
        print(f"Metadata fetched successfully for video ID: {video_id}")
        return metadata

    except Exception as e:
        import traceback
        print(f"Error fetching video metadata for ID {video_id}: {str(e)}")
        print(traceback.format_exc())
        return {"error": f"Error fetching video metadata: {str(e)}"}


def format_duration(seconds):
    """Format seconds into HH:MM:SS or MM:SS format."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "Invalid duration"
    seconds = int(seconds)
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
            json.dump(data, f, indent=2)
        print(f"Cached data to: {cache_path}")
    except Exception as e:
        print(f"Error caching data to {cache_path}: {str(e)}")


def encode_image_to_base64(image_path):
    """Encode image file to a Base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return None
    except Exception as e:
        print(f"Error encoding image {image_path}: {str(e)}")
        return None

def get_thumbnail_base64(thumbnail_url, cache_dir, video_id, force_refresh=False):
    """
    Downloads the thumbnail image, saves it as jpg in cache, encodes to Base64.
    """
    if not thumbnail_url:
        print("No thumbnail URL provided.")
        return None

    file_extension = os.path.splitext(urlparse(thumbnail_url).path)[1] or '.jpg' # Default to jpg if no extension
    cache_path = os.path.join(cache_dir, f"{video_id}_thumbnail{file_extension}")

    if os.path.exists(cache_path) and not force_refresh:
        print(f"Loading thumbnail from cache: {cache_path}")
    else:
        print(f"Downloading thumbnail from: {thumbnail_url}")
        try:
            response = requests.get(thumbnail_url, timeout=10) # Added timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            with open(cache_path, "wb") as f:
                f.write(response.content)
            print(f"Downloaded and cached thumbnail to: {cache_path}")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading thumbnail: {str(e)}")
            # Attempt to delete potentially corrupted cache file
            if os.path.exists(cache_path):
                 try: os.remove(cache_path)
                 except OSError: pass
            return None
        except Exception as e:
             print(f"An unexpected error occurred during thumbnail download: {e}")
             return None

    # Now encode the (potentially newly downloaded) image
    return encode_image_to_base64(cache_path)


def create_classification_prompt():
    """Create a detailed prompt for Vertex AI Gemini to classify workout videos."""
    # This prompt is largely the same, but emphasizes outputting valid JSON.
    # It also assumes the image will be provided as part of the input context.
    prompt = """You are a specialized AI fitness analyst. Your task is to analyze YouTube workout video metadata and an associated thumbnail image, and classify the workout into specific categories according to the provided JSON schema. Examine the title, description, comments, tags, channel information, and the visual cues from the thumbnail image to make your classification as accurate as possible.

METABOLIC FUNCTION EXPLANATIONS:
[... Same detailed explanations as in the original prompt ...]

BODY PART FOCUS EXPLANATION:
[... Same detailed explanations as in the original prompt ...]

WORKOUT SPIRIT EXPLANATIONS:
[... Same detailed explanations as in the original prompt ...]

WORKOUT VIBE DETAILS:
[... Same detailed explanations (1-26) as in the original prompt ...]

ANALYSIS GUIDELINES:
1. Examine the title, description, tags, channel info, comments, and the thumbnail image carefully.
2. Look for indicators of intensity, duration, exercise types, and visual cues.
3. Consider the channel's focus and typical content style.
4. When confidence is low for a category, mark it appropriately (e.g., "low"). If a category doesn't apply (like strength functions in a pure cardio workout), provide an empty array `[]` for list-based properties or omit optional fields if appropriate for the schema (though the target schema requires most).
5. For 'vibes' and 'spirits', identify up to 3 most suitable entries with a prominence value (0.0 to 1.0) for each.
6. For 'bodyPartFocus', ensure the percentages sum to 1.0.

CONFIDENCE LEVELS EXPLANATION:
- "very high": Strong explicit indicators in title, description, or visuals; central focus of the workout
- "high": Clear indicators or strong implicit evidence; confidently identifiable component
- "moderate": Some indicators or reasonable inference from context; likely but not certain
- "low": Minimal indicators or educated guess; possible but uncertain

RESPONSE FORMAT:
Your entire response MUST be a single, valid JSON object conforming to the schema described below. Do not include any text before or after the JSON object.

TARGET JSON SCHEMA:
{
  "type": "object",
  "properties": {
    "category": {
      "type": "string",
      "enum": ["Cardio", "Cool-down", "Flexibility", "Rest", "Strength", "Warm-up"]
    },
    "spiritsConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
    "vibesConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
    "bodyPartFocusConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
    "categoryConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
    "subcategory": {
      "type": "string",
      "enum": ["Body weight", "Breathing exercises", "Calisthenics", "Cool-down", "Elliptical", "HIIT", "Indoor biking", "Indoor rowing", "Mat", "Meditation", "Pilates", "Running", "Stretching", "Treadmill", "Walking", "Warm-up", "Weight workout", "Yoga"]
    },
    "subcategoryConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
    "aerobicMetabolicFunction": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["Zone 1 (recovery)", "Zone 2 (mitochondrial improvement)", "Functional Threshold (or anaerobic threshold training) - 12-25 minutes", "HIIT - High Intensity Interval Training (30s to 10m reps and rest)"]
      },
      "uniqueItems": true
    },
    "aerobicMetabolicFunctionConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
    "strengthMetabolicFunction": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["Functional strength", "Hypertrophy", "Maximal strength", "Muscle endurance", "Power"]
      },
      "uniqueItems": true
    },
    "strengthMetabolicFunctionConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
    "flexibilityMetabolicFunction": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["Range of motion", "Balance"]
      },
      "uniqueItems": true
    },
    "flexibilityMetabolicFunctionConfidence": {
      "type": "string",
      "enum": ["very high", "high", "moderate", "low"]
    },
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
    "vibes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "enum": ["The Warrior Workout", "The Firestarter", /* ... include all 26 vibe names ... */ "The Nature Flow"]},
          "prominence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["name", "prominence"]
      },
      "minItems": 0, "maxItems": 3 # Allow empty if none fit well
    },
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
      "minItems": 0, "maxItems": 3 # Allow empty if none fit well
    }
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

Now, analyze the following video metadata and thumbnail:
"""
    # The actual metadata and image Part will be appended after this prompt text
    return prompt


def format_metadata_for_analysis(metadata):
    """
    Format metadata in a structured, readable way for the AI model.
    (Truncates long fields to avoid excessive token usage).
    """
    sections = []
    MAX_DESC_LEN = 1500 # Max length for description
    MAX_COMMENT_LEN = 250 # Max length for each comment

    # Video basic information
    sections.append("## VIDEO INFORMATION")
    sections.append(f"Title: {metadata.get('title', 'N/A')}")
    sections.append(f"Channel: {metadata.get('channelTitle', 'N/A')}")
    sections.append(f"Duration: {metadata.get('durationFormatted', 'N/A')} ({metadata.get('duration', 0)} seconds)")
    sections.append(f"Published: {metadata.get('publishedAt', 'N/A')}")
    sections.append(f"Views: {metadata.get('viewCount', 0):,}")
    like_count = metadata.get('likeCount')
    sections.append(f"Likes: {like_count:,}" if like_count is not None else "Likes: N/A")


    # Tags
    tags = metadata.get('tags', [])
    if tags:
        sections.append("\n## TAGS")
        sections.append(", ".join(tags))

    # Description
    description = metadata.get('description', '')
    if description:
        sections.append("\n## DESCRIPTION")
        if len(description) > MAX_DESC_LEN:
            sections.append(f"{description[:MAX_DESC_LEN]}...(truncated)")
        else:
            sections.append(description)

    # Channel information
    sections.append("\n## CHANNEL INFORMATION")
    sections.append(f"Channel: {metadata.get('channelTitle', 'N/A')}")
    subscriber_count = metadata.get('channelSubscriberCount')
    sections.append(f"Subscribers: {subscriber_count:,}" if subscriber_count is not None else "Subscribers: Hidden or N/A")
    sections.append(f"Total channel videos: {metadata.get('channelVideoCount', 0):,}")
    chan_desc = metadata.get('channelDescription', '')
    if chan_desc:
        # Truncate channel description as well if needed
        sections.append(f"Channel description: {chan_desc[:500] + '...' if len(chan_desc) > 500 else chan_desc}")


    # Comments
    comments = metadata.get('comments', [])
    if comments and comments != ["Could not retrieve comments."] and comments != ["Comments disabled for this video."]:
        sections.append("\n## TOP COMMENTS")
        for i, comment in enumerate(comments[:5], 1): # Ensure max 5 comments
            if len(comment) > MAX_COMMENT_LEN:
                comment = comment[:MAX_COMMENT_LEN] + "...(truncated)"
            sections.append(f"{i}. {comment}")
    elif comments: # Handle disabled/error messages
         sections.append(f"\n## COMMENTS\n{comments[0]}")


    return "\n".join(sections)


def classify_workout_with_vertexai(model: GenerativeModel, metadata: dict, thumbnail_base64: str = None):
    """
    Use Vertex AI Gemini model to classify workout video based on metadata and thumbnail.

    Args:
        model: Initialized Vertex AI GenerativeModel.
        metadata: Dictionary containing video metadata.
        thumbnail_base64: Base64 encoded string of the thumbnail image (optional).

    Returns:
        dict: Parsed JSON classification result.

    Raises:
        Exception: If the API call fails or the response is not valid JSON.
    """
    system_prompt = create_classification_prompt()
    formatted_metadata = format_metadata_for_analysis(metadata)

    # Construct the prompt parts (text and image)
    prompt_parts = [Part.from_text(system_prompt + "\n\n" + formatted_metadata)]

    if thumbnail_base64:
        # Add image part if available
        image_part = Part.from_data(
            mime_type="image/jpeg",  # Assuming JPG, adjust if necessary (e.g., image/png)
            data=base64.b64decode(thumbnail_base64) # Decode base64 back to bytes for Vertex
        )
        prompt_parts.append(image_part)
    else:
        print("Proceeding with classification without thumbnail image.")


    # Configure generation settings
    generation_config = GenerationConfig(
        temperature=0.2, # Lower temperature for more deterministic JSON output
        # top_p=1.0,
        # top_k=32,
        max_output_tokens=8192, # Increased token limit for potentially large JSON
        response_mime_type="application/json", # Request JSON output directly
        # response_schema=... # More complex: Define schema programmatically if needed
    )

    # Set safety settings (adjust as needed)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }

    print("Sending request to Vertex AI Gemini model...")
    try:
        response = model.generate_content(
            prompt_parts,
            generation_config=generation_config,
            safety_settings=safety_settings,
            # stream=False # Use stream=True for large responses if needed
        )

        print("Received response from Vertex AI.")
        # Debug: Print raw response text
        # print("Raw Response Text:\n", response.text)

        # Attempt to parse the JSON response
        try:
            result = json.loads(response.text)
            # Basic validation: Check if it's a dictionary
            if not isinstance(result, dict):
                 raise json.JSONDecodeError("Response is not a JSON object", response.text, 0)
            # Add more specific validation if needed (e.g., check for required keys)
            print("JSON parsing successful.")
            return result
        except json.JSONDecodeError as json_err:
            print(f"Error: Failed to decode JSON response from Vertex AI: {json_err}")
            print("--- Raw Response ---")
            print(response.text)
            print("--- End Raw Response ---")
            # Include candidate/safety info if available for debugging
            if hasattr(response, 'candidates') and response.candidates:
                print(f"Finish Reason: {response.candidates[0].finish_reason}")
                if response.candidates[0].safety_ratings:
                    print("Safety Ratings:")
                    for rating in response.candidates[0].safety_ratings:
                        print(f"  - {rating.category}: {rating.probability}")
            raise Exception(f"Vertex AI response was not valid JSON. See logs for details. Error: {json_err}")


    except Exception as e:
        print(f"An error occurred during Vertex AI API call: {e}")
        # Log the full traceback for detailed debugging
        import traceback
        traceback.print_exc()
        raise # Re-raise the exception after logging


# Usage example
if __name__ == "__main__":
    test_url = "https://www.youtube.com/watch?v=xzqexC11dEM"

    print(f"\n--- Analyzing YouTube URL: {test_url} ---")
    # Use force_refresh=True to bypass cache and generate a new analysis
    # Use force_refresh=False to use cached data if available
    result = analyze_youtube_workout(test_url, force_refresh=False)

    print("\n--- Analysis Result ---")
    print(json.dumps(result, indent=2))
    print("--- End of Analysis ---")