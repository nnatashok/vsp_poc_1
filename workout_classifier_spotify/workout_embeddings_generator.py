import json
import csv
import time
import argparse
from pathlib import Path
from openai import OpenAI
from env_utils import load_api_keys
import os
import sys


def load_vibes_info(csv_path='src/vibes_info.csv'):
    """Load vibes information from CSV file into a dictionary."""
    vibes_info = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                vibe_name = row.get('Workout Vibe', '')
                if vibe_name:
                    vibes_info[vibe_name] = {
                        'description': row.get('Vibe Description', ''),
                        'best_for': row.get('Best For', '')
                    }
        print(f"Loaded information for {len(vibes_info)} workout vibes")
        return vibes_info
    except Exception as e:
        print(f"Error loading vibes info: {e}")
        return {}


def create_workout_description(workout, vibes_info):
    """Create a comprehensive text description of a workout based on its attributes using natural language."""
    description = f"This is a {workout.get('duration_minutes', '')} minute workout called '{workout.get('video_title', '')}' from the channel {workout.get('channel_title', '')}.\n"

    # Add instructors style ?? maybe

    # Add category information
    categories = []
    if workout.get('category'):
        categories.append(f"{workout.get('category')}/{workout.get('subcategory', '')}")
    if workout.get('secondary_category'):
        categories.append(f"{workout.get('secondary_category')}/{workout.get('secondary_subcategory', '')}")
    if categories:
        description += f"The workout falls under {' and '.join(categories)}.\n"

    # Add fitness level information
    fitness_levels = [level for level in [workout.get('fitness_level', ''), workout.get('secondary_fitness_level', '')]
                      if level]
    if fitness_levels:
        description += f"It's suitable for {' and '.join(fitness_levels)} fitness levels.\n"

    # Add equipment information (removed tertiary)
    equipment = []
    if workout.get('primary_equipment'):
        equipment.append(workout.get('primary_equipment'))
    if workout.get('secondary_equipment'):
        equipment.append(workout.get('secondary_equipment'))
    if equipment:
        description += f"You'll need {' and '.join(equipment)} for this workout.\n"
    else:
        description += "You won't need any equipment"

    # Add vibe information with extended details from vibes_info
    vibes = []
    vibe_details = []

    primary_vibe = workout.get('primary_vibe')
    secondary_vibe = workout.get('secondary_vibe')

    if primary_vibe:
        vibes.append(primary_vibe)
        # Add detailed information about the primary vibe
        if primary_vibe in vibes_info:
            vibe_details.append(f"The {primary_vibe} vibe means {vibes_info[primary_vibe]['description']}")
            if vibes_info[primary_vibe]['best_for']:
                vibe_details.append(f"This is especially good for {vibes_info[primary_vibe]['best_for']}")

    if secondary_vibe:
        vibes.append(secondary_vibe)
        # Add detailed information about the secondary vibe
        if secondary_vibe in vibes_info and secondary_vibe != primary_vibe:  # Avoid duplicate info
            vibe_details.append(f"The {secondary_vibe} vibe means {vibes_info[secondary_vibe]['description']}")
            if vibes_info[secondary_vibe]['best_for']:
                vibe_details.append(f"This is especially good for {vibes_info[secondary_vibe]['best_for']}")

    if vibes:
        description += f"The workout has a {' and '.join(vibes)} vibe.\n"
        if vibe_details:
            description += f"{' '.join(vibe_details)}.\n"

    # Add technique difficulty information (removed tertiary)
    technique_difficulties = []
    if workout.get('primary_technique_difficulty'):
        technique_difficulties.append(workout.get('primary_technique_difficulty'))
    if workout.get('secondary_technique_difficulty'):
        technique_difficulties.append(workout.get('secondary_technique_difficulty'))
    if technique_difficulties:
        description += f"The technique difficulty is {' and '.join(technique_difficulties)}.\n"

    # Add effort difficulty information (removed tertiary)
    effort_difficulties = []
    if workout.get('primary_effort_difficulty'):
        effort_difficulties.append(workout.get('primary_effort_difficulty'))
    if workout.get('secondary_effort_difficulty'):
        effort_difficulties.append(workout.get('secondary_effort_difficulty'))
    if effort_difficulties:
        description += f"The effort required is {' and '.join(effort_difficulties)}.\n"

    # Add first 1000 symbols of workout description from full_analysis_json if available
    if workout.get('full_analysis_json'):
        try:
            full_analysis = json.loads(workout.get('full_analysis_json', '{}'))
            if 'video_metadata_cleaned' in full_analysis and 'text' in full_analysis['video_metadata_cleaned']:
                video_description = full_analysis['video_metadata_cleaned']['text']
                if video_description:
                    description += f"\nOriginal workout description: {video_description[:1000]}...\n"
        except (json.JSONDecodeError, KeyError):
            pass  # Skip if there's an error parsing the JSON or finding the description

    return description


