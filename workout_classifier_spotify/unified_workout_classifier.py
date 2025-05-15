from openai import OpenAI, OpenAIError
import json
import os
import re
import platform
import time
import random
import io
from tqdm import tqdm
import subprocess
import zipfile
import shutil
import sys
import requests
import base64
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any
from PIL import Image
import requests
from io import BytesIO
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service

# Import classifier modules
from category_classifier import CATEGORY_PROMPT, CATEGORY_USER_PROMPT, CATEGORY_RESPONSE_FORMAT
from track_query import TRACK_PROMPT, TRACK_USER_PROMPT, TRACK_RESPONSE_FORMAT
from vibe_classifier import VIBE_PROMPT, VIBE_USER_PROMPT, VIBE_RESPONSE_FORMAT
from spirit_classifier import SPIRIT_PROMPT, SPIRIT_USER_PROMPT, SPIRIT_RESPONSE_FORMAT
from db_transformer import transform_to_db_structure

def analyse_spotify_workout(workout_json, openai_api_key,
                          cache_dir='cache', force_refresh=False, #!
                          enable_vibe=True, enable_spirit=True,
                          enable_web_search = True,
                          enable_image_in_meta=False):
    """
    Analyzes a workout playlist and classifies it according to enabled dimensions:
    1. Vibe (e.g., Warrior Workout, Zen Flow)
    2. Spirit (e.g., High-Energy & Intense, Flow & Rhythm)

    Args:
        workout_json (str): json
        openai_api_key (str, optional): OpenAI API key for accessing OpenAI API
        cache_dir (str): Directory to store cached data
        force_refresh (bool): Whether to force fresh analysis even if cached data exists
        enable_vibe (bool): Whether to classify workout by vibe
        enable_spirit (bool): Whether to classify workout by spirit

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
    video_id = workout_json.get('playlist').get('id')
    meta = extract_spotify_playlist_summary(workout_json)
    
    # using gpt and optionally the web scrapper to collect more information about tracks
    tracks_meta = tracks_descriptions(workout_json,
                                      video_id,
                                      enable_web_search,
                                      oai_client,
                                      cache_dir,
                                      force_refresh)
    tracks_meta_str = format_tracks_meta(tracks_meta)
    meta['text'] += "\n\nTracks Analysis:\n" + tracks_meta_str

    
    # Initialize combined analysis
    playlist = workout_json.get("playlist", {})
    combined_analysis = {
        "video_id": video_id,
        "video_url": playlist.get('external_urls', {}).get('spotify',None),
        "video_title": playlist.get("name"),
        "duration": calculate_total_duration_of_tracks(workout_json),
        'video_metadata': workout_json,
        'video_metadata_cleaned': meta,
        "channel_title": playlist.get('owner', {}).get('display_name',None),
        "poster_uri": meta['image']
        }

    if not enable_image_in_meta:
        del meta['image']


    # Define classifier configurations
    classifiers = [
        {
            "name": "category",
            "enabled": True,
            "cache_key": f"{video_id}_category_analysis.json",
            "system_prompt": CATEGORY_PROMPT,
            "user_prompt": CATEGORY_USER_PROMPT,
            "response_format": CATEGORY_RESPONSE_FORMAT
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
                        meta,
                        classifier["system_prompt"],
                        classifier["user_prompt"],
                        classifier["response_format"]
                    )
                    cache_data(analysis, cache_path)
            else:
                analysis = run_classifier(
                    oai_client,
                    meta,
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
        return return_error_analysis(error_message, workout_json)

# Other functions remain unchanged
def cache_data(data, cache_path):
    """Cache data to a JSON file."""
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Cached data to: {cache_path}")
    except Exception as e:
        print(f"Error caching data: {str(e)}")
               
def format_duration(seconds):
        if not seconds:
            return "Unknown duration"
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h:02}:{m:02}:{s:02}"

def extract_track_details(item: Dict[str, Any]) -> tuple[str, str, str, str]:
    """
    Extract artist name, track name, release year, and a formatted track summary from a playlist track item.
    Returns:
        (artist_name, track_name, release_year, summary_text)
    """
    def safe_get(dct, path, default=None):
        try:
            for key in path.split('.'):
                if key.isdigit():
                    dct = dct[int(key)]
                else:
                    dct = dct.get(key, {})
            return dct if dct not in ({}, []) else default
        except (IndexError, AttributeError, TypeError):
            return default

    track = item.get("track", {})
    try:
        artist = safe_get(track, "artists.0.name", "N/A")
        track_name = track.get("name", "N/A")
        release_date = safe_get(track, "album.release_date", "N/A")
        release_year = release_date.split("-")[0] if release_date else "N/A"

        duration_ms = track.get("duration_ms", 0)
        minutes = duration_ms // 60000
        seconds = (duration_ms % 60000) // 1000
        duration_str = f"{minutes}:{seconds:02d}"

        summary = f"- '{track_name}' by {artist}, from album '{safe_get(track, 'album.name', 'N/A')}' ({release_year})\n" \
                f"  Duration: {duration_str}, Explicit: {track.get('explicit', False)}, Popularity: {track.get('popularity', 'N/A')}"

        return artist, track_name, release_year, summary
    except:
        return "", "", "", ""

def safe_get(dct, path, default=None):
        try:
            for key in path.split('.'):
                if key.isdigit():
                    dct = dct[int(key)]
                else:
                    dct = dct.get(key, {})
            return dct if dct not in ({}, []) else default
        except (IndexError, AttributeError, TypeError):
            return default

def extract_video_id(raw_json: str, idx:int) -> str:
    schema = json.loads(raw_json)
    video_id = schema.get("playlist",{}).get("id")
    if not video_id:
        video_id = f"manual_{idx}"
        schema.setdefault("playlist", {})["id"] = video_id
    updated_raw_json = json.dumps(schema, separators=(',', ':'))
    return video_id, updated_raw_json

def extract_spotify_playlist_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts full playlist metadata and track summaries.
    Returns summary text and image URL.
    """

    playlist = data.get("playlist", {})
    tracks = safe_get(playlist, "tracks.items", [])

    summary_lines = [
        f"Playlist Name: {playlist.get('name', 'N/A')}",
        f"Description: {playlist.get('description', 'N/A')}",
        f"Query Used: {safe_get(data, 'search.query', 'N/A')} (Rank {safe_get(data, 'search.rank', 'N/A')})",
        f"Total Tracks: {safe_get(playlist, 'tracks.total', 'N/A')}",
        "",
        "Tracklist:"
    ]

    for idx, item in enumerate(tracks[:100]):
        _, _, _, track_summary = extract_track_details(item)
        summary_lines.append(f"{idx+1}. {track_summary}")

    image_url = safe_get(playlist, "images.0.url", None)
    try: del data['tracklist']
    except: pass
    try:
        data = delete_keys_with_market_inplace(data)
    except:pass

    return {
        "text": "\n".join(summary_lines),
        "image": image_url
    }

