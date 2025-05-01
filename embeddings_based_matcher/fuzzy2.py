import pandas as pd
import numpy as np
import json
from datetime import datetime
import re
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from env_utils import load_api_keys

# Load API keys
api_keys = load_api_keys()
client = OpenAI(api_key=api_keys['OPENAI_API_KEY'])


def load_data():
    """Load workout plan specifications and workout library data"""
    workout_plan = pd.read_csv('WorkoutPlanDaySpec.csv')
    workout_library = pd.read_csv('workouts_analyzed.csv')
    return workout_plan, workout_library


def extract_plan_info(workout_plan):
    """Extract essential information from workout plan"""
    plan_data = []
    for _, row in workout_plan.iterrows():
        day_info = {'day': row['date']}  # Use the 'date' column directly

        # Extract duration
        day_info['duration'] = int(row['duration']) if pd.notna(row['duration']) else 30

        # Extract category and subcategory
        day_info['category'] = row['category'] if pd.notna(row['category']) else ''
        day_info['subcategory'] = row['subcategory'] if pd.notna(row['subcategory']) else ''

        # Extract workout vibes
        day_info['primary_vibe'] = row['primary_vibe'] if pd.notna(row['primary_vibe']) else ''
        day_info['secondary_vibe'] = row['secondary_vibe'] if pd.notna(row['secondary_vibe']) else ''

        # Extract fitness level
        day_info['fitness_level'] = row['fitness_level'] if pd.notna(row['fitness_level']) else ''

        plan_data.append(day_info)

    return pd.DataFrame(plan_data)


def extract_workout_details(workout_row):
    """Extract workout title and description from full_analysis_json"""
    title = workout_row.get('video_title', '')
    description = ''

    try:
        if pd.notna(workout_row.get('full_analysis_json')):
            analysis = json.loads(workout_row['full_analysis_json'])

            # Try to extract description from various places in the JSON
            if 'description' in analysis:
                description = analysis['description']
            elif 'category' in analysis and 'categoriesExplanation' in analysis['category']:
                description = analysis['category']['categoriesExplanation']
            elif 'vibe' in analysis and 'vibesExplanation' in analysis['vibe']:
                description = analysis['vibe']['vibesExplanation']
            elif 'spirit' in analysis and 'spiritsExplanation' in analysis['spirit']:
                description = analysis['spirit']['spiritsExplanation']
    except (json.JSONDecodeError, AttributeError, KeyError):
        pass

    return title, description


def get_embedding(text, model="text-embedding-3-small"):
    """Get OpenAI embedding for a given text"""
    text = text.replace("\n", " ")
    try:
        response = client.embeddings.create(input=[text], model=model)
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None


def create_plan_text(plan_row):
    """Create a descriptive text from plan specification for embedding"""
    parts = []

    if plan_row.get('category'):
        parts.append(f"{plan_row['category']} workout")

    if plan_row.get('subcategory'):
        parts.append(f"focusing on {plan_row['subcategory']}")

    if plan_row.get('primary_vibe'):
        parts.append(f"with {plan_row['primary_vibe']} vibe")

    if plan_row.get('secondary_vibe'):
        parts.append(f"and {plan_row['secondary_vibe']} feel")

    if plan_row.get('fitness_level'):
        parts.append(f"for {plan_row['fitness_level']} level")

    if plan_row.get('duration'):
        parts.append(f"lasting {plan_row['duration']} minutes")

    return " ".join(parts)


def create_workout_text(workout_row):
    """Create a descriptive text from workout for embedding"""
    title, description = extract_workout_details(workout_row)

    parts = [title]

    if description:
        parts.append(description)

    # Add basic info
    parts.append(f"{workout_row.get('category', '')} {workout_row.get('subcategory', '')} workout")

    if workout_row.get('primary_vibe'):
        parts.append(f"with {workout_row['primary_vibe']} vibe")

    if workout_row.get('fitness_level'):
        parts.append(f"for {workout_row['fitness_level']} level")

    if workout_row.get('duration_minutes'):
        parts.append(f"lasting {workout_row['duration_minutes']} minutes")

    return " ".join(parts)


def precompute_workout_embeddings(workout_library):
    """Precompute embeddings for all workouts"""
    embeddings = []
    texts = []

    for _, workout_row in workout_library.iterrows():
        text = create_workout_text(workout_row)
        texts.append(text)
        print('workout text', text)
        embedding = get_embedding(text)

        if embedding:
            embeddings.append(embedding)
        else:
            # If embedding fails, use a zero vector
            embeddings.append([0] * 1536)  # Default embedding size for text-embedding-3-small

    return np.array(embeddings), texts


