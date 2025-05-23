import base64
import json
import os
import requests
from urllib.parse import urlparse, parse_qs
import isodate  # For parsing ISO 8601 duration format
from googleapiclient.discovery import build
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    Part,
    GenerationConfig,
    HarmCategory,
    HarmBlockThreshold
)
import traceback # For detailed error logging

# --- Configuration ---
# Replace with your actual Google Cloud project ID and region
VERTEXAI_PROJECT_ID = 'norse-sector-250410'
VERTEXAI_LOCATION = 'us-central1' # e.g., 'us-central1'
# Replace with your actual YouTube API Key
YOUTUBE_API_KEY = 'AIzaSyCkpiTfTUvNVNmPcyw8ZO1NOn_0b_LV8RA'
# Specify the Gemini model to use (ensure it supports multimodal input)
VERTEXAI_MODEL_NAME = "gemini-1.5-pro-preview-0409"
# --- End Configuration ---

# --- Constants ---
CACHE_DIR = 'cache_4' # Changed cache dir name
MAX_DESC_LEN = 1500 # Max length for description in prompt
MAX_COMMENT_LEN = 250 # Max length for each comment in prompt
MAX_CHAN_DESC_LEN = 500 # Max length for channel description in prompt
# --- End Constants ---

# Global variable for the initialized model (optional, could also be passed around)
vertex_model = None

def initialize_vertexai():
    """Initializes Vertex AI and the Generative Model."""
    global vertex_model
    if vertex_model is None:
        if not VERTEXAI_PROJECT_ID or not VERTEXAI_LOCATION:
            print("FATAL: VERTEXAI_PROJECT_ID and VERTEXAI_LOCATION must be set.")
            raise ValueError("Missing Vertex AI project ID or location.")
        try:
            print(f"Initializing Vertex AI for project '{VERTEXAI_PROJECT_ID}' in location '{VERTEXAI_LOCATION}'...")
            vertexai.init(project=VERTEXAI_PROJECT_ID, location=VERTEXAI_LOCATION)
            # Ensure the model selected supports video modality
            vertex_model = GenerativeModel(VERTEXAI_MODEL_NAME)
            print(f"Vertex AI initialized successfully. Using model: {VERTEXAI_MODEL_NAME}")
        except Exception as e:
            print(f"FATAL: Failed to initialize Vertex AI: {str(e)}")
            print(traceback.format_exc())
            raise  # Re-raise the exception

def initialize_youtube_client():
    """Initializes the YouTube Data API client."""
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == 'YOUR_YOUTUBE_API_KEY':
        print("FATAL: YOUTUBE_API_KEY must be set.")
        raise ValueError("Missing YouTube API Key.")
    try:
        print("Initializing YouTube API client...")
        youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        print("YouTube API client initialized.")
        return youtube_client
    except Exception as e:
        print(f"FATAL: Failed to initialize YouTube API client: {str(e)}")
        print(traceback.format_exc())
        raise

