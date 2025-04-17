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


def analyze_youtube_workout(youtube_url, cache_dir='cache_16', force_refresh=False):
    """
    Analyzes a YouTube workout video and categorizes it according to various fitness vibes.

    Args:
        youtube_url (str): URL of the YouTube workout video
        cache_dir (str): Directory to store cached data
        force_refresh (bool): Whether to force fresh analysis even if cached data exists

    Returns:
        dict: Workout vibe information
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

    # Now send the metadata to OpenAI for workout vibe classification
    try:
        analysis = classify_workout_with_openai(oai_client, metadata)
        cache_data(analysis, analysis_cache_path)
        return analysis
    except Exception as e:
        return {"error": f"Failed to classify workout vibes: {str(e)}"}


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


from main16_vibes_and_schema import create_classification_prompt, RESPONSE_FORMAT


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
    """Use OpenAI to classify workout video vibes based on metadata with retry mechanism for rate limits."""
    prompt = create_classification_prompt()

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
                response_format=RESPONSE_FORMAT,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user",
                     "content": f"Analyze this workout video metadata and classify its vibe according to the schema:\n\n{formatted_metadata}"}
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
                    return {"error": f"Error classifying workout vibes with OpenAI after {max_retries} retries: {str(e)}"}
            else:
                # If it's not a rate limit error, don't retry
                return {"error": f"Error classifying workout vibes with OpenAI: {str(e)}"}

    # This should only happen if we exhaust all retries
    return {"error": "Failed to classify workout vibes after maximum retry attempts"}


# Usage example
if __name__ == "__main__":
    # Add force_refresh=True to ignore cache and create a new analysis
    result = analyze_youtube_workout("https://www.youtube.com/watch?v=zZD1H7XTTKc", force_refresh=True)
    print(json.dumps(result, indent=2))