import pandas as pd
import csv
import json
import re
import os
from tqdm import tqdm  # For progress bar
from unified_workout_classifier import analyze_youtube_workout, extract_video_id
from db_transformer import transform_to_db_structure


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


def process_workouts_csv(input_csv_path, output_csv_path, max_workouts=None, 
                        enable_category=True, enable_fitness_level=True, 
                        enable_vibe=True, enable_spirit=True, enable_equipment=True):
    """
    Process YouTube workout URLs from a CSV file and output analysis results.
    Always rewrites the output file from scratch.

    Args:
        input_csv_path (str): Path to input CSV file
        output_csv_path (str): Path to output CSV file
        max_workouts (int, optional): Maximum number of workouts to process (for testing)
        enable_category (bool): Whether to analyze workout categories
        enable_fitness_level (bool): Whether to analyze fitness levels
        enable_vibe (bool): Whether to analyze workout vibes
        enable_spirit (bool): Whether to analyze workout spirits
        enable_equipment (bool): Whether to analyze required equipment
    """
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

    # Get all columns as they might have unusual names
    columns = df.columns.tolist()
    if len(columns) < 1:
        print(f"CSV file has insufficient columns: {columns}")
        return

    # Initialize output CSV file with headers (always start fresh)
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'video_id',
            'video_url',
            'video_title',
            'channel_title',
            'duration',
            'category',
            'subcategory',
            'secondary_category',
            'secondary_subcategory',
            'fitness_level',
            'secondary_fitness_level',  # New field
            'primary_equipment',
            'secondary_equipment',
            'primary_spirit',
            'secondary_spirit',
            'primary_vibe',
            'secondary_vibe',
            'full_analysis_json'
        ])

    # Track counts
    total_urls = 0
    valid_youtube_urls = 0
    successful_analyses = 0

    # Collect YouTube URLs from all columns
    all_urls = []
    for _, row in df.iterrows():
        for col in columns:
            if is_youtube_url(str(row[col])):
                all_urls.append(str(row[col]))
                total_urls += 1

    print(f"Found {total_urls} total YouTube URLs in the CSV")

    # Limit the number of workouts to process if specified
    if max_workouts and max_workouts > 0:
        all_urls = all_urls[:max_workouts]
        print(f"Limited to processing {max_workouts} URLs")

    # Process each YouTube URL
    for url in tqdm(all_urls, desc="Processing workouts"):
        if not is_youtube_url(url):
            continue

        valid_youtube_urls += 1
        video_id = extract_video_id(url)

        if not video_id:
            print(f"Could not extract video ID from URL: {url}")
            continue

        try:
            # Analyze the workout
            print(f"Analyzing workout: {url}")
            result = analyze_youtube_workout(
                url,
                force_refresh=False,
                enable_category=enable_category,
                enable_fitness_level=enable_fitness_level,
                enable_vibe=enable_vibe,
                enable_spirit=enable_spirit,
                enable_equipment=enable_equipment
            )

            # Check if analysis was successful
            if "error" in result:
                error_msg = str(result["error"])
                print(f"Error analyzing workout {video_id}: {error_msg}")
                continue

            # Transform to database structure
            db_structure = transform_to_db_structure(result)

            # Convert full analysis to JSON string
            full_analysis_json = json.dumps(result)

            # Prepare data for CSV row
            row_data = [
                db_structure.get('video_id', ''),
                db_structure.get('video_url', ''),
                db_structure.get('video_title', ''),
                db_structure.get('channel_title', ''),
                db_structure.get('duration', ''),
                db_structure.get('category', ''),
                db_structure.get('subcategory', ''),
                db_structure.get('secondary_category', ''),
                db_structure.get('secondary_subcategory', ''),
                db_structure.get('fitness_level', ''),
                db_structure.get('secondary_fitness_level', ''),  # New field
                db_structure.get('primary_equipment', ''),
                db_structure.get('secondary_equipment', ''),
                db_structure.get('primary_spirit', ''),
                db_structure.get('secondary_spirit', ''),
                db_structure.get('primary_vibe', ''),
                db_structure.get('secondary_vibe', ''),
                full_analysis_json
            ]

            # Write to output CSV
            with open(output_csv_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(row_data)

            successful_analyses += 1

        except Exception as e:
            print(f"Error processing workout {video_id}: {str(e)}")

    # Print summary
    print(f"\nProcessing complete!")
    print(f"Total URLs found: {total_urls}")
    print(f"Valid YouTube URLs: {valid_youtube_urls}")
    print(f"Successful analyses: {successful_analyses}")
    print(f"Results saved to: {output_csv_path}")


if __name__ == "__main__":
    input_csv_path = "all_workouts_1.csv"
    output_csv_path = "workouts_analyzed.csv"

    # You can limit the number of workouts for testing
    # Set to None to process all workouts
    max_workouts = 3

    process_workouts_csv(
        input_csv_path,
        output_csv_path,
        max_workouts=max_workouts,
        enable_category=True,
        enable_fitness_level=True,
        enable_vibe=True,
        enable_spirit=True,
        enable_equipment=True
    )