def analyze_youtube_workout(youtube_url, cache_dir=CACHE_DIR, force_refresh=False):
    """
    Analyzes a YouTube workout video using Vertex AI Gemini, providing the video URL
    directly to the model along with metadata for context.

    Args:
        youtube_url (str): URL of the YouTube workout video.
        cache_dir (str): Directory to store cached data (metadata and analysis).
        force_refresh (bool): Whether to force fresh analysis even if cached data exists.

    Returns:
        dict: Categorized workout information or an error dictionary.
    """
    # Initialize API clients (Vertex AI is initialized globally or on first call)
    try:
        initialize_vertexai() # Ensure Vertex AI is initialized
        youtube_client = initialize_youtube_client() # Ensure YouTube client is initialized
    except Exception as e:
        # Initialization errors are fatal
        return {"error": f"API Client Initialization Failed: {str(e)}"}

    # Extract video ID
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return {"error": "Invalid YouTube URL. Could not extract video ID."}
    print(f"Extracted Video ID: {video_id}")

    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)

    # Check for cached analysis results first (most efficient check)
    analysis_cache_path = os.path.join(cache_dir, f"{video_id}_vertex_video_analysis.json") # Specific cache filename
    if os.path.exists(analysis_cache_path) and not force_refresh:
        try:
            with open(analysis_cache_path, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
            print(f"Loaded analysis from cache: {analysis_cache_path}")
            return analysis
        except Exception as e:
            print(f"Warning: Error loading cached analysis: {str(e)}. Proceeding with fresh analysis.")

    # --- Metadata Handling ---
    metadata_cache_path = os.path.join(cache_dir, f"{video_id}_metadata.json")
    metadata = None

    # Try loading metadata from cache
    if os.path.exists(metadata_cache_path) and not force_refresh:
        try:
            with open(metadata_cache_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"Loaded metadata from cache: {metadata_cache_path}")
        except Exception as e:
            print(f"Warning: Error loading cached metadata: {str(e)}. Fetching fresh metadata.")
            metadata = None # Ensure metadata is None if cache load fails

    # Fetch metadata if not loaded from cache or if refresh is forced
    if metadata is None:
        metadata = fetch_video_metadata(youtube_client, video_id)
        if "error" in metadata:
            return metadata # Propagate metadata fetch error
        cache_data(metadata, metadata_cache_path)

    # --- Vertex AI Video Analysis ---
    try:
        if not vertex_model:
             # This check should ideally be redundant due to initialize_vertexai()
             return {"error": "Vertex AI model not initialized."}

        print("Starting workout classification with Vertex AI (using video URL)...")
        # Pass the youtube_url directly to the classification function
        analysis = classify_workout_with_vertexai_video(vertex_model, metadata, youtube_url)
        print("Classification successful.")
        cache_data(analysis, analysis_cache_path) # Cache the successful analysis
        return analysis
    except Exception as e:
        print(f"ERROR: Failed to classify workout using Vertex AI: {str(e)}")
        print(traceback.format_exc()) # Print detailed traceback
        return {"error": f"Vertex AI Classification Failed: {str(e)}"}

# --- Helper Functions (extract_video_id, fetch_video_metadata, format_duration, cache_data, format_metadata_for_analysis) ---
# These functions remain largely the same as in the original script.
# Minor adjustments might be needed based on Gemini's behavior with video + metadata.

def extract_video_id(youtube_url):
    """Extract YouTube video ID from various URL formats."""
    if not youtube_url:
        return None
    try:
        # Standard watch URL
        if "youtube.com/watch" in youtube_url:
            parsed_url = urlparse(youtube_url)
            query_params = parse_qs(parsed_url.query)
            return query_params.get("v", [None])[0]
        # Shortened URL
        elif "youtu.be/" in youtube_url:
            parsed_url = urlparse(youtube_url)
            return parsed_url.path[1:] # Path after the slash
        # Embed URL
        elif "youtube.com/embed/" in youtube_url:
            parsed_url = urlparse(youtube_url)
            return parsed_url.path.split('/embed/')[1].split('?')[0]
         # Shorts URL
        elif "youtube.com/shorts/" in youtube_url:
            parsed_url = urlparse(youtube_url)
            return parsed_url.path.split('/shorts/')[1].split('?')[0]
        # Less common V URL
        elif "youtube.com/v/" in youtube_url:
             parsed_url = urlparse(youtube_url)
             return parsed_url.path.split('/v/')[1].split('?')[0]
        # Handle potential googleusercontent links if necessary (though direct analysis is preferred)
        elif 'googleusercontent.com/youtube.com/' in youtube_url:
            # This format might indicate a proxied link; direct analysis might still work
            # Let's try a generic extraction assuming ID is often last path component
            parts = youtube_url.split('/')
            if len(parts) > 1:
                 potential_id = parts[-1].split('?')[0]
                 # Basic check if it looks like a video ID (alphanumeric, underscore, hyphen)
                 if all(c.isalnum() or c in ['_', '-'] for c in potential_id) and len(potential_id) > 5:
                      print(f"Warning: Attempting extraction from googleusercontent URL: {potential_id}")
                      return potential_id
            print(f"Warning: Could not reliably extract ID from googleusercontent URL: {youtube_url}")
            return None # Avoid guessing if unsure

    except Exception as e:
        print(f"Error parsing URL {youtube_url}: {e}")
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
        snippet = video_data.get('snippet', {})
        content_details = video_data.get('contentDetails', {})
        statistics = video_data.get('statistics', {})
        player = video_data.get('player', {})

        # Get channel details
        channel_id = snippet.get('channelId')
        channel_data = {}
        channel_stats = {}
        channel_snippet = {}
        if channel_id:
            try:
                channel_request = youtube_client.channels().list(
                    part='snippet,statistics',
                    id=channel_id
                )
                channel_response = channel_request.execute()
                if channel_response.get('items'):
                    channel_data = channel_response['items'][0]
                    channel_stats = channel_data.get('statistics', {})
                    channel_snippet = channel_data.get('snippet', {})
            except Exception as chan_e:
                 print(f"Warning: Could not fetch channel details for {channel_id}: {chan_e}")

        # Get comments (top 5) - Handle potential errors gracefully
        comments = []
        try:
            comments_request = youtube_client.commentThreads().list(
                part='snippet',
                videoId=video_id,
                order='relevance', # 'time' might also be useful
                textFormat='plainText',
                maxResults=5
            )
            comments_response = comments_request.execute()
            comments = [item['snippet']['topLevelComment']['snippet']['textDisplay']
                        for item in comments_response.get('items', [])]
        except Exception as comment_error:
            if 'commentsDisabled' in str(comment_error):
                print(f"Info: Comments are disabled for video ID: {video_id}")
                comments = ["Comments disabled for this video."]
            elif 'forbidden' in str(comment_error).lower():
                 print(f"Warning: Access forbidden for comments on video ID {video_id}. Check API key permissions.")
                 comments = ["Could not retrieve comments (permission denied)."]
            else:
                print(f"Warning: Could not fetch comments for video ID {video_id}: {comment_error}")
                comments = ["Could not retrieve comments (error)."]

        # Parse duration
        duration_iso = content_details.get('duration', 'PT0S')
        duration_seconds = 0
        try:
            duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())
        except (isodate.ISO8601Error, ValueError) as dur_e:
            print(f"Warning: Could not parse ISO 8601 duration '{duration_iso}': {dur_e}. Setting duration to 0.")

        # Compile metadata
        metadata = {
            'video_id': video_id,
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'channelTitle': snippet.get('channelTitle', ''),
            'channelDescription': channel_snippet.get('description', ''),
            'tags': snippet.get('tags', []),
            'publishedAt': snippet.get('publishedAt', ''),
            'duration': duration_seconds,
            'durationFormatted': format_duration(duration_seconds),
            'viewCount': int(statistics.get('viewCount', 0)),
            'likeCount': int(statistics['likeCount']) if 'likeCount' in statistics else None,
            # Note: Comment count from statistics might differ from retrieved comments
            'commentCount': int(statistics.get('commentCount', 0)) if 'commentCount' in statistics else None,
            'thumbnails': snippet.get('thumbnails', {}), # Keep thumbnails for potential display/other uses
            'embedHtml': player.get('embedHtml', ''),
            'topComments': comments, # Renamed for clarity
            'channelSubscriberCount': int(channel_stats['subscriberCount']) if channel_stats.get('subscriberCount') and not channel_stats.get('hiddenSubscriberCount', False) else None,
            'channelVideoCount': int(channel_stats.get('videoCount', 0))
        }
        print(f"Metadata fetched successfully for video ID: {video_id}")
        return metadata

    except Exception as e:
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
            json.dump(data, f, indent=2, ensure_ascii=False) # ensure_ascii=False for broader language support
        print(f"Cached data to: {cache_path}")
    except Exception as e:
        print(f"Error caching data to {cache_path}: {str(e)}")


