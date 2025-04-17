"""
This script scans a directory of JSON files, flattens their structure,
and generates a frequency table of all keys (including nested ones).
# 
The frequency table includes:
- How often each key appears
- How often each key has a meaningful (non-empty) value
- The data types encountered for each key
# 
Useful for analyzing large JSON datasets with inconsistent schema.
"""
# 
import os
import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Any, List
import pandas as pd
from tqdm import tqdm
# 
# --- Config ---
DATA_FOLDER = Path('/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/data_raw/hydrow_jsons')#Path("placeholder") # directory with all json files
FREQ_TABLE_OUT = Path('/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/data_raw/hydrow_jsons_field_frequency_table.csv') #Path("placeholder") #path to output stats csv file 
# 
# --- Utils ---
def flatten_json(y: Dict[str, Any], prefix='') -> Dict[str, Any]:
    """
    Recursively flattens a nested JSON object into a flat dictionary with dot-separated keys.
    Handles both dictionaries and lists of dictionaries.
# 
    Args:
        y (Dict[str, Any]): The JSON object to flatten.
        prefix (str): Used internally to prefix nested keys.
# 
    Returns:
        Dict[str, Any]: A flat dictionary with dot notation keys.
    """
    out = {}
    for k, v in y.items():
        if k == "mediaSources":
            test = ""  # Debug hook (can be removed)
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_json(v, key))
        elif isinstance(v, list):
            for elem_id, elem in enumerate(v):
                if isinstance(elem, dict):
                    out.update(flatten_json(elem, f"{key}.{elem_id}"))
        else:
            out[key] = v
    return out
# 
def is_meaningful(value: Any) -> bool:
    """
    Determines if a value is 'meaningful' — i.e., not empty, null, or placeholder-like.
# 
    Args:
        value (Any): The value to evaluate.
# 
    Returns:
        bool: True if the value is meaningful, False otherwise.
    """
    if value is None:
        return False
# 
    if isinstance(value, str):
        return value.strip() not in {"", "n/a", "null", "none", "undefined", "-"}
# 
    if isinstance(value, (list, dict, set)):
        return len(value) > 0
# 
    if isinstance(value, (int, float)):
        return value != 0 and not pd.isna(value)
# 
    return True
# 
# --- Step 1: Frequency Table Generator ---
def generate_key_frequency(folder: Path, sample_size: int = None) -> pd.DataFrame:
    """
    Processes a folder of JSON files and generates a frequency table of keys,
    and prints all unique musicGenre and workoutTypes values with their counts.
    """
    key_counts = Counter()
    type_examples = defaultdict(set)
    non_empty_counts = Counter()
    music_genre_counter = Counter()
    workout_types_counter = Counter()  # <-- NEW
# 
    files = list(folder.glob("*.json"))
    if sample_size:
        files = files[:sample_size]
# 
    for file in tqdm(files, desc="Building key frequency table"):
        with open(file, 'r') as f:
            try:
                data = json.load(f)
                flat = flatten_json(data)
# 
                # Count musicGenre values if present
                for key, val in flat.items():
                    if key.endswith("musicGenre") and is_meaningful(val):
                        music_genre_counter[str(val).strip()] += 1
# 
                    # Count workoutTypes values
                    if key.endswith("workoutTypes") and is_meaningful(val):
                        if isinstance(val, list):
                            for item in val:
                                workout_types_counter[str(item).strip()] += 1
                        else:
                            workout_types_counter[str(val).strip()] += 1
# 
                key_counts.update(flat.keys())
                for k, v in flat.items():
                    type_examples[k].add(type(v).__name__)
                    if is_meaningful(v):
                        non_empty_counts[k] += 1
            except Exception as e:
                print(f"Failed to process {file.name}: {e}")
# 
    # Print out musicGenre statistics
    if music_genre_counter:
        print("\n🎵 Detected musicGenre values and counts:")
        for genre, count in music_genre_counter.most_common():
            print(f"{genre}: {count}")
    else:
        print("\n⚠️ No musicGenre values found in dataset.")
# 
    # Print out workoutTypes statistics
    if workout_types_counter:
        print("\n💪 Detected workoutTypes values and counts:")
        for wtype, count in workout_types_counter.most_common():
            print(f"{wtype}: {count}")
    else:
        print("\n⚠️ No workoutTypes values found in dataset.")
# 
    df = pd.DataFrame.from_dict(key_counts, orient='index', columns=['field count'])
    df['non empty count'] = df.index.map(lambda k: non_empty_counts.get(k, 0))
    df['data types'] = df.index.map(lambda k: ', '.join(sorted(type_examples[k])))
    df = df.sort_index()
    return df
# 
# 
# --- Main Entrypoint ---
if __name__ == "__main__":
    # Generate the frequency table and save it to CSV
    freq_df = generate_key_frequency(DATA_FOLDER)
    freq_df.to_csv(FREQ_TABLE_OUT)
    print(f"Field frequency table saved to {FREQ_TABLE_OUT}")


# import os
# import json
# from pathlib import Path
# from collections import Counter
# from tqdm import tqdm

# # --- Config ---
# JSON_DIR = Path("/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/data_raw/hydrow_jsons")

# # --- Initialize Counter ---
# stroke_name_counter = Counter()

# # --- Loop over JSON files ---
# for file_path in tqdm(list(JSON_DIR.glob("*.json")), desc="Processing JSON files"):
#     try:
#         with open(file_path, 'r') as f:
#             data = json.load(f)

#             # Navigate directly to instructors.stroke.name
#             instructors = data.get("instructors", {})
#             stroke = instructors.get("stroke", {})
#             name = stroke.get("name")

#             if isinstance(name, str) and name.strip():
#                 stroke_name_counter[name.strip()] += 1

#     except Exception as e:
#         print(f"⚠️ Failed to process {file_path.name}: {e}")

# # --- Output counts ---
# print("\n🧑‍🏫 Detected instructors.stroke.name values and counts:")
# for name, count in stroke_name_counter.most_common():
#     print(f"{name}: {count}")
