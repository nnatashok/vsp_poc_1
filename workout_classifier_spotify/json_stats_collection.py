import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Any
import pandas as pd
from tqdm import tqdm

# --- Config ---
WORKOUT_CSV = Path('/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/workout_classifier_spotify/Workout.csv')  # Replace with your actual file path
FREQ_TABLE_OUT = Path('/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/cache/spotify_json_field_frequency_table.csv')  # Replace with your output file path

# --- Utils ---
def flatten_json(y: Dict[str, Any], prefix='') -> Dict[str, Any]:
    out = {}
    for k, v in y.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_json(v, key))
        elif isinstance(v, list):
            for i, elem in enumerate(v):
                if isinstance(elem, dict):
                    out.update(flatten_json(elem, f"{key}.{i}"))
        else:
            out[key] = v
    return out

def is_meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "n/a", "null", "none", "undefined", "-"}
    if isinstance(value, (list, dict, set)):
        return len(value) > 0
    if isinstance(value, (int, float)):
        return value != 0 and not pd.isna(value)
    return True

# --- Main Analysis ---
def analyze_spotify_jsons_from_csv(file_path: Path):
    df = pd.read_csv(file_path)
    if df.shape[1] < 12:
        raise ValueError("CSV does not contain enough columns to access columns H and L.")

    key_counts = Counter()
    non_empty_counts = Counter()
    type_examples = defaultdict(set)
    value_counts = defaultdict(Counter)
    music_genre_counter = Counter()
    workout_types_counter = Counter()

    total_spotify_entries = 0

    for i, row in tqdm(df.iterrows(), total=len(df), desc="Processing CSV rows"):
        marker = str(row.iloc[11]).lower()  # Column L (index 11)
        json_str = row.iloc[7]  # Column H (index 7)

        if "spotify" in marker and isinstance(json_str, str) and json_str.strip().startswith("{"):
            try:
                data = json.loads(json_str)
                flat = flatten_json(data)
                total_spotify_entries += 1

                for k, v in flat.items():
                    key_counts[k] += 1
                    type_examples[k].add(type(v).__name__)
                    if is_meaningful(v):
                        non_empty_counts[k] += 1
                        val_str = str(v).strip()
                        value_counts[k][val_str] += 1

                    # Count specific field values
                    if k.endswith("musicGenre") and is_meaningful(v):
                        music_genre_counter[str(v).strip()] += 1
                    if k.endswith("workoutTypes") and is_meaningful(v):
                        if isinstance(v, list):
                            for item in v:
                                workout_types_counter[str(item).strip()] += 1
                        else:
                            workout_types_counter[str(v).strip()] += 1

            except Exception as e:
                print(f"⚠️ Failed to parse JSON in row {i}: {e}")

    # Print statistics
    print(f"\n📊 Total Spotify entries detected: {total_spotify_entries}")

    # Create output dataframe
    df_out = pd.DataFrame.from_dict(key_counts, orient='index', columns=['field count'])
    df_out['non empty count'] = df_out.index.map(lambda k: non_empty_counts.get(k, 0))
    df_out['data types'] = df_out.index.map(lambda k: ', '.join(sorted(type_examples[k])))
    df_out['most frequent values'] = df_out.index.map(
        lambda k: '; '.join([f"{val} ({cnt})" for val, cnt in value_counts[k].most_common(100)])
    )
    df_out = df_out.sort_index()

    return df_out, total_spotify_entries

# --- Entrypoint ---
if __name__ == "__main__":
    stats_df, total_count = analyze_spotify_jsons_from_csv(WORKOUT_CSV)
    stats_df.to_csv(FREQ_TABLE_OUT, sep="*")
    print(f"\n✅ Field frequency table saved to {FREQ_TABLE_OUT}")
