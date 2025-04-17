from os import makedirs
from os.path import exists, join
import pandas as pd
from openai import OpenAI
from googleapiclient.discovery import build

videos_dir = 'videos'
temp_dir = 'temp'
df_gt = pd.read_csv('exercise videos - Ground truth.csv', index_col='UID')
oai_client = OpenAI(
    api_key='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')

from googleapiclient.discovery import build
youtube_client = build('youtube', 'v3', developerKey='AIzaSyCkpiTfTUvNVNmPcyw8ZO1NOn_0b_LV8RA')


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

    video_dir = join(videos_dir, uid)
    video_url = df_gt.loc[uid, 'Link to Workout Media']
    video_youtube_id = video_url.split('=')[1]
    makedirs(video_dir, exist_ok=True)

    # Fetch video metadata
    response = youtube_client.videos().list(
        part='snippet,statistics',
        id=video_youtube_id
    ).execute()

    response = youtube_client.videos().list(
        part='snippet,statistics,contentDetails',
        id=video_youtube_id
    ).execute()

    if response['items']:
        video = response['items'][0]
        snippet = video.get('snippet', {})
        stats = video.get('statistics', {})
        content = video.get('contentDetails', {})

        metadata = {
            'Title': snippet.get('title'),
            'Channel': snippet.get('channelTitle'),
            'Published At': snippet.get('publishedAt'),
            'Description': snippet.get('description'),
            'Tags': snippet.get('tags'),  # List[str]
            'Category ID': snippet.get('categoryId'),
            'Views': stats.get('viewCount'),
            'Likes': stats.get('likeCount'),
            'Comments': stats.get('commentCount'),
            'Duration': content.get('duration'),  # ISO 8601 format (e.g., "PT3M32S")
            'Dimension': content.get('dimension'),  # "2d" or "3d"
            'Definition': content.get('definition'),  # "hd" or "sd"
            'Caption': content.get('caption'),  # "true" or "false"
            'Licensed Content': content.get('licensedContent'),  # bool
        }

        for key, value in metadata.items():
            print(f"{key}: {value}")
    else:
        print("Video not found or API quota exceeded.")



process_video('41b8e1e9-4a8c-4a4c-a426-35c041a9d8b6')
# process_video('8bfcb76e-16f4-414b-8bec-dbe17e8a0539')
# process_video('f896f107-5bad-46cb-9c4c-0af79250fa02')
# process_video('4d717147-5d9b-40fb-bcea-dcee21e41a11')
# process_video('88a60aa1-088b-4c57-b5ca-796a3b9735fd')
# process_video('20d040f9-4b8a-4e5e-be8a-4e1ee4a95964')





