import json
from importlib.metadata import metadata
from os import listdir
from os.path import join

import pandas as pd

videos_dir = 'videos'
tw_index_id = '67bd08f347ebd55b1eab9e54'
df_gt = pd.read_csv('exercise videos - Ground truth.csv', index_col='UID')
res_filepath = 'res.csv'

# noinspection PyShadowingNames
def read_json(uid, name):
    return json.load(open(join(videos_dir, uid, name + '.json')))

workout_uids = listdir(videos_dir)
new_df = df_gt.loc[workout_uids].copy(deep=True)
for col in ['Duration', 'Source', 'Category', 'SubCategory' , 'Name', 'Equipment Needed', 'Trainer' , 'Fitness Level']:
    new_df[col] = ''

new_df['Cardio metabolic function'] = ''
new_df['Strength metabolic function'] = ''
new_df['Flexibility metabolic function'] = ''

new_df['Body focus'] = ''

new_df['Arms usage %'] = ''
new_df['Chest usage %'] = ''
new_df['Back usage %'] = ''
new_df['Legs usage %'] = ''
new_df['Arms exercises'] = ''
new_df['Chest exercises'] = ''
new_df['Back exercises'] = ''
new_df['Legs exercises'] = ''

new_df['Beginner exercises %'] = ''
new_df['Intermediate exercises %'] = ''
new_df['Advanced exercises %'] = ''
new_df['Beginner exercises'] = ''
new_df['Intermediate exercises'] = ''
new_df['Advanced exercises'] = ''

for uid in workout_uids:
    new_df.loc[uid, 'Source'] = 'YouTube'

    metadata_dict = read_json(uid, 'metadata')
    new_df.loc[uid, 'Duration'] = metadata_dict['duration_s']//60
    new_df.loc[uid, 'Name'] = metadata_dict['title']

    category_dict = read_json(uid, 'category')
    new_df.loc[uid, 'Category'] = category_dict['category']
    new_df.loc[uid, 'SubCategory'] = category_dict['subcategory']

    trainer_dict = read_json(uid, 'trainer')
    new_df.loc[uid, 'Trainer'] = trainer_dict['trainer_name']

    equipment_needed_dict = read_json(uid, 'equipment_needed')
    new_df.loc[uid, 'Equipment Needed'] = ' ,'.join(equipment_needed_dict['equipment'])

    complexity_dict = read_json(uid, 'complexity')
    fitness_levels = []
    if complexity_dict['beginner_exercises_percent'] >= 30:
        fitness_levels.append('Beginner')
    if complexity_dict['intermediate_exercises_percent'] >= 30:
        fitness_levels.append('Intermediate')
    if complexity_dict['advanced_exercises_percent'] >= 30:
        fitness_levels.append('Advanced')
    new_df.loc[uid, 'Fitness Level'] = ', '.join(fitness_levels)

    new_df.loc[uid, 'Beginner exercises %'] = complexity_dict['beginner_exercises_percent']
    new_df.loc[uid, 'Intermediate exercises %'] = complexity_dict['intermediate_exercises_percent']
    new_df.loc[uid, 'Advanced exercises %'] = complexity_dict['advanced_exercises_percent']

    new_df.loc[uid, 'Beginner exercises'] = ', '.join(complexity_dict['beginner_exercises'])
    new_df.loc[uid, 'Intermediate exercises'] = ', '.join(complexity_dict['intermediate_exercises'])
    new_df.loc[uid, 'Advanced exercises'] = ', '.join(complexity_dict['advanced_exercises'])

    if category_dict['category'] == 'Cardio':
        cardio_type_dict = read_json(uid, 'cardio_type')
        new_df.loc[uid, 'Cardio metabolic function'] = cardio_type_dict['type']
    elif category_dict['category'] == 'Strength':
        strength_type_dict = read_json(uid, 'strength_type')
        new_df.loc[uid, 'Strength metabolic function'] = strength_type_dict['type']
    elif category_dict['category'] == 'Flexibility':
        flexibility_type_dict = read_json(uid, 'flexibility_type')
        new_df.loc[uid, 'Flexibility metabolic function'] = flexibility_type_dict['type']

    if category_dict['category'] in ['Cardio', 'Strength']:
        body_parts_usage_dict = read_json(uid, 'body_parts_usage')

        if (body_parts_usage_dict['arms_usage_percent'] >= 30 and
                body_parts_usage_dict['chest_usage_percent'] >= 30 and
                body_parts_usage_dict['back_usage_percent'] >= 30 and
                body_parts_usage_dict['legs_usage_percent'] >= 30):
            new_df.loc[uid, 'Body focus'] = 'Full body workout'
        else:
            body_focus_list = []
            if body_parts_usage_dict['arms_usage_percent'] >= 30:
                body_focus_list.append('Arms')
            if body_parts_usage_dict['chest_usage_percent'] >= 30:
                body_focus_list.append('Chest')
            if body_parts_usage_dict['back_usage_percent'] >= 30:
                body_focus_list.append('Back')
            if body_parts_usage_dict['legs_usage_percent'] >= 30:
                body_focus_list.append('Legs')
            new_df.loc[uid, 'Body focus'] = ', '.join(body_focus_list)

        new_df.loc[uid, 'Arms usage %'] = body_parts_usage_dict['arms_usage_percent']
        new_df.loc[uid, 'Chest usage %'] = body_parts_usage_dict['chest_usage_percent']
        new_df.loc[uid, 'Back usage %'] = body_parts_usage_dict['back_usage_percent']
        new_df.loc[uid, 'Legs usage %'] = body_parts_usage_dict['legs_usage_percent']

        new_df.loc[uid, 'Arms exercises'] = ','.join(body_parts_usage_dict['arms_exercises'])
        new_df.loc[uid, 'Chest exercises'] = ','.join(body_parts_usage_dict['chest_exercises'])
        new_df.loc[uid, 'Back exercises'] = ','.join(body_parts_usage_dict['back_exercises'])
        new_df.loc[uid, 'Legs exercises'] = ','.join(body_parts_usage_dict['legs_exercises'])
    else:
        new_df.loc[uid, 'Body focus'] = '-'
        new_df.loc[uid, 'Arms usage %'] = '-'
        new_df.loc[uid, 'Chest usage %'] = '-'
        new_df.loc[uid, 'Back usage %'] = '-'
        new_df.loc[uid, 'Legs usage %'] = '-'

        new_df.loc[uid, 'Arms exercises'] = '-'
        new_df.loc[uid, 'Chest exercises'] = '-'
        new_df.loc[uid, 'Back exercises'] = '-'
        new_df.loc[uid, 'Legs exercises'] = '-'

new_df.to_csv(res_filepath)