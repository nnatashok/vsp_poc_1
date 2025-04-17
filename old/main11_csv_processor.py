import csv
import pandas as pd
import os
import re
from main11 import analyze_youtube_workout
import json
from urllib.parse import urlparse


def is_youtube_url(url):
    """Check if the given URL is a YouTube URL."""
    if not url or not isinstance(url, str):
        return False

    parsed_url = urlparse(url)
    return any(domain in parsed_url.netloc for domain in ['youtube.com', 'youtu.be', 'www.youtube.com'])


def process_csv_with_workout_analysis(input_csv_path, output_csv_path, cache_dir='workout_cache', force_refresh=False):
    """
    Process a CSV file containing workout links, analyze YouTube links using the analyze_youtube_workout function,
    and create a new CSV with original columns plus analysis results.

    Args:
        input_csv_path (str): Path to the input CSV file
        output_csv_path (str): Path to save the output CSV file
        cache_dir (str): Directory to store cached analysis results
        force_refresh (bool): Whether to force fresh analysis even if cached data exists
    """
    # Create cache directory if it doesn't exist
    os.makedirs(cache_dir, exist_ok=True)

    # Read the input CSV file
    try:
        df = pd.read_csv(input_csv_path)
        print(f"Successfully loaded CSV with {len(df)} rows and {len(df.columns)} columns")
        print(f"Columns: {df.columns.tolist()}")
    except Exception as e:
        print(f"Error reading CSV: {str(e)}")
        return

    # Identify which column contains the video links
    link_column = None
    for col in df.columns:
        if 'link' in col.lower() or 'url' in col.lower() or 'media' in col.lower():
            link_column = col
            break

    if not link_column:
        print("Could not find a column containing video links. Please check your CSV file.")
        return

    print(f"Using '{link_column}' as the column containing video links")

    # Filter for YouTube links only
    youtube_mask = df[link_column].apply(is_youtube_url)
    youtube_count = youtube_mask.sum()
    print(f"Found {youtube_count} YouTube links out of {len(df)} total entries")

    # Create columns for analysis results
    analysis_columns = [
        'analyzed_category',
        'analyzed_subcategory',
        'analyzed_complexity_level',
        'analyzed_equipment',
        'analyzed_body_parts',
        'analyzed_aerobic_function',
        'analyzed_strength_function',
        'analyzed_flexibility_function',
        'analyzed_vibes',  # Added column for vibes
        'analyzed_spirits',  # Added column for spirits
        'analyzed_category_confidence',
        'analyzed_subcategory_confidence',
        'analyzed_complexity_confidence',
        'analyzed_equipment_confidence',
        'analyzed_bodyparts_confidence',
        'analyzed_vibes_confidence',  # Added column for vibes confidence
        'analyzed_spirits_confidence'  # Added column for spirits confidence
    ]

    for col in analysis_columns:
        df[col] = None

    # Process YouTube links
    processed_count = 0
    for idx, row in df[youtube_mask].iterrows():
        youtube_url = row[link_column]
        print(f"Processing {processed_count + 1}/{youtube_count}: {youtube_url}")

        try:
            # Analyze the workout video
            analysis = analyze_youtube_workout(youtube_url, cache_dir=cache_dir, force_refresh=force_refresh)

            if 'error' in analysis:
                print(f"  Error analyzing video: {analysis['error']}")
                continue

            # Update the dataframe with analysis results
            df.at[idx, 'analyzed_category'] = analysis.get('category', '')
            df.at[idx, 'analyzed_subcategory'] = analysis.get('subcategory', '')
            df.at[idx, 'analyzed_complexity_level'] = analysis.get('complexityLevel', '')

            # Store confidence levels
            df.at[idx, 'analyzed_category_confidence'] = analysis.get('categoryConfidence', '')
            df.at[idx, 'analyzed_subcategory_confidence'] = analysis.get('subcategoryConfidence', '')
            df.at[idx, 'analyzed_complexity_confidence'] = analysis.get('complexityLevelConfidence', '')
            df.at[idx, 'analyzed_equipment_confidence'] = analysis.get('equipmentConfidence', '')
            df.at[idx, 'analyzed_bodyparts_confidence'] = analysis.get('bodyPartFocusConfidence', '')
            df.at[idx, 'analyzed_vibes_confidence'] = analysis.get('vibesConfidence', '')
            df.at[idx, 'analyzed_spirits_confidence'] = analysis.get('spiritsConfidence', '')

            # Convert equipment list to string
            equipment_list = analysis.get('equipment', [])
            df.at[idx, 'analyzed_equipment'] = ', '.join(equipment_list) if equipment_list else ''

            # Format body part focus as percentages
            body_parts = analysis.get('bodyPartFocus', {})
            if body_parts:
                body_parts_str = ', '.join([f"{part}: {int(value * 100)}%" for part, value in body_parts.items()])
                df.at[idx, 'analyzed_body_parts'] = body_parts_str

            # Format metabolic functions
            df.at[idx, 'analyzed_aerobic_function'] = ', '.join(analysis.get('aerobicMetabolicFunction', []))
            df.at[idx, 'analyzed_strength_function'] = ', '.join(analysis.get('strengthMetabolicFunction', []))
            df.at[idx, 'analyzed_flexibility_function'] = ', '.join(analysis.get('flexibilityMetabolicFunction', []))

            # Format vibes
            vibes = analysis.get('vibes', [])
            if vibes:
                vibes_str = ', '.join([f"{v['name']} ({int(v['prominence'] * 100)}%)" for v in vibes])
                df.at[idx, 'analyzed_vibes'] = vibes_str

            # Format spirits
            spirits = analysis.get('spirits', [])
            if spirits:
                spirits_str = ', '.join([f"{s['name']} ({int(s['prominence'] * 100)}%)" for s in spirits])
                df.at[idx, 'analyzed_spirits'] = spirits_str

            processed_count += 1
            print(
                f"  Successfully analyzed: {analysis.get('category')} / {analysis.get('subcategory')} / {analysis.get('complexityLevel')}")

        except Exception as e:
            print(f"  Error processing {youtube_url}: {str(e)}")

    # Save the updated dataframe to a new CSV file
    try:
        df.to_csv(output_csv_path, index=False)
        print(f"Successfully saved processed data to {output_csv_path}")
        print(f"Processed {processed_count} out of {youtube_count} YouTube videos")
    except Exception as e:
        print(f"Error saving CSV: {str(e)}")


