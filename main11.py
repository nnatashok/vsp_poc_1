from googleapiclient.discovery import build
from openai import OpenAI, OpenAIError
import requests
import json
import os
import re
import time
import random
from urllib.parse import urlparse, parse_qs
import isodate  # For parsing ISO 8601 duration format


def analyze_youtube_workout(youtube_url, cache_dir='cache_11', force_refresh=False):
    """
    Analyzes a YouTube workout video and categorizes it according to various fitness parameters.

    Args:
        youtube_url (str): URL of the YouTube workout video
        cache_dir (str): Directory to store cached data
        force_refresh (bool): Whether to force fresh analysis even if cached data exists

    Returns:
        dict: Categorized workout information
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

    # Check for cached analysis results
    analysis_cache_path = os.path.join(cache_dir, f"{video_id}_analysis.json")
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
            cache_data(metadata, metadata_cache_path)
    else:
        metadata = fetch_video_metadata(youtube_client, video_id)
        cache_data(metadata, metadata_cache_path)

    # Get thumbnail images and snapshots
    thumbnail_url = metadata.get('snippet', {}).get('thumbnails', {}).get('high', {}).get('url', '')

    # Now send the metadata to OpenAI for workout classification
    try:
        analysis = classify_workout_with_openai(oai_client, metadata)
        cache_data(analysis, analysis_cache_path)
        return analysis
    except Exception as e:
        return {"error": f"Failed to classify workout: {str(e)}"}


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


def create_classification_prompt():
    """Create a detailed prompt for OpenAI to classify workout videos."""
    return """You are a specialized AI fitness analyst. Your task is to analyze YouTube workout video metadata and classify the workout into specific categories. Examine the title, description, comments, tags, channel information, and any other available metadata to make your classification as accurate as possible.

METABOLIC FUNCTION EXPLANATIONS:

Aerobic Metabolic Functions:
- Zone 1 (recovery): Very light intensity, conversational pace, primarily fat burning, perfect for active recovery.
- Zone 2 (mitochondrial improvement): Moderate intensity where you can still talk but with some effort. Builds base endurance and improves mitochondrial function. 
- Functional Threshold: Challenging intensity that can be sustained for 12-25 minutes, improves lactate threshold.
- HIIT: Short, intense bursts followed by rest periods. Improves VO2 max and anaerobic capacity.

Strength Metabolic Functions:
- Functional strength: Movements that mimic real-life activities, improves movement patterns and daily life capabilities.
- Hypertrophy: Moderate weights with higher rep ranges (8-12), focuses on muscle growth.
- Maximal strength: Heavy weights with low reps (1-5), focuses on strength development.
- Muscle endurance: Light to moderate weights with high reps (15+), improves ability to sustain effort.
- Power: Explosive movements combining speed and strength, improves rate of force development.

Flexibility Metabolic Functions:
- Range of motion: Improves joint mobility and muscle flexibility.
- Balance: Improves proprioception, stability, and body control.

BODY PART FOCUS EXPLANATION:
- Arms: Biceps, triceps, forearms, shoulders, deltoids
- Back: Lats, traps, rhomboids, spinal erectors, rear deltoids
- Chest: Pectorals, anterior deltoids, serratus anterior
- Legs: Quadriceps, hamstrings, glutes, calves, hip flexors, adductors, abductors

For body part focus, provide a percentage focus for each body part (Arms, Back, Chest, Legs). The values should sum to 1.0 (100%). For a balanced full-body workout, use equal distribution (0.25 for each part). For targeted workouts, allocate higher percentages to the primary focus areas. Additionally, provide an overall confidence level for your body part focus analysis.

Include confidence levels for "vibes" and "spirits" to indicate your overall certainty in the analysis of these aspects of the workout.

WORKOUT SPIRIT EXPLANATIONS:
- High-Energy & Intense: Fast-paced, heart-pumping, sweat-dripping sessions focused on pushing limits and maximum effort.
- Flow & Rhythm: Smooth, continuous movement patterns that emphasize coordination, music-driven pacing, and mind-body connection.
- Structured & Disciplined: Methodical, progressive training following specific protocols and technical precision.
- Soothing & Restorative: Gentle, healing-focused sessions emphasizing recovery, relaxation, and stress reduction.
- Sport & Agility: Athletic, performance-based training focused on speed, reflexes, coordination, and sports-specific skills.
- Outdoor & Adventure: Nature-based workouts that leverage terrain, environmental challenges, and exploration.

