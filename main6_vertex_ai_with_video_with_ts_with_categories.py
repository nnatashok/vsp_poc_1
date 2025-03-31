import json, os, traceback
import isodate
from googleapiclient.discovery import build
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig, HarmCategory, HarmBlockThreshold

from main6_extract_utilities import extract_video_id
from main6_prompt import create_classification_prompt_video

# Configurations
VERTEXAI_PROJECT_ID = 'norse-sector-250410'
VERTEXAI_LOCATION = 'us-central1'
YOUTUBE_API_KEY = 'AIzaSyCkpiTfTUvNVNmPcyw8ZO1NOn_0b_LV8RA'
VERTEXAI_MODEL_NAME = "gemini-2.5-pro-exp-03-25"

# Constants
CACHE_DIR = 'cache_6'
MAX_DESC_LEN = 1500
MAX_COMMENT_LEN = 250
MAX_CHAN_DESC_LEN = 500
TARGET_SEGMENT_DURATION = 10

# Initialize services
vertexai.init(project=VERTEXAI_PROJECT_ID, location=VERTEXAI_LOCATION)
vertex_model = GenerativeModel(VERTEXAI_MODEL_NAME)
youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def analyze_youtube_workout(youtube_url, cache_dir=CACHE_DIR, force_refresh=False):
    """Analyze a YouTube workout video focusing on its central 10 seconds."""
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return {"error": "Invalid YouTube URL."}
    print(f"Video ID: {video_id}")
    os.makedirs(cache_dir, exist_ok=True)

    analysis_cache = os.path.join(cache_dir, f"{video_id}_vertex_video_analysis_center10s.json")
    if os.path.exists(analysis_cache) and not force_refresh:
        try:
            with open(analysis_cache, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Cache load error: {e}")

    metadata_cache = os.path.join(cache_dir, f"{video_id}_metadata.json")
    metadata = None
    if os.path.exists(metadata_cache) and not force_refresh:
        try:
            with open(metadata_cache, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print("Loaded metadata from cache.")
        except Exception as e:
            print(f"Metadata cache error: {e}")
    if metadata is None:
        metadata = fetch_video_metadata(youtube_client, video_id)
        if "error" in metadata:
            return metadata
        cache_data(metadata, metadata_cache)

    print("Starting Vertex AI classification...")
    analysis = classify_workout_with_vertexai_video(vertex_model, metadata, youtube_url)
    cache_data(analysis, analysis_cache)
    return analysis


def fetch_video_metadata(youtube_client, video_id):
    """Fetch metadata for the video."""
    print(f"Fetching metadata for {video_id}")
    video_response = youtube_client.videos().list(
        part='snippet,contentDetails,statistics,player', id=video_id
    ).execute()
    if not video_response.get('items'):
        return {"error": f"Video not found ({video_id})"}
    video_data = video_response['items'][0]
    snippet = video_data.get('snippet', {})
    content_details = video_data.get('contentDetails', {})
    statistics = video_data.get('statistics', {})
    player = video_data.get('player', {})

    channel_id = snippet.get('channelId')
    channel_snippet, channel_stats = {}, {}
    if channel_id:
        channel_response = youtube_client.channels().list(
            part='snippet,statistics', id=channel_id
        ).execute()
        if channel_response.get('items'):
            channel_data = channel_response['items'][0]
            channel_snippet = channel_data.get('snippet', {})
            channel_stats = channel_data.get('statistics', {})

    comments = []
    try:
        comments_response = youtube_client.commentThreads().list(
            part='snippet', videoId=video_id, order='relevance',
            textFormat='plainText', maxResults=5
        ).execute()
        comments = [item['snippet']['topLevelComment']['snippet']['textDisplay']
                    for item in comments_response.get('items', [])]
    except Exception as e:
        print(f"Comments fetch error: {e}")

    duration_iso = content_details.get('duration', 'PT0S')
    try:
        duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
    except Exception as e:
        print(f"Duration parse error: {e}")
        duration_seconds = 0

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
        'likeCount': int(statistics.get('likeCount', 0)) if 'likeCount' in statistics else None,
        'commentCount': int(statistics.get('commentCount', 0)) if 'commentCount' in statistics else None,
        'thumbnails': snippet.get('thumbnails', {}),
        'embedHtml': player.get('embedHtml', ''),
        'topComments': comments,
        'channelSubscriberCount': int(channel_stats.get('subscriberCount', 0)) if channel_stats.get('subscriberCount') and not channel_stats.get('hiddenSubscriberCount', False) else None,
        'channelVideoCount': int(channel_stats.get('videoCount', 0))
    }
    print("Metadata fetched.")
    return metadata

def format_duration(seconds):
    """Convert seconds to HH:MM:SS or MM:SS."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "Invalid"
    seconds = int(round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

def cache_data(data, cache_path):
    """Cache data to a JSON file."""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Cached to {cache_path}")
    except Exception as e:
        print(f"Cache error: {e}")

def format_metadata_for_analysis(metadata):
    """Format metadata for the prompt."""
    parts = []
    parts.append("## VIDEO INFORMATION")
    parts.append(f"Title: {metadata.get('title', 'N/A')}")
    parts.append(f"Channel: {metadata.get('channelTitle', 'N/A')}")
    parts.append(f"Duration: {metadata.get('durationFormatted', 'N/A')} ({metadata.get('duration', 0):.2f}s)")
    parts.append(f"Published: {metadata.get('publishedAt', 'N/A')}")
    parts.append(f"Views: {metadata.get('viewCount', 0):,}")
    like_count = metadata.get('likeCount')
    parts.append(f"Likes: {like_count:,}" if like_count is not None else "Likes: N/A")
    comment_count = metadata.get('commentCount')
    parts.append(f"Comments: {comment_count:,}" if comment_count is not None else "Comments: N/A")
    if metadata.get('tags'):
        parts.append("\n## TAGS")
        parts.append(", ".join(metadata.get('tags')))
    if metadata.get('description'):
        parts.append("\n## DESCRIPTION")
        desc = metadata.get('description')
        parts.append(f"{desc[:MAX_DESC_LEN]}...(truncated)" if len(desc) > MAX_DESC_LEN else desc)
    parts.append("\n## CHANNEL INFO")
    parts.append(f"Channel: {metadata.get('channelTitle', 'N/A')}")
    subs = metadata.get('channelSubscriberCount')
    parts.append(f"Subscribers: {subs:,}" if subs is not None else "Subscribers: Hidden/N/A")
    parts.append(f"Videos: {metadata.get('channelVideoCount', 0):,}")
    chan_desc = metadata.get('channelDescription', '')
    if chan_desc:
        parts.append(f"Channel desc: {chan_desc[:MAX_CHAN_DESC_LEN]}{'...' if len(chan_desc)>MAX_CHAN_DESC_LEN else ''}")
    comments = metadata.get('topComments', [])
    if comments:
        parts.append("\n## TOP COMMENTS")
        for i, comment in enumerate(comments[:5], 1):
            cmt = str(comment)
            parts.append(f"{i}. {cmt[:MAX_COMMENT_LEN]}{'...(truncated)' if len(cmt)>MAX_COMMENT_LEN else ''}")
    return "\n".join(parts)

def classify_workout_with_vertexai_video(model, metadata, youtube_url):
    """Classify the workout video using Vertex AI."""
    sys_prompt = create_classification_prompt_video()
    formatted_metadata = format_metadata_for_analysis(metadata)
    total_duration = metadata.get('duration', 0)
    video_part = None

    if total_duration > 0:
        half_seg = TARGET_SEGMENT_DURATION / 2.0
        midpoint = total_duration / 2.0
        start = max(0.0, midpoint - half_seg)
        end = min(total_duration, midpoint + half_seg)
        if end - start < TARGET_SEGMENT_DURATION and total_duration >= TARGET_SEGMENT_DURATION:
            if start == 0.0:
                end = min(total_duration, TARGET_SEGMENT_DURATION)
            elif end == total_duration:
                start = max(0.0, total_duration - TARGET_SEGMENT_DURATION)
        if start >= end:
            start, end = 0.0, min(total_duration, 0.1)
        start_int, end_int = int(start), int(end)
        start_nanos = int((start - start_int) * 1e9)
        end_nanos = int((end - end_int) * 1e9)
        seg_metadata = {"start_offset": {"seconds": start_int, "nanos": start_nanos},
                        "end_offset": {"seconds": end_int, "nanos": end_nanos}}
        print(f"Segment: {start:.1f}s to {end:.1f}s")
        try:
            video_part = Part.from_uri(uri=youtube_url, mime_type="video/youtube", video_metadata=seg_metadata)
        except TypeError as e:
            print("Segment info unsupported, using full video.")
            video_part = Part.from_uri(uri=youtube_url, mime_type="video/youtube")
    else:
        print("Unknown duration; analyzing full video.")
        video_part = Part.from_uri(uri=youtube_url, mime_type="video/youtube")

    prompt_parts = [Part.from_text(sys_prompt + "\n\n" + formatted_metadata), video_part]
    gen_config = GenerationConfig(
        temperature=0.2,
        max_output_tokens=8192,
        response_mime_type="application/json",
    )
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }
    print("Sending request to Vertex AI...")
    try:
        response = model.generate_content(prompt_parts, generation_config=gen_config, safety_settings=safety)
        try:
            result = json.loads(response.text)
            if not isinstance(result, dict):
                raise json.JSONDecodeError("Not a JSON object", response.text, 0)
            return result
        except json.JSONDecodeError as je:
            print("JSON decode error:", je)
            print("Response (truncated):", response.text[:200])
            raise Exception(f"Invalid JSON: {je}. Response: {response.text[:200]}")
    except Exception as e:
        print("Vertex AI error:", e)
        print(traceback.format_exc())
        raise

if __name__ == "__main__":
    test_url = "https://www.youtube.com/watch?v=xzqexC11dEM"
    print(f"Analyzing: {test_url}")
    result = analyze_youtube_workout(test_url, force_refresh=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