def generate_embedding(client, text):
    """Generate an embedding for the given text using OpenAI's API."""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-large",  # Using a more powerful embedding model
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        return None


def is_cache_valid(cache_data, workout, vibes_info):
    """Check if the cached embedding is still valid or needs to be regenerated."""
    # If no cache data, it's not valid
    if not cache_data:
        return False

    # If cache data doesn't have a description field, it's an older format
    if 'description' not in cache_data:
        return False

    # Check if the description contains vibe information
    primary_vibe = workout.get('primary_vibe')
    if primary_vibe and primary_vibe in vibes_info:
        vibe_description = vibes_info[primary_vibe]['description']
        # If the vibe description isn't in the cached description, regenerate
        if vibe_description and vibe_description not in cache_data['description']:
            return False

    # Cache seems valid
    return True


def main():
    # Set up relative locations
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    ouput_file = os.path.join(current_dir,"workouts_analyzed_w_embeddings.csv")
    input_file = os.path.join(current_dir,"workouts_analyzed.csv")
    vibes_info = os.path.join(current_dir,"vibes_info.csv")
    cache_dir = os.path.join(current_dir, "cache")

    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Generate workout embeddings')
    parser.add_argument('--force-refresh', action='store_true',
                        help='Force regeneration of all embeddings, ignoring cache')
    parser.add_argument('--input', type=str, default=input_file,
                        help='Path to input CSV file with workout data')
    parser.add_argument('--output', type=str, default=ouput_file,
                        help='Path to output CSV file for workouts with embeddings')
    parser.add_argument('--vibes-info', type=str, default=vibes_info,
                        help='Path to CSV file with vibes information')
    parser.add_argument('--cache-dir', type=str, default=cache_dir,
                        help='Directory for caching embeddings')
    args = parser.parse_args()

    # Load API keys
    api_keys = load_api_keys()
    if not api_keys['OPENAI_API_KEY']:
        print("Error: OPENAI_API_KEY not found in environment variables.")
        return

    # Initialize OpenAI client
    client = OpenAI(api_key=api_keys['OPENAI_API_KEY'])

    # Load vibes information
    vibes_info = load_vibes_info(args.vibes_info)

    # Create cache directory
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(exist_ok=True, parents=True)

    # Read workouts from CSV
    workouts = []
    csv.field_size_limit(sys.maxsize)
    with open(args.input, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Preserve all column names from the input CSV
        fieldnames = reader.fieldnames.copy() if reader.fieldnames else []
        # Add embedding column if it doesn't exist
        if 'embedding' not in fieldnames:
            fieldnames.append('embedding')
        workouts = list(reader)

    print(f"Found {len(workouts)} workouts in CSV file.")

    # Process each workout
    new_embeddings = 0
    cached_embeddings = 0
    failed_embeddings = 0

    for i, workout in enumerate(workouts):
        video_id = workout.get('video_id')
        if not video_id:
            continue

        # Check if cache file exists
        cache_file = cache_dir / f"{video_id}.json"
        cache_data = None

        # Load cache if it exists
        if cache_file.exists() and not args.force_refresh:
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            except json.JSONDecodeError:
                print(f"Cache file for {video_id} is corrupted, will regenerate.")
                cache_data = None

        # Check if cache is valid
        if cache_data and is_cache_valid(cache_data, workout, vibes_info) and not args.force_refresh:
            print(f"Processing workout {i + 1}/{len(workouts)}: {video_id} (using cached embedding)")
            embedding = cache_data.get('embedding')
            cached_embeddings += 1
        else:
            # Generate new embedding
            print(f"Processing workout {i + 1}/{len(workouts)}: {video_id} (generating new embedding)")

            # Create description with vibes info
            description = create_workout_description(workout, vibes_info)

            # Generate embedding
            embedding = generate_embedding(client, description)
            if not embedding:
                print(f"Skipping workout {video_id} due to embedding error.")
                failed_embeddings += 1
                continue

            # Save to cache
            cache_data = {
                "video_id": video_id,
                "description": description,
                "embedding": embedding
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            new_embeddings += 1

            # Sleep briefly to avoid rate limits
            time.sleep(0.1)

        # Add embedding to workout data
        workout['embedding'] = json.dumps(embedding)

    # Create output directory if it doesn't exist
    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True, parents=True)

    # Save workouts with embeddings to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(workouts)

    print(f"Successfully processed {len(workouts) - failed_embeddings} workouts.")
    print(f"  - {new_embeddings} new embeddings generated")
    print(f"  - {cached_embeddings} embeddings loaded from cache")
    print(f"  - {failed_embeddings} embeddings failed")
    print(f"Workouts with embeddings saved to {args.output}")


if __name__ == "__main__":
    main()