def calculate_match_score(plan_row, workout_row, plan_embedding, workout_embedding):
    """Calculate how well a workout matches the plan specification"""
    score = 0
    match_reasons = []

    # 1. Embedding similarity (0-40 points)
    if plan_embedding is not None and len(workout_embedding) > 0:
        try:
            # Convert embeddings to numpy arrays if they aren't already
            plan_emb = np.array(plan_embedding).reshape(1, -1)
            workout_emb = np.array(workout_embedding).reshape(1, -1)

            similarity = cosine_similarity(plan_emb, workout_emb)[0][0]
            embedding_score = similarity * 40  # Scale to 0-40 points
            score += embedding_score
            match_reasons.append(f"Embedding similarity: {similarity:.2f} ({embedding_score:.1f} points)")
        except Exception as e:
            print(f"Error calculating embedding similarity: {e}")

    # 2. Category match (0-15 points)
    plan_category = str(plan_row.get('category', '')).lower()
    workout_category = str(workout_row.get('category', '')).lower()

    if plan_category == workout_category:
        score += 15
        match_reasons.append(f"Perfect category match: {plan_category}")
    elif plan_category in workout_category or workout_category in plan_category:
        score += 8
        match_reasons.append(f"Related category: {plan_category} ~ {workout_category}")

    # 3. Subcategory match (0-15 points)
    plan_subcategory = str(plan_row.get('subcategory', '')).lower()
    workout_subcategory = str(workout_row.get('subcategory', '')).lower()
    workout_secondary_subcategory = str(workout_row.get('secondary_subcategory', '')).lower()

    if plan_subcategory == workout_subcategory:
        score += 15
        match_reasons.append(f"Perfect subcategory match: {plan_subcategory}")
    elif plan_subcategory == workout_secondary_subcategory:
        score += 10
        match_reasons.append(f"Secondary subcategory match: {plan_subcategory}")
    elif plan_subcategory in workout_subcategory or workout_subcategory in plan_subcategory:
        score += 5
        match_reasons.append(f"Related subcategory: {plan_subcategory} ~ {workout_subcategory}")

    # 4. Fitness level match (0-15 points)
    plan_fitness_level = str(plan_row.get('fitness_level', '')).lower()
    workout_fitness_level = str(workout_row.get('fitness_level', '')).lower()
    workout_secondary_fitness_level = str(workout_row.get('secondary_fitness_level', '')).lower()
    workout_tertiary_fitness_level = str(workout_row.get('tertiary_fitness_level', '')).lower()

    if plan_fitness_level == workout_fitness_level:
        score += 15
        match_reasons.append(f"Perfect fitness level match: {plan_fitness_level}")
    elif plan_fitness_level == workout_secondary_fitness_level:
        score += 10
        match_reasons.append(f"Secondary fitness level match: {plan_fitness_level}")
    elif plan_fitness_level == workout_tertiary_fitness_level:
        score += 7
        match_reasons.append(f"Tertiary fitness level match: {plan_fitness_level}")
    else:
        # If no exact match, try to match based on proximity
        fitness_levels = {'beginner': 1, 'intermediate': 2, 'advanced': 3}

        if plan_fitness_level in fitness_levels and workout_fitness_level in fitness_levels:
            level_diff = abs(fitness_levels[plan_fitness_level] - fitness_levels[workout_fitness_level])
            if level_diff == 1:
                score += 5
                match_reasons.append(f"Close fitness level: {plan_fitness_level} ~ {workout_fitness_level}")

    # 5. Duration match (0-15 points)
    plan_duration = plan_row.get('duration', 30)

    # Try to get workout duration
    workout_duration = 30  # Default
    try:
        workout_duration = float(workout_row.get('duration_minutes', 30))
    except (ValueError, TypeError):
        # Try extracting from time format
        duration_str = str(workout_row.get('duration', ''))
        if ':' in duration_str:
            try:
                hours, minutes = duration_str.split(':')[:2]
                workout_duration = int(hours) * 60 + int(minutes)
                workout_duration /= 60  # Convert back to minutes
            except (ValueError, IndexError):
                pass

    # Calculate duration score based on percentage difference
    duration_diff_pct = abs(plan_duration - workout_duration) / plan_duration

    if duration_diff_pct <= 0.1:  # Within 10%
        score += 15
        match_reasons.append(f"Duration is perfect: {workout_duration}min ≈ {plan_duration}min")
    elif duration_diff_pct <= 0.2:  # Within 20%
        score += 10
        match_reasons.append(f"Duration is close: {workout_duration}min ~ {plan_duration}min")
    elif duration_diff_pct <= 0.3:  # Within 30%
        score += 5
        match_reasons.append(f"Duration is acceptable: {workout_duration}min vs {plan_duration}min")
    else:
        match_reasons.append(f"Duration mismatch: {workout_duration}min vs {plan_duration}min")

    return score, match_reasons