def format_metadata_for_analysis(metadata):
    """
    Format metadata in a structured, readable way for the AI model.
    Truncates long fields to avoid excessive token usage.
    """
    sections = []

    # Video basic information
    sections.append("## VIDEO INFORMATION")
    sections.append(f"Title: {metadata.get('title', 'N/A')}")
    sections.append(f"Channel: {metadata.get('channelTitle', 'N/A')}")
    sections.append(f"Duration: {metadata.get('durationFormatted', 'N/A')} ({metadata.get('duration', 0)} seconds)")
    sections.append(f"Published: {metadata.get('publishedAt', 'N/A')}")
    sections.append(f"Views: {metadata.get('viewCount', 0):,}")
    like_count = metadata.get('likeCount')
    sections.append(f"Likes: {like_count:,}" if like_count is not None else "Likes: N/A")
    comment_count = metadata.get('commentCount')
    sections.append(f"Comment Count: {comment_count:,}" if comment_count is not None else "Comment Count: N/A")


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
        sections.append(f"Channel description: {chan_desc[:MAX_CHAN_DESC_LEN] + '...' if len(chan_desc) > MAX_CHAN_DESC_LEN else chan_desc}")


    # Top Comments
    comments = metadata.get('topComments', []) # Use the renamed key
    if comments and comments != ["Could not retrieve comments (error)."] and comments != ["Could not retrieve comments (permission denied)."] and comments != ["Comments disabled for this video."]:
        sections.append("\n## TOP COMMENTS (Sample)")
        for i, comment in enumerate(comments[:5], 1): # Ensure max 5 comments
            safe_comment = str(comment) # Ensure it's a string
            if len(safe_comment) > MAX_COMMENT_LEN:
                safe_comment = safe_comment[:MAX_COMMENT_LEN] + "...(truncated)"
            sections.append(f"{i}. {safe_comment}")
    elif comments: # Handle disabled/error messages
         sections.append(f"\n## COMMENTS\nStatus: {comments[0]}")


    return "\n".join(sections)


