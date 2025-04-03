import pandas as pd
import csv
import re
from main11 import analyze_youtube_workout, extract_video_id
import time
from tqdm import tqdm  # For progress bar
import os


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


def process_workouts_csv(input_csv_path, output_csv_path, max_workouts=None, delay=1):
    """
    Process YouTube workout URLs from a CSV file and output vibe analysis results.

    Args:
        input_csv_path (str): Path to input CSV file
        output_csv_path (str): Path to output CSV file
        max_workouts (int, optional): Maximum number of workouts to process (for testing)
        delay (int, optional): Delay between API calls in seconds to avoid rate limiting
    """
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_csv_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Read the input CSV file
    try:
        df = pd.read_csv(input_csv_path)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    # Convert column names to strings
    df.columns = df.columns.astype(str)

    # Get all columns as they might have unusual names
    columns = df.columns.tolist()
    if len(columns) < 2:
        print(f"CSV file has insufficient columns: {columns}")
        return

    # Initialize output CSV file with headers
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'youtube_id',
            'first_vibe', 'first_vibe_score',
            'second_vibe', 'second_vibe_score',
            'third_vibe', 'third_vibe_score'
        ])

    # Track counts
    total_urls = 0
    valid_youtube_urls = 0
    successful_analyses = 0

    # Collect YouTube URLs from all columns
    all_urls = []
    for _, row in df.iterrows():
        for col in columns:
            if is_youtube_url(row[col]):
                all_urls.append(row[col])
                total_urls += 1

    print(f"Found {total_urls} total URLs in the CSV")

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
            result = analyze_youtube_workout(url, force_refresh=False)

            # Check if analysis was successful
            if "error" in result:
                print(f"Error analyzing workout {video_id}: {result['error']}")
                continue

            # Extract vibes information
            vibes = result.get('vibes', [])

            # Prepare data for CSV row
            row_data = [video_id]

            # Add vibes data (up to 3)
            for i in range(3):
                if i < len(vibes):
                    row_data.extend([vibes[i]['name'], vibes[i]['prominence']])
                else:
                    row_data.extend(['', ''])

            # Write to output CSV
            with open(output_csv_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(row_data)

            successful_analyses += 1

            # Add delay to avoid API rate limiting
            if delay > 0:
                time.sleep(delay)

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
    output_csv_path = "all_workouts_1_vibes_analysis.csv"

    # You can limit the number of workouts for testing
    # Set to None to process all workouts
    max_workouts = None

    # Add a delay between API calls to avoid rate limiting
    delay_seconds = 0.5

    process_workouts_csv(input_csv_path, output_csv_path, max_workouts, delay_seconds)