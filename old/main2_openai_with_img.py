import base64
import json
import os
import requests
from urllib.parse import urlparse, parse_qs
import isodate  # For parsing ISO 8601 duration format
from googleapiclient.discovery import build
from openai import OpenAI


def analyze_youtube_workout(youtube_url, cache_dir='cache_2', force_refresh=False):
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

    # Get thumbnail image URL from metadata (prefer high resolution)
    thumbnails = metadata.get('thumbnails', {})
    # Prefer maxres if available, otherwise fall back to high resolution
    thumbnail_url = thumbnails.get('maxres', thumbnails.get('high', {})).get('url', '')
    thumbnail_base64 = None
    if thumbnail_url:
        thumbnail_base64 = get_thumbnail_base64(thumbnail_url, cache_dir, video_id, force_refresh)
    # Now send the metadata (and image if available) to OpenAI for workout classification
    try:
        analysis = classify_workout_with_openai(oai_client, metadata, thumbnail_base64)
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
            json.dump(data, f)
        print(f"Cached data to: {cache_path}")
    except Exception as e:
        print(f"Error caching data: {str(e)}")


def encode_image(image_path):
    """Encode image file to a Base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_thumbnail_base64(thumbnail_url, cache_dir, video_id, force_refresh=False):
    """
    Downloads the thumbnail image from the given URL, saves it as a jpg in cache,
    and returns a Base64-encoded string.
    """
    cache_path = os.path.join(cache_dir, f"{video_id}_thumbnail.jpg")
    if os.path.exists(cache_path) and not force_refresh:
        print(f"Loading thumbnail from cache: {cache_path}")
    else:
        try:
            response = requests.get(thumbnail_url)
            if response.status_code == 200:
                with open(cache_path, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded and cached thumbnail to: {cache_path}")
            else:
                print(f"Failed to download thumbnail. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error downloading thumbnail: {str(e)}")
            return None
    try:
        return encode_image(cache_path)
    except Exception as e:
        print(f"Error encoding thumbnail: {str(e)}")
        return None


def create_classification_prompt():
    """Create a detailed prompt for OpenAI to classify workout videos."""
    prompt = """You are a specialized AI fitness analyst. Your task is to analyze YouTube workout video metadata and the attached thumbnail image, and classify the workout into specific categories. Examine the title, description, comments, tags, channel information, and the visual cues from the thumbnail image to make your classification as accurate as possible.

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
1. Examine the title, description, tags, channel info, comments, and now the attached thumbnail image carefully.
2. Look for indicators of intensity, duration, exercise types, and visual cues.
3. Consider the channel's focus and typical content style.
4. When confidence is low for a category, mark it appropriately.
5. For categories that don't apply, provide empty arrays where appropriate.
6. For each workout, identify up to 3 most suitable "spirits" and "vibes" with an intensity value (0-1) for each.

CONFIDENCE LEVELS EXPLANATION:
- "very high": Strong explicit indicators in title, description, or visuals; central focus of the workout
- "high": Clear indicators or strong implicit evidence; confidently identifiable component
- "moderate": Some indicators or reasonable inference from context; likely but not certain
- "low": Minimal indicators or educated guess; possible but uncertain

Attached is the high-resolution thumbnail image of the video for additional visual context.
"""
    return prompt


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
            if len(comment) > 300:
                comment = comment[:300] + "...(truncated)"
            sections.append(f"{i}. {comment}")

    return "\n".join(sections)


def classify_workout_with_openai(oai_client, metadata, thumbnail_base64=None):
    """
    Use OpenAI to classify workout video based on metadata and the attached thumbnail image.
    """
    prompt = create_classification_prompt()
    formatted_metadata = format_metadata_for_analysis(metadata)

    # Build the list of message content items with valid types
    user_content = [
        {
            "type": "text",
            "text": f"Analyze this workout video metadata and classify it according to the schema:\n\n{formatted_metadata}"
        }
    ]
    # Attach image input if available, wrapping image_url as an object
    if thumbnail_base64:
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{thumbnail_base64}",
                "detail": "high"
            }
        })

    # JSON schema for strict validation
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "WorkoutAnalysis",
            "schema": {
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
                    }
                },
                "required": ["category", "subcategory"],
                "additionalProperties": False
            }
        }
    }

    response = oai_client.chat.completions.create(
        model="gpt-4o",
        response_format=response_format,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content}
        ]
    )
    result = json.loads(response.choices[0].message.content)
    return result


# Usage example
if __name__ == "__main__":
    # Use force_refresh=True to bypass cache and generate a new analysis
    result = analyze_youtube_workout("https://www.youtube.com/watch?v=xzqexC11dEM", force_refresh=True)
    print(json.dumps(result, indent=2))