def delete_keys_with_market_inplace(obj):
    """
    Recursively deletes all keys containing 'market' from the object in-place.

    Args:
        obj (dict or list): The JSON object to modify.
    """
    if isinstance(obj, dict):
        keys_to_delete = [key for key in obj if 'market' in key.lower()]
        for key in keys_to_delete:
            del obj[key]
        for key in obj:
            delete_keys_with_market_inplace(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            delete_keys_with_market_inplace(item)


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

def return_error_analysis(error_message, workout_json=None):
    if workout_json:
        playlist = workout_json.get("playlist", {})
        sample_id = playlist.get("id")
        video_url = playlist.get("external_urls", {}).get("spotify")
        video_title = playlist.get("name")
        channel_title = playlist.get("owner", {}).get("display_name")
        duration = format_duration(calculate_total_duration_of_tracks(workout_json))
        video_metadata_cleaned = extract_spotify_playlist_summary(workout_json)
    else:
        sample_id = video_url = video_title = channel_title = duration = video_metadata_cleaned = None

    return {
        "error": error_message,
        "reviewable": False,
        "review_comment": f"processing_error {error_message}",
        "video_id": sample_id,
        "video_url": video_url,
        "video_title": video_title,
        "duration": duration,
        "video_metadata": workout_json,
        "video_metadata_cleaned": video_metadata_cleaned,
        "channel_title": channel_title
    }

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 13_2 like Mac OS X)")



    service = get_or_install_chromedriver()
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def collect_snippets_batch(queries: list, delay: float = 3.0, max_wait: int = 10, retry_interval: float = 1.0) -> list:
    results = []
    driver = create_driver()

    for query in tqdm(queries, desc="Web search:"):
        try:
            # Step 1: Go to homepage
            driver.get("https://duckduckgo.com")
            time.sleep(0.5)

            # Step 2: Enter query into input field
            search_box = driver.find_element(By.NAME, "q")
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)

            time.sleep(delay)

            snippets = []
            start_time = time.time()

            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
                driver.execute_script("document.body.dispatchEvent(new Event('mousemove'));")
                time.sleep(0.5)

                elements = driver.find_elements(By.XPATH, '//div[@data-result="snippet"]')

                if elements:
                    snippets = [el.text.strip() for el in elements[:5] if el.text.strip()]
                    # print(snippets)
                    break

                if time.time() - start_time > max_wait:
                    print(f"[Timeout] No snippets for query after {max_wait}s: {query}")
                    break

                time.sleep(retry_interval)

            results.append(" ".join(snippets))

        except Exception as e:
            print(f"[Error] Query failed: {query} | Error: {e}")
            results.append("")

    driver.quit()
    return results

