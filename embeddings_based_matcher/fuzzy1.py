import pandas as pd
import numpy as np
import json
from datetime import datetime
import re


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


def calculate_match_score(plan_row, workout_row):
    """Calculate how well a workout matches the plan specification"""
    score = 0
    match_reasons = []

    # 1. Category match (0-20 points)
    plan_category = str(plan_row.get('category', '')).lower()
    workout_category = str(workout_row.get('category', '')).lower()

    if plan_category == workout_category:
        score += 20
        match_reasons.append(f"Perfect category match: {plan_category}")
    elif plan_category in workout_category or workout_category in plan_category:
        score += 10
        match_reasons.append(f"Related category: {plan_category} ~ {workout_category}")

    # 2. Subcategory match (0-20 points)
    plan_subcategory = str(plan_row.get('subcategory', '')).lower()
    workout_subcategory = str(workout_row.get('subcategory', '')).lower()
    workout_secondary_subcategory = str(workout_row.get('secondary_subcategory', '')).lower()

    if plan_subcategory == workout_subcategory:
        score += 20
        match_reasons.append(f"Perfect subcategory match: {plan_subcategory}")
    elif plan_subcategory == workout_secondary_subcategory:
        score += 15
        match_reasons.append(f"Secondary subcategory match: {plan_subcategory}")
    elif plan_subcategory in workout_subcategory or workout_subcategory in plan_subcategory:
        score += 10
        match_reasons.append(f"Related subcategory: {plan_subcategory} ~ {workout_subcategory}")

    # 3. Vibe match (0-20 points)
    plan_primary_vibe = str(plan_row.get('primary_vibe', '')).lower()
    plan_secondary_vibe = str(plan_row.get('secondary_vibe', '')).lower()
    workout_primary_vibe = str(workout_row.get('primary_vibe', '')).lower()
    workout_secondary_vibe = str(workout_row.get('secondary_vibe', '')).lower()

    vibe_score = 0
    if plan_primary_vibe and workout_primary_vibe:
        if plan_primary_vibe == workout_primary_vibe:
            vibe_score += 10
            match_reasons.append(f"Perfect primary vibe match: {plan_primary_vibe}")
        elif plan_primary_vibe == workout_secondary_vibe:
            vibe_score += 7
            match_reasons.append(f"Primary vibe matches secondary: {plan_primary_vibe}")
        # elif plan_primary_vibe in workout_primary_vibe or workout_primary_vibe in plan_primary_vibe:
        #     vibe_score += 5
        #     match_reasons.append(f"Related primary vibe: {plan_primary_vibe} ~ {workout_primary_vibe}")

    if plan_secondary_vibe and workout_secondary_vibe:
        if plan_secondary_vibe == workout_secondary_vibe:
            vibe_score += 10
            match_reasons.append(f"Perfect secondary vibe match: {plan_secondary_vibe}")
        elif plan_secondary_vibe == workout_primary_vibe:
            vibe_score += 7
            match_reasons.append(f"Secondary vibe matches primary: {plan_secondary_vibe}")
        elif plan_secondary_vibe in workout_secondary_vibe or workout_secondary_vibe in plan_secondary_vibe:
            vibe_score += 5
            match_reasons.append(f"Related secondary vibe: {plan_secondary_vibe} ~ {workout_secondary_vibe}")

    score += vibe_score

    # 4. Fitness level match (0-20 points)
    plan_fitness_level = str(plan_row.get('fitness_level', '')).lower()
    workout_fitness_level = str(workout_row.get('fitness_level', '')).lower()
    workout_secondary_fitness_level = str(workout_row.get('secondary_fitness_level', '')).lower()
    workout_tertiary_fitness_level = str(workout_row.get('tertiary_fitness_level', '')).lower()

    if plan_fitness_level == workout_fitness_level:
        score += 20
        match_reasons.append(f"Perfect fitness level match: {plan_fitness_level}")
    elif plan_fitness_level == workout_secondary_fitness_level:
        score += 15
        match_reasons.append(f"Secondary fitness level match: {plan_fitness_level}")
    elif plan_fitness_level == workout_tertiary_fitness_level:
        score += 10
        match_reasons.append(f"Tertiary fitness level match: {plan_fitness_level}")
    else:
        # If no exact match, try to match based on proximity
        # Beginner < Intermediate < Advanced
        fitness_levels = {'beginner': 1, 'intermediate': 2, 'advanced': 3}

        if plan_fitness_level in fitness_levels and workout_fitness_level in fitness_levels:
            level_diff = abs(fitness_levels[plan_fitness_level] - fitness_levels[workout_fitness_level])
            if level_diff == 1:
                score += 10
                match_reasons.append(f"Close fitness level: {plan_fitness_level} ~ {workout_fitness_level}")
            elif level_diff == 0:
                score += 20
                match_reasons.append(f"Fitness level match: {plan_fitness_level}")

    # 5. Duration match (0-20 points)
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
        score += 20
        match_reasons.append(f"Duration is perfect: {workout_duration}min ≈ {plan_duration}min")
    elif duration_diff_pct <= 0.2:  # Within 20%
        score += 15
        match_reasons.append(f"Duration is close: {workout_duration}min ~ {plan_duration}min")
    elif duration_diff_pct <= 0.3:  # Within 30%
        score += 10
        match_reasons.append(f"Duration is acceptable: {workout_duration}min vs {plan_duration}min")
    else:
        match_reasons.append(f"Duration mismatch: {workout_duration}min vs {plan_duration}min")

    return score, match_reasons


