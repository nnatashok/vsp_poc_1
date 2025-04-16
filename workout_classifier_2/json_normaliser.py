# json_schema_normalizer.py

import os
import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Any, List
import pandas as pd
from tqdm import tqdm

# --- Config ---
DATA_FOLDER = Path("/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/data_raw/hydrow_jsons")  # TODO: update this
FREQ_TABLE_OUT = Path("/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/data_raw/hydrow_jsons_field_frequency_table.csv")

# --- Utils ---
def flatten_json(y: Dict[str, Any], prefix='') -> Dict[str, Any]:
    out = {}
    for k, v in y.items():
        if k == "mediaSources":
            test = ""
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_json(v, key))
        elif isinstance(v, list):
            for elem_id, elem in enumerate(v):
                if isinstance(elem, dict): out.update(flatten_json(elem, f"{key}.{elem_id}"))
        else:
            out[key] = v
    return out

def is_meaningful(value: Any) -> bool:
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
    # 1. Generate key frequency table
    freq_df = generate_key_frequency(DATA_FOLDER)
    freq_df.to_csv(FREQ_TABLE_OUT)
    print(f"Field frequency table saved to {FREQ_TABLE_OUT}")
