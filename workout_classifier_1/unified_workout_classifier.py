from googleapiclient.discovery import build
from openai import OpenAI, OpenAIError
import json
import os
import re
import time
import random
from urllib.parse import urlparse, parse_qs
import isodate  # For parsing ISO 8601 duration format

# Import classifier modules
from category_classifier import CATEGORY_PROMPT, CATEGORY_USER_PROMPT, CATEGORY_RESPONSE_FORMAT
from fitness_level_classifier import FITNESS_LEVEL_PROMPT, FITNESS_LEVEL_USER_PROMPT, FITNESS_LEVEL_RESPONSE_FORMAT
from vibe_classifier import VIBE_PROMPT, VIBE_USER_PROMPT, VIBE_RESPONSE_FORMAT
from spirit_classifier import SPIRIT_PROMPT, SPIRIT_USER_PROMPT, SPIRIT_RESPONSE_FORMAT
from equipment_classifier import EQUIPMENT_PROMPT, EQUIPMENT_USER_PROMPT, EQUIPMENT_RESPONSE_FORMAT
from db_transformer import transform_to_db_structure


def analyze_youtube_workout(youtube_url, youtube_api_key, openai_api_key,
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
        youtube_url (str): URL of the YouTube workout video
        youtube_api_key (str, optional): YouTube API key for accessing YouTube API
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
    # Initialize clients
    try:
        oai_client = OpenAI(api_key=openai_api_key)
        youtube_client = build('youtube', 'v3', developerKey=youtube_api_key)
    except Exception as e:
        return {"error": f"Failed to initialize API clients: {str(e)}"}

    # Extract video ID
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return {"error": "Invalid YouTube URL. Could not extract video ID."}

    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)

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

    # Format metadata for analysis
    formatted_metadata = format_metadata_for_analysis(metadata)

    # Initialize combined analysis
    combined_analysis = {
        "video_id": video_id,
        "video_url": youtube_url,
        "video_title": metadata.get('title', ''),
        "channel_title": metadata.get('channelTitle', ''),
        "duration": metadata.get('durationFormatted', ''),
        "duration_minutes": round(metadata.get('duration', 0) / 60, 1),  # Convert seconds to minutes
        "reviewable": True  # Default to reviewable unless errors occur
    }

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
                    analysis = run_classifier(
                        oai_client,
                        formatted_metadata,
                        classifier["system_prompt"],
                        classifier["user_prompt"],
                        classifier["response_format"]
                    )
                    cache_data(analysis, cache_path)
            else:
                analysis = run_classifier(
                    oai_client,
                    formatted_metadata,
                    classifier["system_prompt"],
                    classifier["user_prompt"],
                    classifier["response_format"]
                )
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
        return {
            "error": error_message,
            "reviewable": False,
            "review_comment": "processing_error",
            "video_id": video_id,
            "video_url": youtube_url,
            "video_title": metadata.get('title', ''),
            "channel_title": metadata.get('channelTitle', ''),
            "duration": metadata.get('durationFormatted', '')
        }


# Other functions remain unchanged
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

        # Format duration directly here (integrated)
        hours, remainder = divmod(duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            duration_formatted = f"{minutes}:{seconds:02d}"

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
            'durationFormatted': duration_formatted,
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


def cache_data(data, cache_path):
    """Cache data to a JSON file."""
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Cached data to: {cache_path}")
    except Exception as e:
        print(f"Error caching data: {str(e)}")


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
        # Truncate very long descriptions to first 3000 chars
        description = metadata.get('description', '')
        if len(description) > 3000:
            sections.append(f"{description[:3000]}...(truncated)")
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


def run_classifier(oai_client, formatted_metadata, system_prompt, user_prompt, response_format, max_retries=3):
    """
    Generic function to run a classifier through OpenAI API with improved error handling.

    Args:
        oai_client: OpenAI client
        formatted_metadata: Formatted video metadata
        system_prompt: System prompt for the classifier
        user_prompt: User prompt for the classifier
        response_format: Expected response format
        max_retries: Maximum number of retry attempts for API and parsing issues

    Returns:
        dict: Classification results or error information
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_prompt}\n\n{formatted_metadata}"}
    ]

    # JSON parsing retries counter
    parsing_retries = 0

    while parsing_retries < max_retries:
        try:
            # Try to get response from OpenAI with rate limit handling
            api_response = openai_call_with_retry(oai_client, "gpt-4o", messages, response_format)

            # If we got here, the API call was successful
            return api_response

        except json.JSONDecodeError as json_error:
            # Handle JSON parsing errors specifically
            parsing_retries += 1
            print(f"JSON parsing error (attempt {parsing_retries}/{max_retries}): {str(json_error)}")

            # If we've reached max retries, return an error
            if parsing_retries >= max_retries:
                return {
                    "error": f"JSON parsing error after {max_retries} attempts: {str(json_error)}",
                    "review_comment": "json_parsing_error"
                }

            # Wait a short time before retrying
            time.sleep(1)

        except OpenAIError as api_error:
            # Check if it's a rate limit error
            error_str = str(api_error)
            if "rate_limit_exceeded" in error_str or "Rate limit reached" in error_str:
                return {
                    "error": f"Rate limit error: {str(api_error)}",
                    "review_comment": "rate_limit_error"
                }
            else:
                # For other OpenAI errors, don't retry
                return {
                    "error": f"OpenAI API error: {str(api_error)}",
                    "review_comment": "processing_error"
                }

        except Exception as e:
            # For any other exceptions
            return {
                "error": f"Error with classifier: {str(e)}",
                "review_comment": "processing_error"
            }

    # This should not be reached but just in case
    return {
        "error": "Unexpected error in classifier",
        "review_comment": "processing_error"
    }


def openai_call_with_retry(oai_client, model, messages, response_format):
    """
    Helper function to make OpenAI API calls with retry for rate limits.
    Now properly propagates JSON parsing errors to the calling function.
    """
    # Maximum number of retries for rate limits
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

            # Get the response content
            response_content = response.choices[0].message.content

            # Let JSON parsing errors propagate to caller for handling
            parsed_response = json.loads(response_content)
            return parsed_response

        except json.JSONDecodeError as json_error:
            # Propagate JSON parsing errors to caller
            raise json_error

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
                    raise OpenAIError(f"Rate limit error after {max_retries} retries: {str(e)}")
            else:
                # If it's not a rate limit error, don't retry
                raise OpenAIError(f"OpenAI API error: {str(e)}")

    # This should only happen if we exhaust all retries
    raise Exception("Failed after maximum retry attempts")
