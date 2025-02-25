import json
from enum import StrEnum
from os import makedirs, remove
from os.path import exists, join
from typing import List

import ffmpeg
from pytubefix import YouTube
from pytubefix.cli import on_progress
import pandas as pd

from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task
from pydantic import BaseModel
from openai import OpenAI

videos_dir = 'videos'
temp_dir = 'temp'
df_gt = pd.read_csv('exercise videos - Ground truth.csv', index_col='UID')
tw_client = TwelveLabs(api_key='tlk_3D5EH0Z1ME6JYR2S9C1S40XYZPFC')
tw_index_id = '67bd08f347ebd55b1eab9e54'

oai_client = OpenAI(api_key='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')

select_category_prompt = '''
Select the category and subcategory of the video:
Cardio: Walking, Running, HIIT, Indoor biking, Indoor rowing, Treadmill, Elliptical
Flexibility: Yoga, Stretching, Pilates
Strength: Body weight, Weight workout, Calisthenics
'''[1:]

class WorkoutCategoryEnum(StrEnum):
    Cardio = 'Cardio'
    Felxibility = 'Felxibility'
    Strength = 'Strength'

class WorkoutSubCategoryEnum(StrEnum):
    Walking = 'Walking'
    Running = 'Running'
    HIIT = 'HIIT'
    Indoor_biking = 'Indoor biking'
    Indoor_rowing = 'Indoor rowing'
    Treadmill = 'Treadmill'
    Elliptical = 'Elliptical'
    Yoga = 'Yoga'
    Stretching = 'Stretching'
    Pilates = 'Pilates'
    Body_weight = 'Body weight'
    Weight_workout = 'Weight workout'
    Calisthenics = 'Calisthenics'

class WorkoutCategoryModel(BaseModel):
    category: WorkoutCategoryEnum
    subcategory: WorkoutSubCategoryEnum

set_complexity_prompt_general = '''
Set the percentage for each category to describe the video:
Beginner exercises
Intermediate exercises
Advanced exercises
'''[1:]

set_complexity_prompt_yoga = '''
You are a yogi with excellent flexibility. What percentage of the exercises in the workout in the video would be easy, medium and difficult for you?
'''[1:]

class WorkoutComplexityModel(BaseModel):
    beginner_exercises_percent: int
    intermediate_exercises_percent: int
    advanced_exercises_percent: int
    beginner_exercises: List[str]
    intermediate_exercises: List[str]
    advanced_exercises: List[str]

# for [Strength, Cardio]
set_body_parts_usage_prompt = '''
Set what percentage of the video each body part is used extensively:
Arms
Chest
Back
Legs
'''[1:]

class BodyPartsUsageModel(BaseModel):
    arms_usage_percent: int
    chest_usage_percent: int
    back_usage_percent: int
    legs_usage_percent: int
    arms_exercises: List[str]
    chest_exercises: List[str]
    back_exercises: List[str]
    legs_exercises: List[str]

# for [Flexibility]
select_flexibility_type_prompt = '''
Select the category of the video:
Range of motion
Balance
'''[1:]

class FlexibilityTypeEnum(StrEnum):
    Range_of_motion = 'Range of motion'
    Balance = 'Balance'

class FlexibilityTypeModel(BaseModel):
    type: FlexibilityTypeEnum

# for [Strength]
select_strength_type_prompt = '''
Select the category of the video:
Muscle endurance
Hypertrophy
Functional strength
Maximal strength
'''[1:]

class StrengthTypeEnum(StrEnum):
    Muscle_endurance = 'Muscle endurance'
    Hypertrophy = 'Hypertrophy'
    Functional_strength = 'Functional strength'
    Maximal_strength = 'Maximal strength'

class StrengthTypeModel(BaseModel):
    type: StrengthTypeEnum

# for [Cardio]
select_cardio_type_prompt = '''
Select the category of the video:
Heart Rate Zone 1 - super easy effort
Heart Rate Zone 2 - is a bit more complicated, as it should feel pretty easy, at least in the beginning
HIIT - High Intensity Interval Training (30s to 10m reps and rest)
Functional Threshold (or anaerobic threshold training)
'''[1:]

class CardioTypeEnum(StrEnum):
    Heart_Rate_Zone_1 = 'Heart Rate Zone 1'
    Heart_Rate_Zone_2 = 'Heart Rate Zone 2'
    HIIT = 'HIIT'
    Functional_Threshold = 'Functional Threshold'

class CardioTypeModel(BaseModel):
    type: CardioTypeEnum