def tracks_descriptions(workout_json: Dict[str, Any],
                        video_id: str,
                        enable_web_search: bool,
                        oai_client: Any,
                        cache_dir: str,
                        force_refresh: bool) -> Dict[str, Any]:
    classifier = {
        "cache_key": f"{video_id}_tracks_analysis.json",
        "system_prompt": TRACK_PROMPT,
        "user_prompt": TRACK_USER_PROMPT,
        "response_format": TRACK_RESPONSE_FORMAT
    }

    cache_path = os.path.join(cache_dir, classifier["cache_key"])
    if not force_refresh and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            print(f"Loaded tracks enriched meta from {cache_path}")
            return json.load(f)

    items = workout_json.get("playlist", {}).get("tracks", {}).get("items", [])
    basic_meta = [extract_track_details(item)[:3] for item in items]

    if enable_web_search:
        try:
            queries = [
                f"{track_name} by {artist} {year} lyrics meaning genre bpm mood"
                for artist, track_name, year in basic_meta
            ]
            queries = queries[:5]
            snippets = collect_snippets_batch(queries, delay=.5)

            enriched_meta = []
            for (artist, track_name, year), snippet in zip(basic_meta, snippets):
                enriched_meta.append({
                    "key": f"{artist}_{track_name}",
                    "text": f"Track: '{track_name}' by {artist} ({year})\nSnippet: {snippet}"
                })
        except:
            enriched_meta = [
            {
                "key": f"{artist}_{track_name}",
                "text": f"Track: '{track_name}' by {artist} ({year})"
            }
            for artist, track_name, year in basic_meta
        ][:5]
    else:
        enriched_meta = [
            {
                "key": f"{artist}_{track_name}",
                "text": f"Track: '{track_name}' by {artist} ({year})"
            }
            for artist, track_name, year in basic_meta
        ][:5]

    # One call per track
    analysis = {}
    for item in enriched_meta:
        try:
            result = run_classifier(
                oai_client,
                item,
                classifier["system_prompt"],
                classifier["user_prompt"],
                classifier["response_format"]
            )
            analysis[item["key"]] = result
        except Exception as e:
            print(f"[Error] GPT classification failed for {item['key']}: {e}")

    cache_data(analysis, cache_path)
    return analysis