def create_classification_prompt_video():
    """Create a detailed prompt for Vertex AI Gemini to classify workout videos using video content and metadata."""
    # Updated prompt emphasizing video analysis
    prompt = """You are a specialized AI fitness analyst. Your task is to analyze the **content of the YouTube video provided via the URL**, along with its **metadata** (title, description, tags, channel info, comments, duration), and classify the workout into specific categories according to the provided JSON schema.

**Pay close attention to the visual and auditory cues from the video itself**:
* What exercises are being performed?
* What is the intensity level demonstrated (speed, effort)?
* What equipment is used (if any)?
* What is the instructor's style and instructions?
* What is the overall pace and flow of the workout?
* Does the music or tone suggest a particular mood?

Combine these observations with the textual metadata to make your classification as accurate as possible.

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

WORKOUT VIBE DETAILS:
1. The Warrior Workout: Unleash your inner beast. Sweat-dripping, heart-pounding, primal energy.  
   - Example Workouts: HIIT, boxing, bootcamp, heavy strength training.  
   - Platforms: Peloton Bootcamp, Les Mills BodyCombat, Beachbody Insanity, iFit HIIT.  
   - Best For: Days when you want to destroy stress and feel invincible.
2. The Firestarter: Fast, explosive, and electrifying. Short but devastating.  
   - Example Workouts: Tabata, sprint intervals, powerlifting bursts.  
   - Platforms: Peloton HIIT Rides, iFit Sprint Workouts, Nike Training Club Quick HIIT.  
   - Best For: When you only have 10-20 minutes but want to give 1000%.
3. The Nightclub Workout: Lights down, music up, full-body euphoria.  
   - Example Workouts: Dance cardio, rhythm boxing, cycle party rides.  
   - Platforms: Peloton EDM Rides, Les Mills Sh’Bam, Apple Fitness+ Dance, Zumba.  
   - Best For: When you want to move like no one’s watching and feel amazing.
4. The Competitor: Gamified, leaderboard-driven, full-send energy.  
   - Example Workouts: Live cycling, rowing races, CrossFit, esports-style fitness.  
   - Platforms: Peloton Leaderboard, Zwift Races, Hydrow Competitive Rows.  
   - Best For: Those who need to chase a score or beat their own record.
5. The Adrenaline Rush: Heart-racing, full-body intensity, unpredictable challenges.  
   - Example Workouts: Obstacle course training, parkour, extreme bootcamps.  
   - Platforms: Tough Mudder Training, Spartan Race Workouts, Freeletics.  
   - Best For: Those who crave challenge, variety, and adrenaline.
6. The Groove Session: Fun, fluid, expressive, completely in the moment.  
   - Example Workouts: Dance-based workouts, shadowboxing, flow yoga.  
   - Platforms: Apple Fitness+ Dance, Peloton Boxing, Barre3, Les Mills BodyBalance.  
   - Best For: Days when you want to move intuitively and just vibe.
7. The Meditative Grind: Zone in, lock down, let repetition take over.  
   - Example Workouts: Rowing, long-distance cycling, endurance running.  
   - Platforms: Hydrow Endurance Rows, Peloton Endurance Rides, iFit Scenic Runs.  
   - Best For: Those who love a slow burn and rhythmic intensity.
8. The Zen Flow: Grounding, intentional, breath-centered, unhurried.  
   - Example Workouts: Slow-flow yoga, tai chi, mobility training.  
   - Platforms: Alo Moves, Peloton Yoga, iFit Recovery Workouts.  
   - Best For: When you need balance, mindfulness, and release.
9. The Rhythmic Powerhouse: Beat-driven, strong but fluid, music-infused.  
   - Example Workouts: Power yoga, dance strength, cardio boxing.  
   - Platforms: Les Mills BodyJam, Peloton Boxing, Barre3.  
   - Best For: When you want strength and rhythm to blend seamlessly.
10. The Endorphin Wave: Elevated energy, feel-good movement, steady build.  
    - Example Workouts: Cycling climbs, endurance rowing, plyometric flows.  
    - Platforms: Peloton Power Zone Rides, iFit Rowing Journeys.  
    - Best For: When you want a challenging but steady burn.
11. The Progression Quest: Methodical, incremental, long-term improvement.  
    - Example Workouts: Strength cycles, hypertrophy training, marathon training plans.  
    - Platforms: iFit Progressive Strength, Tonal Programs, Peloton Strength Plans.  
    - Best For: Anyone who loves tracking progress and leveling up.
12. The Masterclass Workout: Technique-driven, focused, skill-building.  
    - Example Workouts: Pilates, kettlebell training, Olympic lifting, mobility drills.  
    - Platforms: Les Mills Core, Kettlebell Workouts on YouTube, Ready State Mobility.  
    - Best For: Those who love precision and mastery in movement.
13. The Disciplined Grind: No excuses, no distractions, just execute.  
    - Example Workouts: Classic bodybuilding, strength endurance, functional fitness.  
    - Platforms: Fitness Blender Strength, iFit Gym Workouts, Peloton Power Zones.  
    - Best For: When you want pure focus and efficiency.
14. The Tactical Athlete: Military-inspired, performance-focused, strategic.  
    - Example Workouts: Ruck training, tactical fitness, functional circuits.  
    - Platforms: Mountain Tactical Institute, Navy SEAL Workouts, Tactical Barbell.  
    - Best For: Those who want military-grade training and real-world capability.
15. The Foundation Builder: Strengthen weak points, rebuild, perfect the basics.  
    - Example Workouts: Stability, corrective exercise, injury prevention.  
    - Platforms: GOWOD, Ready State Mobility, Foundation Training.  
    - Best For: Those coming back from injury or refining fundamentals.
16. The Reboot Workout: Deep stretch, low stress, total-body refresh.  
    - Example Workouts: Gentle yoga, mobility drills, foam rolling.  
    - Platforms: Peloton Recovery, GOWOD, iFit Mobility.  
    - Best For: Recovery days, stress relief, post-travel stiffness.
17. The Comfort Moves: Safe, cozy, feel-good movement.  
    - Example Workouts: Chair workouts, senior fitness, prenatal/postnatal movement.  
    - Platforms: SilverSneakers, Fitness Blender Low-Impact, YouTube Chair Workouts.  
    - Best For: Those who want to move but need it to feel easy and accessible.
18. The Mindful Walk: Meditative, story-driven, immersive.  
    - Example Workouts: Guided outdoor walks, treadmill hikes.  
    - Platforms: Apple Fitness+ Time to Walk, iFit Outdoor Walks.  
    - Best For: When you need fresh air, a change of pace, and mental clarity.
19. The Deep Recharge: Nervous system reset, ultra-gentle movement.  
    - Example Workouts: Yoga Nidra, breathwork, passive stretching.  
    - Platforms: Yoga with Adriene, Headspace Yoga, iRest Meditation.  
    - Best For: Times of extreme stress, fatigue, or mental overload.
20. The Sleep Prep: Wind down, ease tension, prepare for rest.  
    - Example Workouts: Bedtime yoga, deep breathing, progressive relaxation.  
    - Platforms: Calm App, Peloton Sleep Yoga, Yoga Nidra.  
    - Best For: When you need the best possible night’s sleep.
21. The Athlete’s Circuit: Explosive power, agility, game-ready fitness.  
    - Example Workouts: Sprint drills, plyometrics, sport-specific agility.  
    - Platforms: Nike Training Club, Vertimax Workouts, P90X.  
    - Best For: Those training for sports or improving athleticism.
22. The Speed & Power Sprint: Short, high-speed, maximal power output.  
    - Example Workouts: Sprint workouts, fast-twitch training, overspeed drills.  
    - Platforms: Peloton Tread Intervals, Sprint Workouts, EXOS Training.  
    - Best For: Those improving speed, acceleration, and fast reactions.
23. The Fight Camp: Grit, intensity, combat-ready fitness.  
    - Example Workouts: MMA training, heavy bag work, footwork drills.  
    - Platforms: FightCamp, Bas Rutten Workouts, Les Mills BodyCombat.  
    - Best For: Those who want to train like a fighter.
24. The Explorer’s Workout: Adventurous, scenic, open-air challenge.  
    - Example Workouts: Trail running, outdoor HIIT, sand dune sprints.  
    - Platforms: iFit Outdoor Series, Trail Running Workouts.  
    - Best For: When you want nature, challenge, and adventure.
25. The Ruck Challenge: Weighted backpack, functional endurance.  
    - Example Workouts: Rucking, weighted hikes, uphill treks.  
    - Platforms: GoRuck Programs, Tactical Training Workouts.  
    - Best For: Those who want real-world endurance and strength.
26. The Nature Flow: Breath-centered, full-body, outdoor rhythm.  
    - Example Workouts: Beach workouts, rock climbing drills, park workouts.  
    - Platforms: iFit Beach Sessions, Outdoor Bootcamps.  
    - Best For: When you want fresh air, nature, and full-body movement.

ANALYSIS GUIDELINES:
1.  **Prioritize the video content** (exercises shown, intensity, pace, audio cues).
2.  Use metadata (title, description, tags, comments) as **supporting context**.
3.  Infer intensity, duration, exercise types from both video and text.
4.  Consider the channel's typical content style if known from metadata.
5.  When confidence is low for a category, mark it "low". If a category doesn't apply (e.g., strength functions in pure cardio), provide an empty array `[]` for list properties or use reasonable defaults (like 0 for body part focus if truly N/A). Ensure bodyPartFocus percentages sum to 1.0.
6.  For 'vibes' and 'spirits', identify up to 3 most suitable entries with a prominence value (0.0 to 1.0) for each. Sum of prominence is not restricted.
7.  Adhere strictly to the JSON output format and schema.

CONFIDENCE LEVELS EXPLANATION:
- "very high": Obvious and central focus, explicitly stated or clearly demonstrated throughout.
- "high": Clearly identifiable component, strong evidence from video/text.
- "moderate": Reasonable inference from context, likely present but not the sole focus.
- "low": Minimal indicators, educated guess, uncertain.

RESPONSE FORMAT:
Your entire response MUST be a single, valid JSON object conforming to the schema described below. Do not include any text, explanations, or markdown formatting before or after the JSON object.

TARGET JSON SCHEMA:
{
  "type": "object",
  "properties": {
    "category": { "type": "string", "enum": ["Cardio", "Cool-down", "Flexibility", "Rest", "Strength", "Warm-up"] },
    "categoryConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "subcategory": { "type": "string", "enum": ["Body weight", "Breathing exercises", "Calisthenics", "Cool-down", "Elliptical", "HIIT", "Indoor biking", "Indoor rowing", "Mat", "Meditation", "Pilates", "Running", "Stretching", "Treadmill", "Walking", "Warm-up", "Weight workout", "Yoga"] },
    "subcategoryConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "aerobicMetabolicFunction": {
      "type": "array",
      "items": { "type": "string", "enum": ["Zone 1 (recovery)", "Zone 2 (mitochondrial improvement)", "Functional Threshold (or anaerobic threshold training) - 12-25 minutes", "HIIT - High Intensity Interval Training (30s to 10m reps and rest)"] },
      "uniqueItems": true
    },
    "aerobicMetabolicFunctionConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "strengthMetabolicFunction": {
      "type": "array",
      "items": { "type": "string", "enum": ["Functional strength", "Hypertrophy", "Maximal strength", "Muscle endurance", "Power"] },
      "uniqueItems": true
    },
    "strengthMetabolicFunctionConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "flexibilityMetabolicFunction": {
      "type": "array",
      "items": { "type": "string", "enum": ["Range of motion", "Balance"] },
      "uniqueItems": true
    },
    "flexibilityMetabolicFunctionConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
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
     "bodyPartFocusConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
    "vibes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          # Make sure to list ALL 26 vibe names in the enum below
          "name": {"type": "string", "enum": ["The Warrior Workout", "The Firestarter", "The Zen Master", "The Power Builder", "The Enduro Champ", "The Agility Ace", "The Recovery Ritual", "The Morning Energizer", "The Lunchtime Lift", "The Evening Unwind", "The Dance Fusion", "The Core Crusher", "The Flexibility Flow", "The Strength Circuit", "The Cardio Blast", "The Mindful Mover", "The Body Sculptor", "The Athletic Performer", "The Calisthenics King/Queen", "The Pilates Pro", "The Yoga Guru", "The Boxing Powerhouse", "The Runner's High", "The Cyclist's Climb", "The Swimmer's Glide", "The Nature Flow"]},
          "prominence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["name", "prominence"]
      },
      "minItems": 0, "maxItems": 3
    },
    "vibesConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] },
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
      "minItems": 0, "maxItems": 3
    },
    "spiritsConfidence": { "type": "string", "enum": ["very high", "high", "moderate", "low"] }
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

Now, analyze the following video (provided via URL) and its associated metadata:
"""
    # The actual metadata text and video Part will be appended after this prompt text
    return prompt


