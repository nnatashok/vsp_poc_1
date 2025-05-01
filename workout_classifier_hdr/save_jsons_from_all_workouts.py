import pandas as pd
import json
import os
from datetime import datetime

# Paths
csv_path = '/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/data_raw/Workout.csv'  # <-- change this
output_dir = '/home/karalandes/Documents/Juliy/VideoClfv1/vsp_poc_1/data_raw/hydrow_jsons/'

# Ensure the output directory exists
os.makedirs(output_dir, exist_ok=True)

# Read the CSV
df = pd.read_csv(csv_path)

# Process each row
for i, row in df.iterrows():
    if row['source1']!='hydrow': continue
    details_json = row['json_details']

    try:
        # Parse JSON
        data = json.loads(details_json)

        # Construct filename
        filename = f"{data['videoDateTime'][:4]}_{data['id']}.json"
        filepath = os.path.join(output_dir, filename)

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"Error processing row {i}: {e}")