def compare_results_with_ground_truth(processed_csv_path, output_report_path='comparison_report.txt'):
    """
    Compare the AI-analyzed results with the ground truth data and generate a report
    showing accuracy metrics.

    Args:
        processed_csv_path (str): Path to the processed CSV with both ground truth and analysis results
        output_report_path (str): Path to save the comparison report
    """
    try:
        df = pd.read_csv(processed_csv_path)

        # Define the pairs of columns to compare (ground truth column, analyzed column)
        comparison_pairs = [
            ('Category', 'analyzed_category'),
            ('SubCategory', 'analyzed_subcategory'),
            ('Fitness Level', 'analyzed_complexity_level'),
            ('Equipment Needed', 'analyzed_equipment')
        ]

        # Open a file to write the report
        with open(output_report_path, 'w') as f:
            f.write("# Comparison Report: Ground Truth vs. AI Analysis\n\n")

            total_youtube_entries = df['analyzed_category'].notna().sum()
            f.write(f"Total YouTube entries analyzed: {total_youtube_entries}\n\n")

            for gt_col, ai_col in comparison_pairs:
                if gt_col not in df.columns or ai_col not in df.columns:
                    f.write(f"Could not compare {gt_col} with {ai_col} - one or both columns missing\n\n")
                    continue

                # Filter rows where both columns have values
                mask = df[gt_col].notna() & df[ai_col].notna()
                valid_entries = mask.sum()

                if valid_entries == 0:
                    f.write(f"No valid entries to compare for {gt_col} vs {ai_col}\n\n")
                    continue

                # For equipment, we need special handling as formats may differ
                if 'Equipment' in gt_col:
                    # Count as match if all ground truth equipment is found in analyzed equipment
                    matches = 0
                    partial_matches = 0

                    for idx, row in df[mask].iterrows():
                        gt_equip = set([e.strip().lower() for e in str(row[gt_col]).split(',') if e.strip()])
                        ai_equip = set([e.strip().lower() for e in str(row[ai_col]).split(',') if e.strip()])

                        if gt_equip.issubset(ai_equip):
                            matches += 1
                        elif gt_equip.intersection(ai_equip):
                            partial_matches += 1

                    exact_match_rate = matches / valid_entries
                    partial_match_rate = partial_matches / valid_entries

                    f.write(f"## {gt_col} vs {ai_col}\n")
                    f.write(f"Exact match rate: {exact_match_rate:.2%} ({matches}/{valid_entries})\n")
                    f.write(f"Partial match rate: {partial_match_rate:.2%} ({partial_matches}/{valid_entries})\n")
                    f.write(f"Combined match rate: {(matches + partial_matches) / valid_entries:.2%}\n\n")

                else:
                    # For other columns, do direct comparison
                    # First, standardize the values by lowercasing and removing extra whitespace
                    df[f'{gt_col}_std'] = df[gt_col].apply(lambda x: str(x).lower().strip() if pd.notna(x) else x)
                    df[f'{ai_col}_std'] = df[ai_col].apply(lambda x: str(x).lower().strip() if pd.notna(x) else x)

                    # Calculate exact matches
                    exact_matches = (df[f'{gt_col}_std'] == df[f'{ai_col}_std']).sum()
                    exact_match_rate = exact_matches / valid_entries

                    # Calculate closest matches (when ground truth is contained in the analyzed value or vice versa)
                    close_matches = 0
                    for idx, row in df[mask].iterrows():
                        gt_val = str(row[f'{gt_col}_std'])
                        ai_val = str(row[f'{ai_col}_std'])
                        if gt_val in ai_val or ai_val in gt_val:
                            close_matches += 1

                    close_match_rate = close_matches / valid_entries

                    f.write(f"## {gt_col} vs {ai_col}\n")
                    f.write(f"Exact match rate: {exact_match_rate:.2%} ({exact_matches}/{valid_entries})\n")
                    f.write(f"Close match rate: {close_match_rate:.2%} ({close_matches}/{valid_entries})\n\n")

            # Add a section for unique values in each column
            f.write("# Value Distributions\n\n")
            for gt_col, ai_col in comparison_pairs:
                if gt_col not in df.columns or ai_col not in df.columns:
                    continue

                f.write(f"## {gt_col} values in ground truth:\n")
                value_counts = df[gt_col].value_counts().to_dict()
                for val, count in value_counts.items():
                    if pd.notna(val):
                        f.write(f"- {val}: {count}\n")
                f.write("\n")

                f.write(f"## {ai_col} values in AI analysis:\n")
                value_counts = df[ai_col].value_counts().to_dict()
                for val, count in value_counts.items():
                    if pd.notna(val):
                        f.write(f"- {val}: {count}\n")
                f.write("\n")

            # Add the new sections for vibes and spirits distributions
            ai_vibes_col = 'analyzed_vibes'
            ai_spirits_col = 'analyzed_spirits'

            if ai_vibes_col in df.columns:
                f.write("## Vibes distributions in AI analysis:\n")
                # Extract the vibe names without the percentages
                vibe_names = []
                for vibes_str in df[ai_vibes_col].dropna():
                    for vibe_item in vibes_str.split(', '):
                        if ' (' in vibe_item:
                            vibe_name = vibe_item.split(' (')[0]
                            vibe_names.append(vibe_name)

                # Count occurrences of each vibe
                vibe_counts = pd.Series(vibe_names).value_counts().to_dict()
                for vibe, count in vibe_counts.items():
                    f.write(f"- {vibe}: {count}\n")
                f.write("\n")

            if ai_spirits_col in df.columns:
                f.write("## Spirits distributions in AI analysis:\n")
                # Extract the spirit names without the percentages
                spirit_names = []
                for spirits_str in df[ai_spirits_col].dropna():
                    for spirit_item in spirits_str.split(', '):
                        if ' (' in spirit_item:
                            spirit_name = spirit_item.split(' (')[0]
                            spirit_names.append(spirit_name)

                # Count occurrences of each spirit
                spirit_counts = pd.Series(spirit_names).value_counts().to_dict()
                for spirit, count in spirit_counts.items():
                    f.write(f"- {spirit}: {count}\n")
                f.write("\n")

        print(f"Comparison report saved to {output_report_path}")

    except Exception as e:
        print(f"Error generating comparison report: {str(e)}")


if __name__ == "__main__":
    # Set your file paths here
    input_csv = "exercise videos - Ground truth.csv"
    output_csv = "main_11_exercise_videos_with_analysis.csv"

    # Process the CSV file
    process_csv_with_workout_analysis(
        input_csv_path=input_csv,
        output_csv_path=output_csv,
        cache_dir="cache_11"
    )

    # Generate comparison report
    compare_results_with_ground_truth(
        processed_csv_path=output_csv,
        output_report_path="main_11_workout_analysis_comparison.txt"
    )