def classify_workout_with_vertexai_video(model: GenerativeModel, metadata: dict, youtube_url: str):
    """
    Use Vertex AI Gemini model to classify workout video based on the video URL and metadata.

    Args:
        model: Initialized Vertex AI GenerativeModel.
        metadata: Dictionary containing video metadata.
        youtube_url: The URL of the YouTube video to analyze.

    Returns:
        dict: Parsed JSON classification result.

    Raises:
        Exception: If the API call fails or the response is not valid JSON.
    """
    system_prompt = create_classification_prompt_video()
    formatted_metadata = format_metadata_for_analysis(metadata)

    # Construct the prompt parts (text metadata + video URI)
    prompt_parts = [
        # Part 1: System prompt + formatted text metadata
        Part.from_text(system_prompt + "\n\n" + formatted_metadata),

        # Part 2: The video itself, referenced by URL
        # Use 'video/youtube' mime type for direct YouTube URLs
        # Ensure the URL is clean and directly points to the video
        Part.from_uri(uri=youtube_url, mime_type="video/youtube")
    ]

    # Configure generation settings
    generation_config = GenerationConfig(
        temperature=0.2, # Lower temperature for more deterministic JSON
        # top_p=1.0, # Often default is fine
        # top_k=32,  # Often default is fine
        max_output_tokens=8192, # Ensure sufficient space for complex JSON
        response_mime_type="application/json", # Crucial for getting JSON output
    )

    # Set safety settings (adjust as needed)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }

    print(f"Sending request to Vertex AI Gemini model for video: {youtube_url}")
    print(f"Using model: {model._model_name}") # Access underlying model name
    print(f"Prompt includes {len(prompt_parts)} parts (Text Metadata + Video URI).")

    try:
        # Make the API call
        response = model.generate_content(
            prompt_parts,
            generation_config=generation_config,
            safety_settings=safety_settings,
            # stream=False # Use stream=True for potentially very long analysis/transcription in future
        )

        print("Received response from Vertex AI.")
        # Debugging: Log raw response text length and type
        # print(f"Raw response type: {type(response.text)}, Length: {len(response.text)}")
        # print("Raw Response Text (first 500 chars):\n", response.text[:500])


        # Attempt to parse the JSON response
        try:
            # The response text should *only* contain the JSON data
            # due to response_mime_type="application/json"
            result = json.loads(response.text)
            # Basic validation: Check if it's a dictionary
            if not isinstance(result, dict):
                 # This case should be less likely with response_mime_type="application/json"
                 # but good to keep as a fallback check.
                 raise json.JSONDecodeError("Response is not a JSON object", response.text, 0)

            # Add more specific schema validation here if desired using libraries like jsonschema

            print("JSON parsing successful.")
            return result
        except json.JSONDecodeError as json_err:
            print(f"ERROR: Failed to decode JSON response from Vertex AI: {json_err}")
            print("--- Raw Response Text ---")
            print(response.text)
            print("--- End Raw Response Text ---")
            # Include candidate/safety info if available for debugging
            if hasattr(response, 'candidates') and response.candidates:
                 print(f"Finish Reason: {response.candidates[0].finish_reason}")
                 if response.candidates[0].safety_ratings:
                     print("Safety Ratings:")
                     for rating in response.candidates[0].safety_ratings:
                         print(f"  - {rating.category.name}: {rating.probability.name}") # Use .name for enums
                 # Check for citation metadata if relevant
                 if response.candidates[0].citation_metadata:
                      print("Citation Metadata:", response.candidates[0].citation_metadata)
            else:
                 print("No candidates found in response.")

            raise Exception(f"Vertex AI response was not valid JSON. See logs. Error: {json_err}. Raw text: {response.text[:200]}...") # Include snippet of raw text in exception

    except Exception as e:
        print(f"ERROR: An error occurred during the Vertex AI API call: {e}")
        print(traceback.format_exc()) # Print detailed traceback
        # Include details about the request if possible (be careful not to log sensitive data)
        print(f"Failed while processing URL: {youtube_url}")
        raise # Re-raise the exception after logging