def get_workout_essence(workout_row):
    """Extract essence information from a workout"""
    title, description = extract_workout_details(workout_row)

    essence = {
        'type': f"{workout_row.get('category', '')} - {workout_row.get('subcategory', '')}",
        'primary_vibe': workout_row.get('primary_vibe', ''),
        'secondary_vibe': workout_row.get('secondary_vibe', ''),
        'fitness_level': workout_row.get('fitness_level', ''),
        'secondary_fitness_level': workout_row.get('secondary_fitness_level', ''),
        'tertiary_fitness_level': workout_row.get('tertiary_fitness_level', ''),
        'title': title,
        'description_snippet': description[:200] + '...' if description else ''
    }

    return essence


def match_workouts():
    """Main function to match workouts with plan specifications"""
    # Load data
    workout_plan, workout_library = load_data()

    # Process plan data
    plan_data = extract_plan_info(workout_plan)

    # Precompute workout embeddings
    print("Computing workout embeddings...")
    workout_embeddings, workout_texts = precompute_workout_embeddings(workout_library)

    # Match each day's plan with the best workout
    matched_workouts = []

    for idx, plan_row in plan_data.iterrows():
        print(f"Matching workout for day {idx + 1}/{len(plan_data)}...")

        # Get embedding for plan
        plan_text = create_plan_text(plan_row)
        print('plan_text', plan_text)
        plan_embedding = get_embedding(plan_text)

        best_score = -1
        best_match = None
        best_reasons = []
        best_workout_text = ""

        for workout_idx, workout_row in workout_library.iterrows():
            workout_embedding = workout_embeddings[workout_idx]
            score, reasons = calculate_match_score(plan_row, workout_row, plan_embedding, workout_embedding)

            if score > best_score:
                best_score = score
                best_match = workout_row
                best_reasons = reasons
                best_workout_text = workout_texts[workout_idx]

        if best_match is not None:
            workout_essence = get_workout_essence(best_match)

            matched_workouts.append({
                'day': plan_row.get('day', ''),
                'plan': {
                    'category': plan_row.get('category', ''),
                    'subcategory': plan_row.get('subcategory', ''),
                    'primary_vibe': plan_row.get('primary_vibe', ''),
                    'secondary_vibe': plan_row.get('secondary_vibe', ''),
                    'fitness_level': plan_row.get('fitness_level', ''),
                    'duration': plan_row.get('duration', 30),
                    'plan_text': plan_text
                },
                'workout': {
                    'id': best_match.get('video_id', ''),
                    'title': best_match.get('video_title', ''),
                    'url': best_match.get('video_url', ''),
                    'category': best_match.get('category', ''),
                    'subcategory': best_match.get('subcategory', ''),
                    'duration': best_match.get('duration', ''),
                    'workout_text': best_workout_text[:200] + '...' if len(
                        best_workout_text) > 200 else best_workout_text
                },
                'match_score': best_score,
                'match_quality': 'Excellent' if best_score >= 80 else 'Good' if best_score >= 60 else 'Fair',
                'match_reasons': best_reasons,
                'workout_essence': workout_essence
            })

    return matched_workouts


def main():
    """Main function to run the workout matching process"""
    # Check if API key is available
    if not api_keys['OPENAI_API_KEY']:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return

    matched_workouts = match_workouts()

    # Save results to file
    with open('matched_workouts_embeddings.json', 'w') as f:
        json.dump(matched_workouts, f, indent=2)

    # Print summary
    print(f"\nSuccessfully matched {len(matched_workouts)} workouts")

    # Show sample results
    print("\nSample matches:")
    for i, match in enumerate(matched_workouts[:3]):
        print(f"\n--- Day: {match['day']} ---")
        print(f"Plan: {match['plan']['plan_text']}")
        print(f"Workout: {match['workout']['title']}")
        print(f"Match score: {match['match_score']:.1f}/100 ({match['match_quality']})")
        print("Reasons:")
        for reason in match['match_reasons']:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()