def format_tracks_meta(tracks_meta: Dict[str, Dict[str, Any]]) -> str:
    """
    Formats the track metadata dictionary into a human-readable text block.
    Each track's analysis is rendered as a section with its details.
    """
    lines = []
    for track_key, analysis in tracks_meta.items():
        lines.append(f"\nTrack: {track_key}")
        for field, value in analysis.items():
            lines.append(f"  {field}: {value}")
    return "\n".join(lines)

def calculate_total_duration_of_tracks(workout_json):
    """
    Calculate the total duration in seconds of all tracks in the JSON.
    Expects structure: playlist.tracks.items[i].track.duration_ms

    Args:
        workout_json (dict): Parsed JSON object

    Returns:
        float: Total duration of all tracks in seconds
    """
    if isinstance(workout_json, str):
        try:
            workout_json = json.loads(workout_json)
        except json.JSONDecodeError:
            return 0

    try:
        items = workout_json["playlist"]["tracks"]["items"]
    except (KeyError, TypeError):
        return 0

    total_ms = 0
    for item in items:
        try:
            duration = item["track"]["duration_ms"]
            if isinstance(duration, (int, float)):
                total_ms += duration
        except (KeyError, TypeError):
            continue

    return int(total_ms/1000)

def detect_chrome_binary():
    candidates = [
        "google-chrome",
        "chromium-browser",
        "chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ]

    for candidate in candidates:
        try:
            output = subprocess.check_output([candidate, "--version"], stderr=subprocess.STDOUT).decode().strip()
            if "Chrome" in output or "Chromium" in output:
                return candidate, output
        except Exception:
            continue
    return None, None

def get_chrome_version(binary_path):
    try:
        output = subprocess.check_output([binary_path, "--version"], stderr=subprocess.STDOUT).decode().strip()
        version = next(part for part in output.split() if part[0].isdigit())
        return version
    except Exception as e:
        print(f"[Error] Failed to get Chrome version: {e}")
        return None
    
def download_chromedriver(version, dest_path, os_type):
    print(f"Downloading chromedriver for version {version}...")
    base_url = "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing"
    platform_key = {
        "linux": "linux64",
        "windows": "win64"
    }

    if os_type not in platform_key:
        raise Exception(f"Unsupported OS: {os_type}")

    url = f"{base_url}/{version}/{platform_key[os_type]}/chromedriver-{platform_key[os_type]}.zip"
    zip_path = os.path.join(dest_path, "chromedriver.zip")

    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Failed to download chromedriver from {url}")
    with open(zip_path, "wb") as f:
        f.write(r.content)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_path)
    os.remove(zip_path)

    # Move actual binary to consistent path
    inner = os.path.join(dest_path, "chromedriver-" + platform_key[os_type], "chromedriver")
    target = os.path.join(dest_path, "chromedriver")
    shutil.move(inner, target)
    shutil.rmtree(os.path.join(dest_path, "chromedriver-" + platform_key[os_type]))

    os.chmod(target, 0o755)
    print(f"Chromedriver ready at {target}")
    return target

def get_or_install_chromedriver(dest_dir="chromedriver_bin"):
    os_type = platform.system().lower()
    if os_type not in ["linux", "windows"]:
        raise Exception(f"Unsupported OS: {os_type}")

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    driver_path = os.path.join(dest_dir, "chromedriver")
    if os_type == "windows":
        driver_path += ".exe"

    if os.path.exists(driver_path):
        return Service(driver_path)

    chrome_path, chrome_output = detect_chrome_binary()
    if not chrome_path:
        raise Exception("Could not detect a Chrome or Chromium binary automatically.")

    chrome_version = get_chrome_version(chrome_path)
    if not chrome_version:
        raise Exception("Could not determine Chrome version.")

    major_version = chrome_version.split('.')[0]
    print(f"Detected Chrome: {chrome_output} → using major version {major_version}")

    # Look up the latest full version via metadata
    meta_url = f"https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
    meta = requests.get(meta_url).json()

    # This returns a stable version for download
    full_version = meta["channels"]["Stable"]["version"]

    return Service(download_chromedriver(full_version, dest_dir, os_type))