# --- Main Execution Block ---
if __name__ == "__main__":
    # --- Get API Keys and Config (More Robustly) ---
    # Ensure required environment variables are set
    if not VERTEXAI_PROJECT_ID or not VERTEXAI_LOCATION or not YOUTUBE_API_KEY or YOUTUBE_API_KEY == 'YOUR_YOUTUBE_API_KEY':
        print("FATAL ERROR: Environment variables VERTEXAI_PROJECT_ID, VERTEXAI_LOCATION, and YOUTUBE_API_KEY must be set.")
        exit(1) # Exit if config is missing

    # --- Example Usage ---
    # Replace with the YouTube video URL you want to analyze
    # test_url = "https://www.youtube.com/watch?v= absolvoval" # Example HIIT workout
    test_url = "https://www.youtube.com/watch?v=xzqexC11dEM"
    # test_url = "https://www.youtube.com/watch?v=...' # Add your target URL here

    print(f"\n--- Analyzing YouTube URL: {test_url} ---")

    # Use force_refresh=True to bypass cache and generate a new analysis
    # Use force_refresh=False (default) to use cached data if available
    analysis_result = analyze_youtube_workout(test_url, force_refresh=False)

    print("\n--- Analysis Result ---")
    # Use json.dumps for pretty printing the final result dictionary
    print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
    print("--- End of Analysis ---")

    # --- Example of analyzing another video (optional) ---
    # test_url_2 = "https://www.youtube.com/watch?v=..."
    # print(f"\n--- Analyzing YouTube URL: {test_url_2} ---")
    # analysis_result_2 = analyze_youtube_workout(test_url_2, force_refresh=False)
    # print("\n--- Analysis Result 2 ---")
    # print(json.dumps(analysis_result_2, indent=2, ensure_ascii=False))
    # print("--- End of Analysis 2 ---")