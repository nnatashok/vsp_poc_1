"""
This script scans a directory of JSON files, flattens their structure,
and generates a frequency table of all keys (including nested ones).

The frequency table includes:
- How often each key appears
- How often each key has a meaningful (non-empty) value
- The data types encountered for each key

Useful for analyzing large JSON datasets with inconsistent schema.
"""

import os
import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Any, List
import pandas as pd
from tqdm import tqdm

# --- Config ---
DATA_FOLDER = Path("placeholder") # directory with all json files
FREQ_TABLE_OUT = Path("placeholder") #path to  ouutput stats csv file 

# --- Utils ---
def flatten_json(y: Dict[str, Any], prefix='') -> Dict[str, Any]:
    """
    Recursively flattens a nested JSON object into a flat dictionary with dot-separated keys.
    Handles both dictionaries and lists of dictionaries.

    Args:
        y (Dict[str, Any]): The JSON object to flatten.
        prefix (str): Used internally to prefix nested keys.

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

def is_meaningful(value: Any) -> bool:
    """
    Determines if a value is 'meaningful' — i.e., not empty, null, or placeholder-like.

    Args:
        value (Any): The value to evaluate.

    Returns:
        bool: True if the value is meaningful, False otherwise.
    """
    if value is None:
        return False

    if isinstance(value, str):
        return value.strip() not in {"", "n/a", "null", "none", "undefined", "-"}

    if isinstance(value, (list, dict, set)):
        return len(value) > 0

    if isinstance(value, (int, float)):
        return value != 0 and not pd.isna(value)

    return True

# --- Step 1: Frequency Table Generator ---
def generate_key_frequency(folder: Path, sample_size: int = None) -> pd.DataFrame:
    """
    Processes a folder of JSON files and generates a frequency table of keys.

    Args:
        folder (Path): Directory containing JSON files.
        sample_size (int, optional): Number of files to process. Defaults to all.

    Returns:
        pd.DataFrame: A DataFrame containing key frequencies, non-empty counts, and data types.
    """
    key_counts = Counter()
    type_examples = defaultdict(set)
    non_empty_counts = Counter()

    files = list(folder.glob("*.json"))
    if sample_size:
        files = files[:sample_size]

    for file in tqdm(files, desc="Building key frequency table"):
        with open(file, 'r') as f:
            try:
                data = json.load(f)
                flat = flatten_json(data)
                key_counts.update(flat.keys())
                for k, v in flat.items():
                    type_examples[k].add(type(v).__name__)
                    if is_meaningful(v):
                        non_empty_counts[k] += 1
            except Exception as e:
                print(f"Failed to process {file.name}: {e}")

    df = pd.DataFrame.from_dict(key_counts, orient='index', columns=['field count'])
    df['non empty count'] = df.index.map(lambda k: non_empty_counts.get(k, 0))
    df['data types'] = df.index.map(lambda k: ', '.join(sorted(type_examples[k])))
    df = df.sort_index()
    return df

# --- Main Entrypoint ---
if __name__ == "__main__":
    # Generate the frequency table and save it to CSV
    freq_df = generate_key_frequency(DATA_FOLDER)
    freq_df.to_csv(FREQ_TABLE_OUT)
    print(f"Field frequency table saved to {FREQ_TABLE_OUT}")