def get_workout_essence(workout_row):
    """Extract essence information from a workout"""
    essence = {
        'type': f"{workout_row.get('category', '')} - {workout_row.get('subcategory', '')}",
        'primary_vibe': workout_row.get('primary_vibe', ''),
        'secondary_vibe': workout_row.get('secondary_vibe', ''),
        'fitness_level': workout_row.get('fitness_level', ''),
        'secondary_fitness_level': workout_row.get('secondary_fitness_level', ''),
        'tertiary_fitness_level': workout_row.get('tertiary_fitness_level', '')
    }

    return essence


def match_workouts():
    """Main function to match workouts with plan specifications"""
    # Load data
    workout_plan, workout_library = load_data()

    # Process plan data
    plan_data = extract_plan_info(workout_plan)

    # Match each day's plan with the best workout
    matched_workouts = []

    for _, plan_row in plan_data.iterrows():
        best_score = -1
        best_match = None
        best_reasons = []

        for _, workout_row in workout_library.iterrows():
            score, reasons = calculate_match_score(plan_row, workout_row)

            if score > best_score:
                best_score = score
                best_match = workout_row
                best_reasons = reasons

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
                    'duration': plan_row.get('duration', 30)
                },
                'workout': {
                    'id': best_match.get('video_id', ''),
                    'title': best_match.get('video_title', ''),
                    'url': best_match.get('video_url', ''),
                    'category': best_match.get('category', ''),
                    'subcategory': best_match.get('subcategory', ''),
                    'duration': best_match.get('duration', '')
                },
                'match_score': best_score,
                'match_quality': 'Excellent' if best_score >= 80 else 'Good' if best_score >= 60 else 'Fair',
                'match_reasons': best_reasons,
                'workout_essence': workout_essence
            })

    return matched_workouts


def main():
    """Main function to run the workout matching process"""
    matched_workouts = match_workouts()

    # Save results to file
    with open('matched_workouts.json', 'w') as f:
        json.dump(matched_workouts, f, indent=2)

    # Print summary
    print(f"Successfully matched {len(matched_workouts)} workouts")

    # Show sample results
    print("\nSample matches:")
    for i, match in enumerate(matched_workouts[:3]):
        print(f"\n--- Day: {match['day']} ---")
        print(f"Workout: {match['workout']['title']}")
        print(f"Match score: {match['match_score']}/100 ({match['match_quality']})")
        print("Reasons:")
        for reason in match['match_reasons']:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()