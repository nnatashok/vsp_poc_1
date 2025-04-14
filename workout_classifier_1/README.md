# YouTube Workout Classifier

A comprehensive tool for analyzing and classifying YouTube workout videos. This system analyzes workout videos and categorizes them based on several dimensions:

- **Categories**: The type of workout (e.g., Yoga, HIIT, Running)
- **Fitness Level**: Required skill and intensity level (Beginner, Intermediate, Advanced)
- **Equipment**: What tools are needed for the workout
- **Spirit**: The energetic quality of the workout
- **Vibe**: The emotional/experiential quality of the workout

## Setup

### Prerequisites

- Python 3.11+
- YouTube Data API v3 key
- OpenAI API key

### Installation

1. Clone this repository
2. Install the required dependencies (TBD)
```

3. Set up your API keys by creating a `.env` file in one of these locations:
   - In the project directory
   - One level up from the project directory
   - Two levels up from the project directory

Example `.env` file:

```
YOUTUBE_API_KEY=your_youtube_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

### Basic Usage

Process a CSV file containing YouTube URLs:

```bash
python csv_processor.py --input workouts.csv --output results.csv
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--input` | Path to input CSV file | all_workouts_1.csv |
| `--output` | Path to output CSV file | workouts_analyzed.csv |
| `--max` | Maximum number of workouts to process | None (process all) |
| `--no-category` | Disable workout category analysis | Enabled by default |
| `--no-fitness` | Disable fitness level analysis | Enabled by default |
| `--no-vibe` | Disable workout vibe analysis | Enabled by default |
| `--no-spirit` | Disable workout spirit analysis | Enabled by default |
| `--no-equipment` | Disable required equipment analysis | Enabled by default |

### Examples

Process only the first 10 workouts:
```bash
python csv_processor.py --input workouts.csv --output results.csv --max 10
```

Skip vibe and spirit analysis:
```bash
python csv_processor.py --input workouts.csv --output results.csv --no-vibe --no-spirit
```

## Input CSV Format

The input CSV should contain YouTube URLs in any column. The processor will identify and extract all valid YouTube video URLs from the entire CSV.

Example:
```csv
id,title,video_url,notes
1,Morning Workout,https://www.youtube.com/watch?v=AbCdEfGhIjK,Good one
2,HIIT Session,https://www.youtube.com/watch?v=LmNoPqWxyz1,Intense
```

## Output Format

The output CSV includes detailed analysis with the following columns:

- Basic info: video_id, video_url, video_title, channel_title, duration
- Category info: category, subcategory, secondary_category, secondary_subcategory
- Fitness level: fitness_level, secondary_fitness_level, tertiary_fitness_level
- Equipment: primary_equipment, secondary_equipment, tertiary_equipment
- Spirit: primary_spirit, secondary_spirit
- Vibe: primary_vibe, secondary_vibe
- full_analysis_json: Complete analysis in JSON format

## Components

- **csv_processor.py**: Main entry point, processes CSV files with YouTube URLs
- **unified_workout_classifier.py**: Core analyzer that classifies workouts using AI
- **db_transformer.py**: Transforms analysis results into database-friendly structure
- **env_utils.py**: Handles environment variable loading from .env files
- **category_classifier.py**: Specialized classifier for workout categories
- **fitness_level_classifier.py**: Analyzes required fitness level
- **equipment_classifier.py**: Identifies equipment needed
- **spirit_classifier.py**: Analyzes workout energy and spirit
- **vibe_classifier.py**: Analyzes emotional and experiential qualities

## Caching

The system caches analysis results to avoid re-processing the same videos. The cache is stored in the `cache` directory. To force a fresh analysis, use code:

```python
result = analyze_youtube_workout(url, force_refresh=True)
```

## Categories Explained

### Workout Categories
- **Cardio**: Elliptical, HIIT, Indoor biking, Mat, Running, Treadmill, Walking
- **Flexibility**: Pilates, Stretching, Yoga
- **Rest**: Breathing exercises, Meditation
- **Strength**: Body weight, Calisthenics, Weight workout

### Fitness Levels
- **Beginner**: Suitable for people new to exercise
- **Intermediate**: For those with consistent exercise experience (3-6 months)
- **Advanced**: For dedicated fitness enthusiasts (6+ months)

### Equipment Categories
- **Weights**: Dumbbells, Kettlebells, Medicine balls, Barbell, Weight bench
- **Rower**: Rowing machine
- **Treadmill**: Treadmill
- **Exercise Bike**: Exercise bike
- **Other**: Any other equipment

## Troubleshooting

### API Key Issues
If you encounter authentication errors, check that your .env file is properly configured and in one of the expected locations.

### YouTube URL Extraction
If some YouTube URLs aren't being processed, ensure they're valid YouTube watch URLs (not playlists or channel URLs).

### Rate Limiting
The system includes retry logic for API rate limits, but if you're processing many videos, you might need to increase the retry limits in unified_workout_classifier.py.

## License

[Insert your license information here]
