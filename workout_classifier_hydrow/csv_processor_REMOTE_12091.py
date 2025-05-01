import pandas as pd
import csv
import json
import re
import os
import argparse
import json
from tqdm import tqdm  # For progress bar
from env_utils import load_api_keys
from unified_workout_classifier import analyse_hydrow_workout, cache_data
from json_stats_collection import flatten_json
from db_transformer import transform_to_db_structure


import json

def is_hydrow_meta(value):
    """
    Check if a value is a valid JSON object (or stringified JSON) that
    contains 'image.bucket' and its value starts with 'hydrow'.
    
    Args:
        value (str or dict): Input to validate
    
    Returns:
        bool: True if valid and meets all criteria, False otherwise
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return False

    if not isinstance(value, dict):
        return False

    image = value.get("image")
    if not isinstance(image, dict):
        return False

    bucket = image.get("bucket")
    return isinstance(bucket, str) and bucket.startswith("hydrow")


def process_workouts_csv(input_csv_path, output_csv_path, max_workouts=None, 
                        enable_category=True, enable_fitness_level=True, 
                        enable_vibe=True, enable_spirit=True, enable_equipment=True):
    """
    Process Hydrow workout JSONs from a CSV file and output analysis results.
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
    # Load API keys from .env files in different locations
    api_keys = load_api_keys()
    openai_api_key = api_keys.get('OPENAI_API_KEY')
    
    # Output API key status
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
            'secondary_fitness_level',
            'tertiary_fitness_level',  # New field
            'primary_equipment',
            'secondary_equipment',
            'tertiary_equipment',  # New field
            'primary_spirit',
            'secondary_spirit',
            'primary_vibe',
            'secondary_vibe',
            'full_analysis_json'
        ])

    # Track counts
    total_jsons = 0
    successful_analyses = 0

    # Collect hydrow meta from all columns
    all_jsons = []
    for _, row in df.iterrows():
        for col in columns:
            if is_hydrow_meta(str(row[col])):
                all_jsons.append(str(row[col]))
                total_jsons += 1
                break # assumption: 1 row has 1 unique JSON!


    print(f"Found {total_jsons} total hydrow JSONs in the CSV")

    # Limit the number of workouts to process if specified
    if max_workouts and max_workouts > 0:
        all_jsons = all_jsons[:max_workouts]
        print(f"Limited to processing {max_workouts} JSONs")

    # Process each YouTube URL
    for sch, schema in tqdm(enumerate(all_jsons), total=len(all_jsons), desc="Processing workouts"):
        # ! sample every 100
        if sch%100 != 0: 
            continue
        
        if is_hydrow_meta(schema):
            schema = json.loads(schema)
        else:
            print("The json #{sch} not valid. Skipping.")
        
        # ! skiping all workouts with no Genre label
        flat_schema = flatten_json(schema)
        if not any(k.endswith("musicGenre") for k in flat_schema):
            print(f'For json #{sch} no musicGenre specified. Therefore workout is skipped.')
            continue

        video_id = schema.get("id")
        if not video_id:
            print(f"Could not extract video ID from URL: json #{sch}")
            continue

        # ! cache original json file if needed
        # cache_data(schema, "path_placeholder")

        try:
            # Analyze the workout, passing API keys to the function
            print(f"Analyzing workout json #{sch}")
            result = analyse_hydrow_workout(
                schema,
                openai_api_key=openai_api_key,
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
                db_structure.get('secondary_fitness_level', ''),
                db_structure.get('tertiary_fitness_level', ''),  # New field #? todos?
                db_structure.get('primary_equipment', ''),
                db_structure.get('secondary_equipment', ''),
                db_structure.get('tertiary_equipment', ''),  # New field
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
    print(f"Total URLs found: {total_jsons}")
    print(f"Successful analyses: {successful_analyses}")
    print(f"Results saved to: {output_csv_path}")


if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process Hydrow workout videos from a CSV file')
    parser.add_argument('--input', type=str, default="workouts_w_hydrow.csv",
                        help='Path to input CSV file containing Hydrow metadata in JSONs')
    parser.add_argument('--output', type=str, default="workouts_analyzed.csv", 
                        help='Path to output CSV file for analysis results')
    parser.add_argument('--max', type=int, default=None,
                        help='Maximum number of workouts to process')
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

    # Process workouts CSV with command line arguments
    process_workouts_csv(
        input_csv_path=args.input,
        output_csv_path=args.output,
        max_workouts=args.max,
        enable_category=args.category,
        enable_fitness_level=args.fitness_level,
        enable_vibe=args.vibe,
        enable_spirit=args.spirit,
        enable_equipment=args.equipment
    )