import re

import pandas as pd
import csv
import json
import os
import argparse
import time
from tqdm import tqdm
from multiprocessing import Pool
from unified_workout_classifier import analyze_youtube_workout, extract_video_id, fetch_video_metadata
from db_transformer import transform_to_db_structure
from env_utils import load_api_keys


def is_youtube_url(url):
    """Check if a URL is a YouTube video URL (not a playlist)."""
    if not isinstance(url, str):
        return False

    youtube_pattern = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+$'
    if not re.match(youtube_pattern, url):
        return False

    # Exclude playlist URLs
    if 'list=' in url or 'playlist' in url:
        return False

    return True


def analyze_workout(args):
    """
    Process a single workout video URL - for multiprocessing pool.

    Args:
        args (tuple): Contains (url, youtube_api_key, openai_api_key, enabled_features, process_id)

    Returns:
        dict or None: Analysis results or None if failed
    """
    url, youtube_api_key, openai_api_key, enabled_features, process_id = args

    if not is_youtube_url(url):
        print(f"Process {process_id}: Skipping invalid URL: {url}")
        return None

    video_id = extract_video_id(url)
    if not video_id:
        print(f"Process {process_id}: Could not extract video ID from URL: {url}")
        return None

    try:
        # Import YouTube API client to fetch metadata
        from googleapiclient.discovery import build
        youtube_client = build('youtube', 'v3', developerKey=youtube_api_key)

        # Fetch video metadata first
        video_metadata = fetch_video_metadata(youtube_client, video_id)

        # Check if metadata fetching was successful
        if "error" in video_metadata:
            print(f"Process {process_id}: Error fetching video metadata for {video_id}: {video_metadata['error']}")
            return None

        # Analyze the workout with specified features
        print(f"Process {process_id}: Analyzing workout: {url}")
        result = analyze_youtube_workout(
            url,
            youtube_api_key=youtube_api_key,
            openai_api_key=openai_api_key,
            force_refresh=False,
            enable_category=enabled_features['category'],
            enable_fitness_level=enabled_features['fitness_level'],
            enable_vibe=enabled_features['vibe'],
            enable_spirit=enabled_features['spirit'],
            enable_equipment=enabled_features['equipment']
        )

        # Check if analysis was successful
        if "error" in result:
            print(f"Process {process_id}: Error analyzing workout {video_id}: {result['error']}")
            return None

        # Add video_metadata to the result
        result['video_metadata'] = video_metadata

        # Transform to database structure
        db_structure = transform_to_db_structure(result)

        # Prepare result data
        output_data = {
            'video_id': db_structure.get('video_id', ''),
            'video_url': db_structure.get('video_url', ''),
            'video_title': db_structure.get('video_title', ''),
            'channel_title': db_structure.get('channel_title', ''),
            'duration': db_structure.get('duration', ''),
            'duration_minutes': db_structure.get('duration_minutes', 0),
            'category': db_structure.get('category', ''),
            'subcategory': db_structure.get('subcategory', ''),
            'secondary_category': db_structure.get('secondary_category', ''),
            'secondary_subcategory': db_structure.get('secondary_subcategory', ''),
            'fitness_level': db_structure.get('fitness_level', ''),
            'secondary_fitness_level': db_structure.get('secondary_fitness_level', ''),
            'tertiary_fitness_level': db_structure.get('tertiary_fitness_level', ''),
            'primary_equipment': db_structure.get('primary_equipment', ''),
            'secondary_equipment': db_structure.get('secondary_equipment', ''),
            'tertiary_equipment': db_structure.get('tertiary_equipment', ''),
            'primary_spirit': db_structure.get('primary_spirit', ''),
            'secondary_spirit': db_structure.get('secondary_spirit', ''),
            'primary_vibe': db_structure.get('primary_vibe', ''),
            'secondary_vibe': db_structure.get('secondary_vibe', ''),
            'reviewable': db_structure.get('reviewable', False),
            'review_comment': db_structure.get('review_comment', ''),
            'primary_technique_difficulty': db_structure.get('primary_technique_difficulty', ''),
            'secondary_technique_difficulty': db_structure.get('secondary_technique_difficulty', ''),
            'tertiary_technique_difficulty': db_structure.get('tertiary_technique_difficulty', ''),
            'primary_effort_difficulty': db_structure.get('primary_effort_difficulty', ''),
            'secondary_effort_difficulty': db_structure.get('secondary_effort_difficulty', ''),
            'tertiary_effort_difficulty': db_structure.get('tertiary_effort_difficulty', ''),
            'full_analysis_json': json.dumps(result, sort_keys=True, indent=2)
        }

        print(f"Process {process_id}: Successfully analyzed workout: {video_id}")
        return output_data

    except Exception as e:
        print(f"Process {process_id}: Error processing workout {video_id}: {str(e)}")
        return None


