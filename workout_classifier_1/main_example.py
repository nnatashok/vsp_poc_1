# Example usage of the unified workout classifier

from unified_workout_classifier import analyze_youtube_workout, transform_to_db_structure
import json

def main():
    # Analyze a workout video with specific classifiers enabled
    result = analyze_youtube_workout(
        "https://www.youtube.com/watch?v=zZD1H7XTTKc",  # Replace with any workout video URL
        force_refresh=False,  # Set to True to ignore cache
        enable_category=True,
        enable_fitness_level=True,
        enable_vibe=True,
        enable_spirit=True,
        enable_equipment=True
    )
    
    # Print the full analysis in a readable format
    print("Full Analysis:")
    print(json.dumps(result, indent=2))
    
    # Transform to database structure
    db_structure = transform_to_db_structure(result)
    print("\nDatabase Structure:")
    print(json.dumps(db_structure, indent=2))
    
    # Example of analyzing only specific dimensions
    category_only = analyze_youtube_workout(
        "https://www.youtube.com/watch?v=zZD1H7XTTKc",
        enable_category=True,
        enable_fitness_level=False,
        enable_vibe=False,
        enable_spirit=False,
        enable_equipment=False
    )
    
    print("\nCategory Analysis Only:")
    print(json.dumps(category_only, indent=2))
    
    # Even with partial analysis, we can transform to database structure
    partial_db_structure = transform_to_db_structure(category_only)
    print("\nPartial Database Structure:")
    print(json.dumps(partial_db_structure, indent=2))

if __name__ == "__main__":
    main()