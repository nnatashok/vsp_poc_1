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
    # Find date column (starts with 2025-)
    date_col = [col for col in workout_plan.columns if str(col).startswith('2025-')][0]

    plan_data = []
    for _, row in workout_plan.iterrows():
        day_info = {'day': row[date_col]}

        # Extract duration - check common duration columns
        for duration_col in ['30', '28']:
            if duration_col in row and pd.notna(row[duration_col]):
                try:
                    day_info['duration'] = int(row[duration_col])
                    break
                except (ValueError, TypeError):
                    pass

        if 'duration' not in day_info:
            day_info['duration'] = 30  # Default duration

        # Extract workout type
        for category in ['Cardio', 'Strength', 'Flexibility']:
            if category in row and pd.notna(row[category]):
                day_info['category'] = row[category]
                break

        for subcategory in ['HIIT', 'Calisthenics', 'Yoga', 'Stretching', 'Walking']:
            if subcategory in row and pd.notna(row[subcategory]):
                day_info['subcategory'] = row[subcategory]
                break

        # Extract workout experience types (vibe/spirit)
        for key in row.index:
            if key in ['The Adrenaline Rush', 'The Competitor', 'The Progression Quest',
                       'The Firestarter', 'The Zen Flow', 'The Deep Recharge']:
                day_info['workout_type'] = key

            if row[key] in ['The Adrenaline Rush', 'The Competitor', 'The Progression Quest',
                            'The Firestarter', 'The Zen Flow', 'The Deep Recharge',
                            'The Endorphin Wave', 'The Warrior Workout']:
                day_info['workout_feel'] = row[key]

        plan_data.append(day_info)

    return pd.DataFrame(plan_data)


def calculate_match_score(plan_row, workout_row):
    """Calculate how well a workout matches the plan specification"""
    score = 0
    match_reasons = []

    # 1. Category match (0-30 points)
    plan_category = str(plan_row.get('category', '')).lower()
    workout_category = str(workout_row.get('category', '')).lower()

    if plan_category == workout_category:
        score += 30
        match_reasons.append(f"Perfect category match: {plan_category}")
    elif plan_category in workout_category or workout_category in plan_category:
        score += 20
        match_reasons.append(f"Related category: {plan_category} ~ {workout_category}")

    # 2. Subcategory match (0-30 points)
    plan_subcategory = str(plan_row.get('subcategory', '')).lower()
    workout_subcategory = str(workout_row.get('subcategory', '')).lower()
    workout_secondary_subcategory = str(workout_row.get('secondary_subcategory', '')).lower()

    if plan_subcategory == workout_subcategory:
        score += 30
        match_reasons.append(f"Perfect subcategory match: {plan_subcategory}")
    elif plan_subcategory == workout_secondary_subcategory:
        score += 25
        match_reasons.append(f"Secondary subcategory match: {plan_subcategory}")
    elif plan_subcategory in workout_subcategory or workout_subcategory in plan_subcategory:
        score += 15
        match_reasons.append(f"Related subcategory: {plan_subcategory} ~ {workout_subcategory}")

    # 3. Workout experience match (0-20 points)
    # Define workout type affinities - map workout types to matching spirits and vibes
    workout_type_map = {
        'The Adrenaline Rush': ['High-Energy & Intense', 'The Endorphin Wave', 'The Warrior Workout'],
        'The Competitor': ['High-Energy & Intense', 'The Warrior Workout', 'The Tactical Athlete'],
        'The Progression Quest': ['Structured & Disciplined', 'The Meditative Grind', 'The Power Builder'],
        'The Firestarter': ['High-Energy & Intense', 'The Endorphin Wave', 'The Groove Session'],
        'The Zen Flow': ['Soothing & Restorative', 'Flow & Rhythm', 'The Zen Flow'],
        'The Deep Recharge': ['Soothing & Restorative', 'The Reboot Workout', 'The Zen Flow']
    }

    plan_type = str(plan_row.get('workout_type', ''))
    plan_feel = str(plan_row.get('workout_feel', ''))

    workout_spirit = str(workout_row.get('primary_spirit', ''))
    workout_vibe = str(workout_row.get('primary_vibe', ''))

    # Check if workout spirit/vibe aligns with plan type
    if plan_type in workout_type_map:
        matching_experiences = workout_type_map[plan_type]

        if workout_spirit in matching_experiences or workout_vibe in matching_experiences:
            score += 20
            match_reasons.append(f"Workout experience matches {plan_type} perfectly")
        else:
            # Check for partial text matches
            for exp in matching_experiences:
                if exp.lower() in workout_spirit.lower() or exp.lower() in workout_vibe.lower():
                    score += 15
                    match_reasons.append(f"Workout experience partially matches {plan_type}")
                    break

    # 4. Duration match (0-20 points)
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
        'spirit': workout_row.get('primary_spirit', ''),
        'vibe': workout_row.get('primary_vibe', ''),
        'level': workout_row.get('fitness_level', '')
    }

    # Try to extract detailed analysis from JSON if available
    try:
        if pd.notna(workout_row.get('full_analysis_json')):
            analysis = json.loads(workout_row['full_analysis_json'])

            # Extract key insights if available
            if 'spirit' in analysis and 'spirits' in analysis['spirit']:
                essence['spirit_details'] = analysis['spirit']['spirits']

            if 'vibe' in analysis and 'vibes' in analysis['vibe']:
                essence['vibe_details'] = analysis['vibe']['vibes']
    except:
        # Ignore JSON parsing errors
        pass

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
                    'workout_type': plan_row.get('workout_type', ''),
                    'workout_feel': plan_row.get('workout_feel', ''),
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