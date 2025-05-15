import pandas as pd
import csv
import json
import os
import re
import numpy as np
import argparse
from tqdm import tqdm
from multiprocessing import Pool
import time 

from env_utils import load_api_keys
from unified_workout_classifier import analyse_spotify_workout, return_error_analysis, extract_video_id
from json_stats_collection import flatten_json
from db_transformer import transform_to_db_structure


import json

def is_spotify_meta(value):
    """
    Check if a value is a valid Spotify playlist JSON (real or stringified).
    It must contain a playlist.external_urls.spotify field containing a URL to Spotify.

    Args:
        value (str or dict): Potential JSON input

    Returns:
        bool: True if valid Spotify workout metadata
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return False

    if not isinstance(value, dict):
        return False

    playlist = value.get("playlist")
    if not isinstance(playlist, dict):
        return False

    external_urls = playlist.get("external_urls")
    if not isinstance(external_urls, dict):
        return False

    spotify_url = external_urls.get("spotify")
    return isinstance(spotify_url, str) and spotify_url.startswith("https://open.spotify.com/")

def analyze_workout(args):
    """
    Analyze a single Spotify playlist JSON entry. Used for parallel processing.

    Args:
        args (tuple): (raw_json, openai_api_key, enabled_features dict, process_id)

    Returns:
        dict or None: Structured result dictionary or None if analysis failed
    """
    raw_json, openai_api_key, enabled_features, process_id, cache_dir_path = args

    try:
        schema = json.loads(raw_json)
    except Exception:
        print(f"Process {process_id}: Failed to parse JSON")
        return return_error_analysis("Failed to parse JSON", None)
 
    video_id, raw_json = extract_video_id(raw_json, None)
    
    try:
        print(f"Process {process_id}: Analyzing workout {video_id}")
        result = analyse_spotify_workout(
            schema,
            openai_api_key=openai_api_key,
            force_refresh=False,
            cache_dir=cache_dir_path,
            enable_vibe=enabled_features['vibe'],
            enable_spirit=enabled_features['spirit'],
            enable_web_search=enabled_features['websearch'],
            enable_image_in_meta=enabled_features['image']
        )


        if "error" in result:
            print(f"Process {process_id}: Error during analysis: {result['error']}")
            return return_error_analysis("Error during analysis.", schema)

        db_structure = transform_to_db_structure(result)

        output_data = {
            'video_id': db_structure.get('video_id', ''),
            'video_url': db_structure.get('video_url', ''),
            'video_title': db_structure.get('video_title', ''),
            'channel_title': db_structure.get('channel_title', ''),
            'duration': db_structure.get('duration', ''),
            'duration_minutes': db_structure.get('duration_minutes', ''),
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
            'reviewable': db_structure.get('reviewable', ''),
            'review_comment': db_structure.get('review_comment', ''),
            'primary_technique_difficulty': db_structure.get('primary_technique_difficulty', ''),
            'secondary_technique_difficulty': db_structure.get('secondary_technique_difficulty', ''),
            'tertiary_technique_difficulty': db_structure.get('tertiary_technique_difficulty', ''),
            'primary_effort_difficulty': db_structure.get('primary_effort_difficulty', ''),
            'secondary_effort_difficulty': db_structure.get('secondary_effort_difficulty', ''),
            'tertiary_effort_difficulty': db_structure.get('tertiary_effort_difficulty', ''),
            'full_analysis_json': json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            'poster_uri':db_structure.get('poster_uri', ''),
        }
        print(f"Process {process_id}: Successfully analyzed workout: {video_id}")
        return output_data

    except Exception as e:
        print(f"Process {process_id}: Unexpected error for workout #{video_id}: {str(e)}")
        return return_error_analysis("Unexpected error for workout.", schema)

def write_results_to_csv(results, output_csv_path):
    """
    Write analysis results to CSV file.
    Filter out duplicates based on video_id (keeping the first occurrence).

    Args:
        results (list): List of analysis results
        output_csv_path (str): Path to output CSV file
    """
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        print("No valid results to write.")
        return

    # Deduplicate results based on video_id
    unique_results = {}
    for result in valid_results:
        video_id = result.get('video_id')
        if video_id and video_id not in unique_results:
            unique_results[video_id] = result

    # Write to output CSV
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
            'full_analysis_json', 'poster_uri'
    ]
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for result in unique_results.values():
            writer.writerow(result)

    return unique_results

def process_workouts_csv_mp(input_csv_path, output_csv_path, cache_dir_path,
                             num_processes=8, max_workouts=None,
                             enable_vibe=True, enable_spirit=True,
                             include_image=False, enable_web_search=True):
    """
    Process Hydrow workout JSONs from a CSV using multiprocessing.

    Args:
        input_csv_path (str): Path to CSV file with JSON metadata
        output_csv_path (str): Destination CSV file path
        max_workouts (int): Optional cap on number of workouts to analyze
        processes (int): Number of parallel processes to use
        enable_category (bool): Whether to classify by workout category
        enable_fitness_level (bool): Whether to classify by fitness level
        enable_vibe (bool): Whether to classify by vibe
        enable_spirit (bool): Whether to classify by spirit
        enable_equipment (bool): Whether to extract equipment
        include_image (bool): Whether to include image in analysis
    """
    start_time = time.time()
    
    api_keys = load_api_keys()
    openai_api_key = api_keys.get('OPENAI_API_KEY')
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
      
    df.columns = df.columns.astype(str)

    # Get all columns
    columns = df.columns.tolist()
    if len(columns) < 1:
        print(f"CSV file has insufficient columns: {columns}")
        return

    all_jsons = []
    for _, row in df.iterrows():
        for col in df.columns:
            cell = str(row[col])
            if is_spotify_meta(cell):
                all_jsons.append(cell)
                break

    print(f"Found {len(all_jsons)} valid Spotify JSON entries")

    
    # Deduplicate URLs based on video_id
    unique_jsons = {}
    for js, json_str in enumerate(all_jsons):
        video_id, json_str = extract_video_id(json_str, js)
        if video_id and video_id not in unique_jsons:
            unique_jsons[video_id] = json_str
    
    deduplicated_jsons = list(unique_jsons.values())
    
    # Limit the number of workouts to process if specified
    if max_workouts and max_workouts > 0:
        deduplicated_jsons = deduplicated_jsons[:max_workouts]
        print(f"Limited to processing {max_workouts} JSONs")

    total_jsons = len(all_jsons)
    unique_count = len(deduplicated_jsons)
    print(f"Found {total_jsons} total samples in the CSV")
    print(f"After deduplication: {unique_count} unique JSONs")

    # Check if we have more processes than videos
    actual_processes = min(num_processes, max(1, len(deduplicated_jsons)))
    if actual_processes != num_processes:
        print(f"Using {actual_processes} processes for {len(deduplicated_jsons)} URLs")

  
    enabled_features = {
        'vibe': enable_vibe,
        'spirit': enable_spirit,
        'image': include_image,
        'websearch':enable_web_search
    }

    # Create batches of URLs for each process
    batch_size = len(deduplicated_jsons) // actual_processes
    if len(deduplicated_jsons) % actual_processes != 0:
        batch_size += 1

    # Split URLs into batches
    json_batches = []
    for i in range(0, len(deduplicated_jsons), batch_size):
        batch = deduplicated_jsons[i:i + batch_size]
        json_batches.append(batch)

    # Print batch information
    print(f"Split {len(deduplicated_jsons)} JSONs into {len(json_batches)} batches")

    # Prepare arguments for each process
    process_args = []
    for i, batch in enumerate(json_batches):
        # Flatten the batch into individual tasks with process ID
        for el in batch:
            process_args.append((el, openai_api_key, enabled_features, i, cache_dir_path))

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
    print(f"Total JSONs found: {total_jsons}")
    print(f"Unique JSONs found: {unique_count}")
    print(f"Processed JSONs: {len(deduplicated_jsons)}")
    print(f"Successful analyses: {successful_analyses}")
    print(f"Reviewable trainings: {reviewable_count}")
    print(f"Non-reviewable trainings: {non_reviewable_count}")
    print(f"Results saved to: {output_csv_path}")
    print(f"Total processing time: {duration:.2f} seconds")
    if len(deduplicated_jsons) > 0:
        print(f"Average time per workout: {duration / len(deduplicated_jsons):.2f} seconds")

    return results  # Return results for potential further use

if __name__ == "__main__":
    # Set up files
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    input_file = os.path.join(current_dir,"Workout.csv")
    output_file = os.path.join(current_dir,"workouts_analyzed.csv")
    cache_dir = os.path.join(current_dir, "cache")
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process Hydrow workout videos from a CSV file')
    parser.add_argument('--input', type=str, default=input_file,#!
                        help='Path to input CSV file containing Hydrow metadata in JSONs')
    parser.add_argument('--output', type=str, default=output_file, #! 
                        help='Path to output CSV file for analysis results')
    parser.add_argument('--cache', type=str, default=cache_dir, #! 
                        help='Path to save cache, and read from cache')
    parser.add_argument('--max', type=int, default=None,#!
                        help='Maximum number of workouts to process')
    parser.add_argument('--no-vibe', action='store_false', dest='vibe',
                        help='Disable workout vibe analysis')
    parser.add_argument('--no-spirit', action='store_false', dest='spirit',
                        help='Disable workout spirit analysis')
    parser.add_argument('--include-image', action='store_true', dest='image',
                        help='To include poster image as model input')
    parser.add_argument('--include-websearch', action='store_true', dest='websearch',
                        help='To include selenium websearch for tracks in playlist')
    
    # Set default values for boolean arguments
    parser.set_defaults(vibe=True, spirit=True, image=False, websearch=False)
    
    # Parse arguments
    args = parser.parse_args()

    # Process workouts CSV with command line arguments
    results = process_workouts_csv_mp(
        input_csv_path=args.input,
        output_csv_path=args.output,
        cache_dir_path=args.cache,
        max_workouts=args.max,
        enable_web_search=args.websearch,
        enable_vibe=args.vibe,
        enable_spirit=args.spirit,
        include_image=args.image ,
        num_processes=4 #!
    )

    # Cannot use results directly here as they are deduplicated in write_results_to_csv function
    print(f"\nProcess completed successfully!")