def write_results_to_csv(results, output_csv_path):
    """
    Write analysis results to CSV file.
    Filter out duplicates based on video_id (keeping the first occurrence).

    Args:
        results (list): List of analysis results
        output_csv_path (str): Path to output CSV file
    """
    # Filter out None results (failed analyses)
    valid_results = [r for r in results if r is not None]

    # Deduplicate results based on video_id
    unique_results = {}
    for result in valid_results:
        video_id = result.get('video_id')
        if video_id and video_id not in unique_results:
            unique_results[video_id] = result

    # Write to output CSV
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        # Define field names for the CSV header
        fieldnames = [
            'video_id', 'video_url', 'video_title', 'channel_title', 'duration', 'duration_minutes',
            'category', 'subcategory', 'secondary_category', 'secondary_subcategory',
            'fitness_level', 'secondary_fitness_level', 'tertiary_fitness_level',
            'primary_equipment', 'secondary_equipment', 'tertiary_equipment',
            'primary_spirit', 'secondary_spirit',
            'primary_vibe', 'secondary_vibe',
            'reviewable', 'review_comment',
            'primary_technique_difficulty', 'secondary_technique_difficulty', 'tertiary_technique_difficulty',
            'primary_effort_difficulty', 'secondary_effort_difficulty', 'tertiary_effort_difficulty',
            'full_analysis_json'
        ]

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Write data rows
        for result in unique_results.values():
            writer.writerow(result)

    return unique_results


def process_workouts_csv_mp(input_csv_path, output_csv_path, max_workouts=None, num_processes=10,
                            enable_category=True, enable_fitness_level=True,
                            enable_vibe=True, enable_spirit=True, enable_equipment=True):
    """
    Process YouTube workout URLs from a CSV file using multiprocessing.

    Args:
        input_csv_path (str): Path to input CSV file
        output_csv_path (str): Path to output CSV file
        max_workouts (int, optional): Maximum number of workouts to process
        num_processes (int): Number of parallel processes to use
        enable_category (bool): Whether to analyze workout categories
        enable_fitness_level (bool): Whether to analyze fitness levels
        enable_vibe (bool): Whether to analyze workout vibes
        enable_spirit (bool): Whether to analyze workout spirits
        enable_equipment (bool): Whether to analyze required equipment
    """
    start_time = time.time()

    # Load API keys
    api_keys = load_api_keys()
    youtube_api_key = api_keys.get('YOUTUBE_API_KEY')
    openai_api_key = api_keys.get('OPENAI_API_KEY')

    # Output API key status
    if youtube_api_key:
        print(f"YouTube API key found: {youtube_api_key[:5]}...{youtube_api_key[-5:]}")
    else:
        print("WARNING: YouTube API key not found in environment variables")

    if openai_api_key:
        print(f"OpenAI API key found: {openai_api_key[:5]}...{openai_api_key[-5:]}")
    else:
        print("WARNING: OpenAI API key not found in environment variables")

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_csv_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Read the input CSV file
    try:
        df = pd.read_csv(input_csv_path)
        print(f"Successfully read CSV file with {len(df)} rows")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    # Convert column names to strings
    df.columns = df.columns.astype(str)

    # Get all columns
    columns = df.columns.tolist()
    if len(columns) < 1:
        print(f"CSV file has insufficient columns: {columns}")
        return

    # Collect YouTube URLs from all columns
    all_urls = []
    for _, row in df.iterrows():
        for col in columns:
            if is_youtube_url(str(row[col])):
                all_urls.append(str(row[col]))

    # Deduplicate URLs based on video_id
    unique_urls = {}
    for url in all_urls:
        video_id = extract_video_id(url)
        if video_id and video_id not in unique_urls:
            unique_urls[video_id] = url

    deduplicated_urls = list(unique_urls.values())

    total_urls = len(all_urls)
    unique_url_count = len(deduplicated_urls)
    print(f"Found {total_urls} total YouTube URLs in the CSV")
    print(f"After deduplication: {unique_url_count} unique URLs")

    # Limit the number of workouts to process if specified
    if max_workouts and max_workouts > 0:
        deduplicated_urls = deduplicated_urls[:max_workouts]
        print(f"Limited to processing {max_workouts} URLs")

    # Check if we have more processes than URLs
    actual_processes = min(num_processes, max(1, len(deduplicated_urls)))
    if actual_processes != num_processes:
        print(f"Using {actual_processes} processes for {len(deduplicated_urls)} URLs")

    # Set up enabled features dictionary
    enabled_features = {
        'category': enable_category,
        'fitness_level': enable_fitness_level,
        'vibe': enable_vibe,
        'spirit': enable_spirit,
        'equipment': enable_equipment
    }

    # Create batches of URLs for each process
    batch_size = len(deduplicated_urls) // actual_processes
    if len(deduplicated_urls) % actual_processes != 0:
        batch_size += 1

    # Split URLs into batches
    url_batches = []
    for i in range(0, len(deduplicated_urls), batch_size):
        batch = deduplicated_urls[i:i + batch_size]
        url_batches.append(batch)

    # Print batch information
    print(f"Split {len(deduplicated_urls)} URLs into {len(url_batches)} batches")

    # Prepare arguments for each process
    process_args = []
    for i, batch in enumerate(url_batches):
        # Flatten the batch into individual tasks with process ID
        for url in batch:
            process_args.append((url, youtube_api_key, openai_api_key, enabled_features, i))

    # Process URLs in parallel using a pool with progress bar
    print(f"Starting parallel processing with {actual_processes} processes")

    # Add a global progress bar for all tasks
    with tqdm(total=len(process_args), desc="Overall Progress") as pbar:
        with Pool(processes=actual_processes) as pool:
            # Use imap_unordered with tqdm for progress tracking
            results = []
            for result in pool.imap_unordered(analyze_workout, process_args):
                results.append(result)
                pbar.update(1)

    # Calculate total duration
    end_time = time.time()
    duration = end_time - start_time

    # Write results to CSV (with deduplication)
    print(f"Processing complete. Writing results to {output_csv_path}")
    unique_results = write_results_to_csv(results, output_csv_path)

    # Count successful analyses
    successful_analyses = len(unique_results)

    # Count reviewable/non-reviewable
    reviewable_count = sum(1 for result in unique_results.values() if result.get('reviewable', False))
    non_reviewable_count = successful_analyses - reviewable_count

    print(f"\nProcessing complete!")
    print(f"Total URLs found: {total_urls}")
    print(f"Unique URLs found: {unique_url_count}")
    print(f"Processed URLs: {len(deduplicated_urls)}")
    print(f"Successful analyses: {successful_analyses}")
    print(f"Reviewable trainings: {reviewable_count}")
    print(f"Non-reviewable trainings: {non_reviewable_count}")
    print(f"Results saved to: {output_csv_path}")
    print(f"Total processing time: {duration:.2f} seconds")
    if len(deduplicated_urls) > 0:
        print(f"Average time per workout: {duration / len(deduplicated_urls):.2f} seconds")

    return results  # Return results for potential further use