WORKOUT VIBE OPTIONS:
- The Warrior Workout: Unleash your inner beast. Sweat-dripping, heart-pounding, primal energy.
- The Firestarter: Fast, explosive, and electrifying. Short but devastating.
- The Nightclub Workout: Lights down, music up, full-body euphoria.
- The Competitor: Gamified, leaderboard-driven, full-send energy.
- The Adrenaline Rush: Heart-racing, full-body intensity, unpredictable challenges.
- The Groove Session: Fun, fluid, expressive, completely in the moment.
- The Meditative Grind: Zone in, lock down, let repetition take over.
- The Zen Flow: Grounding, intentional, breath-centered, unhurried.
- The Rhythmic Powerhouse: Beat-driven, strong but fluid, music-infused.
- The Endorphin Wave: Elevated energy, feel-good movement, steady build.
- The Progression Quest: Methodical, incremental, long-term improvement.
- The Masterclass Workout: Technique-driven, focused, skill-building.
- The Disciplined Grind: No excuses, no distractions, just execute.
- The Tactical Athlete: Military-inspired, performance-focused, strategic.
- The Foundation Builder: Strengthen weak points, rebuild, perfect the basics.
- The Reboot Workout: Deep stretch, low stress, total-body refresh.
- The Comfort Moves: Safe, cozy, feel-good movement.
- The Mindful Walk: Meditative, story-driven, immersive.
- The Deep Recharge: Nervous system reset, ultra-gentle movement.
- The Sleep Prep: Wind down, ease tension, prepare for rest.
- The Athlete's Circuit: Explosive power, agility, game-ready fitness.
- The Speed & Power Sprint: Short, high-speed, maximal power output.
- The Fight Camp: Grit, intensity, combat-ready fitness.
- The Explorer's Workout: Adventurous, scenic, open-air challenge.
- The Ruck Challenge: Weighted backpack, functional endurance.
- The Nature Flow: Breath-centered, full-body, outdoor rhythm.

COMPLEXITY LEVEL EXPLANATIONS:
- Beginner: Suitable for those new to fitness or the specific workout type. Features basic movements, detailed instruction, modifications for limited fitness levels, slower pacing, and emphasizes proper form.
- Intermediate: For those with established fitness bases. Incorporates more complex movement patterns, moderate intensity, some advanced variations, and assumes basic knowledge of exercises.
- Advanced: Designed for experienced individuals with strong fitness foundations. Features challenging intensity, complex combinations, minimal rest, advanced progressions, and assumes high proficiency in exercise techniques.

EQUIPMENT DETECTION:
Analyze the video content to identify any of the following equipment used:
- Mat: Used for floor exercises, yoga, pilates.
- Dumbbells: Hand weights of various sizes.
- Chair: Used for support, step-ups, or as a workout prop.
- Blocks: Yoga blocks or similar supportive equipment.
- Exercise bike: Stationary cycling equipment.
- Rowing machine: Indoor rowing equipment.
- Treadmill: Running/walking machine.
- Elliptical: Low-impact cardio machine.

ANALYSIS GUIDELINES:
1. Examine the title, description, and tags carefully for explicit workout information.
2. Look for indicators of intensity, duration, and exercise types.
3. Consider the channel's focus and typical content style.
4. User comments may provide additional clues about the workout experience.
5. When confidence is low for a category, mark it appropriately.
6. For categories that don't apply (e.g., strength aspects in a pure yoga video), provide empty arrays where appropriate.
7. For each workout, identify up to 3 most suitable "spirits" that capture the overall energy and approach, with an intensity value (0-1) for each.
8. For each workout, identify up to 3 most suitable "vibes" that match the specific feeling and experience, with an intensity value (0-1) for each.
9. Determine the appropriate complexity level (Beginner, Intermediate, or Advanced) based on movement complexity, intensity, instruction level, and modifications offered.
10. Identify all equipment used or required for the workout, choosing from the predefined list.

CONFIDENCE LEVELS EXPLANATION:
- "very high": Strong explicit indicators in title, description, or visuals; central focus of the workout
- "high": Clear indicators or strong implicit evidence; confidently identifiable component
- "moderate": Some indicators or reasonable inference from context; likely but not certain
- "low": Minimal indicators or educated guess; possible but uncertain

PROMINENCE VALUES EXPLANATION:
- 0.9-1.0: Extremely strong presence, central defining characteristic
- 0.7-0.89: Strong presence, clearly evident
- 0.5-0.69: Moderate presence, noticeable element
- 0.3-0.49: Mild presence, somewhat evident
- 0.1-0.29: Slight presence, minor element