select_equipment_needed_prompt = '''.
Select what equipment from the list is used in the video, if any:
Mat
Dumbbells
Chair
Blocks
Exercise bike
Rowing machine
Treadmill
Elliptical
'''[2:]

class EquipmentTypeEnum(StrEnum):
    Mat = 'Mat'
    Dumbbells = 'Dumbbells'
    Chair = 'Chair'
    Blocks = 'Blocks'
    Exercise_bike = 'Exercise bike'
    Rowing_machine = 'Rowing machine'
    Treadmill = 'Treadmill'
    Elliptical = 'Elliptical'

class EquipmentNeededModel(BaseModel):
    equipment: List[EquipmentTypeEnum]

chatgpt_prompt = 'Extract workout information.'

class NonYoutubeVideoException(Exception):
    pass

prompt_completion_separator = '\n#######################################################\n\n'
def read_completion(filepath):
    return open(filepath).read().split(prompt_completion_separator)[1]

def write_prompt_and_completion(filepath, prompt, competition):
    assert not exists(filepath)
    with open(filepath, 'w') as f:
        f.write(f'{prompt}{prompt_completion_separator}{competition}')

def process_video(uid):
    video_name = df_gt.loc[uid, 'Name']
    print(f'Processing video {video_name} {uid}')

    video_link = df_gt.loc[uid, 'Link to Workout Media']
    if 'youtu' not in video_link:
        return NonYoutubeVideoException

    video_dir = join(videos_dir, uid)
    makedirs(video_dir, exist_ok=True)

    video_path = join(video_dir, f'{uid}.mp4')
    if not exists(video_path):
        print(f'Downloading {video_path}')
        url = video_link
        yt = YouTube(url, on_progress_callback=on_progress)
        video_track_path = yt.streams.filter(file_extension='mp4', resolution='720p').first().download(output_path=temp_dir)
        audio_track_path = yt.streams.filter(only_audio=True).first().download(output_path=temp_dir)
        video_stream = ffmpeg.input(video_track_path)
        audio_stream = ffmpeg.input(audio_track_path)
        ffmpeg.output(audio_stream, video_stream, video_path).run()
        remove(video_track_path)
        remove(audio_track_path)
        print(f'Video downloaded')
    else:
        print(f'{video_path} already exists')

    tw_video_id_filepath = join(video_dir, 'id.txt')
    if not exists(tw_video_id_filepath):
        print('Uploading video to index')
        task = tw_client.task.create(
             index_id=tw_index_id,
             file=video_path
        )

        # noinspection PyShadowingNames
        def on_task_update(task: Task):
            print(f"  Status={task.status}")
        task.wait_for_done(sleep_interval=5, callback=on_task_update)
        if task.status != "ready":
            raise RuntimeError(f"Indexing failed with status {task.status}")
        tw_video_id = task.video_id
        print(f'Twelvelabs video id is {task.video_id}.')


        tw_client.index.video.update(
            index_id=tw_index_id,
            id = tw_video_id,
        )

        with open(tw_video_id_filepath, 'w') as f:
            f.write(tw_video_id)
    else:
        tw_video_id = open(tw_video_id_filepath, 'r').read()
        print(f'Twelvelabs video id found {tw_video_id}')

    category_txt_filepath =  join(video_dir, 'category.txt')
    if not exists(category_txt_filepath):
        print('Requesting category text')
        category_completion = tw_client.generate.text(video_id=tw_video_id, prompt=select_category_prompt).data
        print('Category text received')
        write_prompt_and_completion(category_txt_filepath, select_category_prompt, category_completion)
    else:
        print('Category text found')
        category_completion = read_completion(category_txt_filepath)

    category_json_filepath = join(video_dir, 'category.json')
    if not exists(category_json_filepath):
        print('Requesting category json')
        completion = oai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": chatgpt_prompt},
                {"role": "user", "content": category_completion},
            ],
            response_format=WorkoutCategoryModel,
        )
        if completion.choices[0].message.refusal:
            raise Exception('ChatGPT refusal')
        category_dict = completion.choices[0].message.parsed.model_dump(mode='json')
        print(f'Category json received {category_dict}')
        with open(category_json_filepath, 'w') as f:
            # noinspection PyTypeChecker
            json.dump(category_dict, f, indent=2)
    else:
        category_dict = json.load(open(category_json_filepath, 'r'))
        print(f'Category json found {category_dict}')

    complexity_txt_filepath =  join(video_dir, 'complexity.txt')
    set_complexity_prompt = set_complexity_prompt_yoga if category_dict['subcategory'] == 'Yoga' else set_complexity_prompt_general
    if not exists(complexity_txt_filepath):
        print('Requesting complexity text')
        complexity_completion = tw_client.generate.text(video_id=tw_video_id, prompt=set_complexity_prompt).data
        print('Complexity text received')
        write_prompt_and_completion(complexity_txt_filepath, set_complexity_prompt, complexity_completion)
    else:
        print('Complexity text found')
        complexity_completion = open(complexity_txt_filepath, 'r').read()
        
    complexity_json_filepath = join(video_dir, 'complexity.json')
    if not exists(complexity_json_filepath):
        print('Requesting complexity json')
        completion = oai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": chatgpt_prompt},
                {"role": "user", "content": complexity_completion},
            ],
            response_format=WorkoutComplexityModel,
        )
        if completion.choices[0].message.refusal:
            raise Exception('ChatGPT refusal')
        complexity_dict = completion.choices[0].message.parsed.model_dump(mode='json')
        print(f'Complexity json received {complexity_dict}')
        with open(complexity_json_filepath, 'w') as f:
            # noinspection PyTypeChecker
            json.dump(complexity_dict, f, indent=2)
    else:
        complexity_dict = json.load(open(complexity_json_filepath, 'r'))
        print(f'Complexity json found {complexity_dict}')

    if category_dict['category'] == 'Felxibility':
        flexibility_type_txt_filepath = join(video_dir, 'flexibility_type.txt')
        if not exists(flexibility_type_txt_filepath):
            print('Requesting flexibility type text')
            flexibility_type_completion = tw_client.generate.text(video_id=tw_video_id, prompt=select_flexibility_type_prompt).data
            print('Flexibility type text received')
            write_prompt_and_completion(flexibility_type_txt_filepath, select_flexibility_type_prompt, flexibility_type_completion)
        else:
            print('Flexibility type text found')
            flexibility_type_completion = open(flexibility_type_txt_filepath, 'r').read()

        flexibility_type_json_filepath = join(video_dir, 'flexibility_type.json')
        if not exists(flexibility_type_json_filepath):
            print('Requesting flexibility_type json')
            completion = oai_client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": chatgpt_prompt},
                    {"role": "user", "content": flexibility_type_completion},
                ],
                response_format=FlexibilityTypeModel,
            )
            if completion.choices[0].message.refusal:
                raise Exception('ChatGPT refusal')
            flexibility_type_dict = completion.choices[0].message.parsed.model_dump(mode='json')
            print(f'Flexibility type json received {flexibility_type_dict}')
            with open(flexibility_type_json_filepath, 'w') as f:
                # noinspection PyTypeChecker
                json.dump(flexibility_type_dict, f, indent=2)
        else:
            flexibility_type_dict = json.load(open(flexibility_type_json_filepath, 'r'))
            print(f'Flexibility type json found {flexibility_type_dict}')

    equipment_needed_txt_filepath = join(video_dir, 'equipment_needed.txt')
    if not exists(equipment_needed_txt_filepath):
        print('Requesting equipment needed text')
        equipment_needed_completion = tw_client.generate.text(video_id=tw_video_id,
                                                              prompt=select_equipment_needed_prompt).data
        print('Equipment needed text received')
        write_prompt_and_completion(equipment_needed_txt_filepath, select_equipment_needed_prompt,
                                    equipment_needed_completion)
    else:
        print('Equipment needed text found')
        equipment_needed_completion = open(equipment_needed_txt_filepath, 'r').read()

    equipment_needed_json_filepath = join(video_dir, 'equipment_needed.json')
    if not exists(equipment_needed_json_filepath):
        print('Requesting equipment needed json')
        completion = oai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": chatgpt_prompt},
                {"role": "user", "content": equipment_needed_completion},
            ],
            response_format=EquipmentNeededModel,
        )
        if completion.choices[0].message.refusal:
            raise Exception('ChatGPT refusal')
        equipment_needed_dict = completion.choices[0].message.parsed.model_dump(mode='json')
        print(f'Equipment needed json received {equipment_needed_dict}')
        with open(equipment_needed_json_filepath, 'w') as f:
            # noinspection PyTypeChecker
            json.dump(equipment_needed_dict, f, indent=2)
    else:
        equipment_needed_dict = json.load(open(equipment_needed_json_filepath, 'r'))
        print(f'Equipment needed json found {equipment_needed_dict}')


process_video('41b8e1e9-4a8c-4a4c-a426-35c041a9d8b6')