if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process YouTube workout videos from a CSV file using multiprocessing')
    parser.add_argument('--input', type=str, default="all_workouts_1.csv",
                        help='Path to input CSV file containing YouTube URLs')
    parser.add_argument('--output', type=str, default="workouts_analyzed.csv",
                        help='Path to output CSV file for analysis results')
    parser.add_argument('--max', type=int, default=None,
                        help='Maximum number of workouts to process')
    parser.add_argument('--processes', type=int, default=10,
                        help='Number of parallel processes to use')
    parser.add_argument('--no-category', action='store_false', dest='category',
                        help='Disable workout category analysis')
    parser.add_argument('--no-fitness', action='store_false', dest='fitness_level',
                        help='Disable fitness level analysis')
    parser.add_argument('--no-vibe', action='store_false', dest='vibe',
                        help='Disable workout vibe analysis')
    parser.add_argument('--no-spirit', action='store_false', dest='spirit',
                        help='Disable workout spirit analysis')
    parser.add_argument('--no-equipment', action='store_false', dest='equipment',
                        help='Disable required equipment analysis')

    # Set default values for boolean arguments
    parser.set_defaults(category=True, fitness_level=True, vibe=True, spirit=True, equipment=True)

    # Parse arguments
    args = parser.parse_args()

    # Process workouts CSV with multiprocessing
    results = process_workouts_csv_mp(
        input_csv_path=args.input,
        output_csv_path=args.output,
        max_workouts=args.max,
        num_processes=args.processes,
        enable_category=args.category,
        enable_fitness_level=args.fitness_level,
        enable_vibe=args.vibe,
        enable_spirit=args.spirit,
        enable_equipment=args.equipment
    )

    # Cannot use results directly here as they are deduplicated in write_results_to_csv function
    print(f"\nProcess completed successfully!")