Your response must follow the JSON schema provided in the API call. If there's insufficient information for a particular category, use your best judgment and provide the most likely options based on available data.
"""


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
        # Truncate very long descriptions to first 1000 chars
        description = metadata.get('description', '')
        if len(description) > 1000:
            sections.append(f"{description[:1000]}...(truncated)")
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


def classify_workout_with_openai(oai_client, metadata):
    """Use OpenAI to classify workout video based on metadata with retry mechanism for rate limits."""
    prompt = create_classification_prompt()

    # Полная JSON-схема для строгой валидации ответа с добавлением complexity и equipment
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "WorkoutAnalysis",  # Обязательное поле name для json_schema
            "schema": {  # Упаковываем схему в поле schema
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
                        "enum": ["Body weight", "Breathing exercises", "Calisthenics", "Cool-down", "Elliptical",
                                 "HIIT", "Indoor biking", "Indoor rowing", "Mat", "Meditation", "Pilates", "Running",
                                 "Stretching", "Treadmill", "Walking", "Warm-up", "Weight workout", "Yoga"]
                    },
                    "subcategoryConfidence": {
                        "type": "string",
                        "enum": ["very high", "high", "moderate", "low"]
                    },
                    "aerobicMetabolicFunction": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "Zone 1 (recovery)",
                                "Zone 2 (mitochondrial improvement)",
                                "Functional Threshold (or anaerobic threshold training) - 12-25 minutes",
                                "HIIT - High Intensity Interval Training (30s to 10m reps and rest)"
                            ]
                        },
                        "uniqueItems": True
                    },
                    "aerobicMetabolicFunctionConfidence": {
                        "type": "string",
                        "enum": ["very high", "high", "moderate", "low"]
                    },
                    "strengthMetabolicFunction": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["Functional strength", "Hypertrophy", "Maximal strength", "Muscle endurance",
                                     "Power"]
                        },
                        "uniqueItems": True
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
                        "uniqueItems": True
                    },
                    "flexibilityMetabolicFunctionConfidence": {
                        "type": "string",
                        "enum": ["very high", "high", "moderate", "low"]
                    },
                    "bodyPartFocus": {
                        "type": "object",
                        "properties": {
                            "Arms": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "Back": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "Chest": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "Legs": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        },
                        "required": ["Arms", "Back", "Chest", "Legs"],
                        "additionalProperties": False
                    },
                    "vibes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "enum": [
                                        "The Warrior Workout", "The Firestarter", "The Nightclub Workout",
                                        "The Competitor",
                                        "The Adrenaline Rush", "The Groove Session", "The Meditative Grind",
                                        "The Zen Flow",
                                        "The Rhythmic Powerhouse", "The Endorphin Wave", "The Progression Quest",
                                        "The Masterclass Workout", "The Disciplined Grind", "The Tactical Athlete",
                                        "The Foundation Builder", "The Reboot Workout", "The Comfort Moves",
                                        "The Mindful Walk", "The Deep Recharge", "The Sleep Prep",
                                        "The Athlete's Circuit",
                                        "The Speed & Power Sprint", "The Fight Camp", "The Explorer's Workout",
                                        "The Ruck Challenge", "The Nature Flow"
                                    ]
                                },
                                "prominence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1
                                }
                            },
                            "required": ["name", "prominence"]
                        },
                        "minItems": 1,
                        "maxItems": 3
                    },
                    "spirits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "enum": [
                                        "High-Energy & Intense", "Flow & Rhythm", "Structured & Disciplined",
                                        "Soothing & Restorative", "Sport & Agility", "Outdoor & Adventure"
                                    ]
                                },
                                "prominence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1
                                }
                            },
                            "required": ["name", "prominence"]
                        },
                        "minItems": 1,
                        "maxItems": 3
                    },
                    # New properties for complexity and equipment
                    "complexityLevel": {
                        "type": "string",
                        "enum": ["Beginner", "Intermediate", "Advanced"]
                    },
                    "complexityLevelConfidence": {
                        "type": "string",
                        "enum": ["very high", "high", "moderate", "low"]
                    },
                    "equipment": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["Mat", "Dumbbells", "Chair", "Blocks", "Exercise bike",
                                     "Rowing machine", "Treadmill", "Elliptical"]
                        },
                        "uniqueItems": True
                    },
                    "equipmentConfidence": {
                        "type": "string",
                        "enum": ["very high", "high", "moderate", "low"]
                    }
                },
                "required": ["category", "subcategory", "complexityLevel", "equipment"],
                "additionalProperties": False
            }
        }
    }

    # Format metadata in a more structured and explanatory way
    formatted_metadata = format_metadata_for_analysis(metadata)

    # Maximum number of retries
    max_retries = 5
    # Initial retry delay in seconds
    retry_delay = 2

    for retry_attempt in range(max_retries):
        try:
            response = oai_client.chat.completions.create(
                model="gpt-4o",
                response_format=response_format,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user",
                     "content": f"Analyze this workout video metadata and classify it according to the schema:\n\n{formatted_metadata}"}
                ]
            )

            result = json.loads(response.choices[0].message.content)
            return result

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
                    return {"error": f"Error classifying workout with OpenAI after {max_retries} retries: {str(e)}"}
            else:
                # If it's not a rate limit error, don't retry
                return {"error": f"Error classifying workout with OpenAI: {str(e)}"}

    # This should only happen if we exhaust all retries
    return {"error": "Failed to classify workout after maximum retry attempts"}


# Usage example
if __name__ == "__main__":
    # Добавляем force_refresh=True для игнорирования кэша и создания нового анализа
    result = analyze_youtube_workout("https://www.youtube.com/watch?v=xzqexC11dEM", force_refresh=True)
    print(json.dumps(result, indent=2))