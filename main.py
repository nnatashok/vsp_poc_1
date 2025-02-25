import re
from os import makedirs, remove
from os.path import exists, join

import ffmpeg
from dash.dash_table.FormatTemplate import percentage
from pytubefix import YouTube
from pytubefix.cli import on_progress
import pandas as pd

from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task

videos_dir = 'videos'
temp_dir = 'temp'
df_gt = pd.read_csv('exercise videos - Ground truth.csv', index_col='UID')
tw_client = TwelveLabs(api_key='tlk_3D5EH0Z1ME6JYR2S9C1S40XYZPFC')
tw_index_id = '67bd08f347ebd55b1eab9e54'

select_category_prompt = '''
Select the category and subcategory of the video:
Cardio: Walking, Running, HIIT, Indoor biking, Indoor rowing, Treadmill, Elliptical
Flexibility: Yoga, Stretching, Pilates
Strength: Body weight, Weight workout, Calisthenics
'''[1:]

select_complexity_prompt = '''
Set the percentage for each category to describe the video:
Beginner exercises
Intermediate exercises
Advanced exercises
'''[1:]

# for [Strength, Cardio]
body_parts_usage_prompt = '''
Set what percentage of the video each body part is used extensively:
Arms
Legs
Chest
Back
'''[1:]

# for [Flexibility]
flexibility_type_prompt = '''
Select the category of the video:
Range of motion
Balance
'''[1:]

# for [Strength]
strenth_type_prompt = '''
Select the category of the video:
Muscle endurance
Hypertrophy
Functional strength
Maximal strength
'''[1:]

# for [Cardio]
cardio_type_prompt = '''
Select the category of the video:
Heart Rate Zone 1 - super easy effort
Heart Rate Zone 2 - is a bit more complicated, as it should feel pretty easy, at least in the beginning
HIIT - High Intensity Interval Training (30s to 10m reps and rest)
Functional Threshold (or anaerobic threshold training)
'''[1:]

required_equipment_prompt = '''.
Select what equipment from the list is used in the video, if any:
Mat
Dumbbells
Chair
Blocks
Exercise bike
Treadmill
Elliptical
'''[2:]

class NonYoutubeVideoException(Exception):
    pass

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

    category_text_filepath =  join(video_dir, 'category.txt')
    if not exists(category_text_filepath):
        print('Requesting category text')
        category_text = tw_client.generate.text(video_id=tw_video_id, prompt=select_category_prompt).data
        with open(category_text_filepath, 'w') as f:
            f.write(category_text)
    else:
        print('Category text found')
        category_text = open(category_text_filepath, 'r').read()

process_video('41b8e1e9-4a8c-4a4c-a426-35c041a9d8b6')





