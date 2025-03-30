import os
import re
import time
import json
import hashlib
import numpy as np
from openai import OpenAI
from googleapiclient.discovery import build

from vibes import vibes_data
from youtube_links import youtube_links

# --- Configuration ---
YOUTUBE_API_KEY = 'AIzaSyCkpiTfTUvNVNmPcyw8ZO1NOn_0b_LV8RA'
OPENAI_API_KEY = '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'

oai_client = OpenAI(api_key=OPENAI_API_KEY)
youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# --- Video Metadata Cache Setup ---
VIDEO_CACHE_FILE = 'video_metadata_cache.json'


def load_metadata_cache():
    if os.path.exists(VIDEO_CACHE_FILE):
        with open(VIDEO_CACHE_FILE, 'r') as f:
            try:
                return json.load(f)
            except Exception as e:
                print("Error loading video cache:", e)
                return {}
    return {}


def save_metadata_cache(cache):
    with open(VIDEO_CACHE_FILE, 'w') as f:
        json.dump(cache, f)


metadata_cache = load_metadata_cache()

# --- Vibe Cache Setup ---
VIBE_CACHE_FILE = 'vibe_cache.json'


def load_vibe_cache():
    if os.path.exists(VIBE_CACHE_FILE):
        with open(VIBE_CACHE_FILE, 'r') as f:
            try:
                return json.load(f)
            except Exception as e:
                print("Error loading vibe cache:", e)
                return {}
    return {}


def save_vibe_cache(cache):
    with open(VIBE_CACHE_FILE, 'w') as f:
        json.dump(cache, f)


# --- Video Embedding Cache Setup ---
VIDEO_EMBEDDING_CACHE_FILE = 'video_embedding_cache.json'


def load_video_embedding_cache():
    if os.path.exists(VIDEO_EMBEDDING_CACHE_FILE):
        with open(VIDEO_EMBEDDING_CACHE_FILE, 'r') as f:
            try:
                return json.load(f)
            except Exception as e:
                print("Error loading video embedding cache:", e)
                return {}
    return {}


def save_video_embedding_cache(cache):
    with open(VIDEO_EMBEDDING_CACHE_FILE, 'w') as f:
        json.dump(cache, f)


video_embedding_cache = load_video_embedding_cache()


def compute_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()


vibe_cache = load_vibe_cache()


# --- Helper Functions ---
def extract_video_id(url):
    """
    Extracts the YouTube video ID from a URL.
    Supports common formats such as:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
    """
    regex = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(regex, url)
    if match:
        return match.group(1)
    else:
        return None


def get_video_metadata(video_id):
    """
    Retrieves video metadata (title and description) using the YouTube Data API.
    First checks if the metadata exists in the cache.
    """
    if video_id in metadata_cache:
        return metadata_cache[video_id]['title'], metadata_cache[video_id]['description']

    request = youtube_client.videos().list(
        part="snippet",
        id=video_id
    )
    response = request.execute()
    if response["items"]:
        snippet = response["items"][0]["snippet"]
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        metadata_cache[video_id] = {"title": title, "description": description}
        save_metadata_cache(metadata_cache)
        return title, description
    else:
        return None, None


def get_embedding(text, model="text-embedding-ada-002"):
    """
    Gets the embedding vector for a given text using OpenAI's embedding API.
    """
    response = oai_client.embeddings.create(
        input=[text],
        model=model
    )
    embedding = response.data[0].embedding
    return np.array(embedding)


def cosine_similarity(vec1, vec2):
    """
    Computes the cosine similarity between two vectors.
    """
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def softmax(x):
    """
    Computes the softmax probabilities for a numpy array.
    """
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum()


# --- Precompute Vibe Embeddings with Cache ---
vibe_embeddings = {}
print("Processing vibe embeddings...")

for vibe in vibes_data:
    vibe_name = vibe["Workout Vibe"]
    # Improved prompt: explicitly include labels for better context.
    vibe_text = (
        f"Workout Vibe: {vibe['Workout Vibe']}. "
        f"Description: {vibe['Vibe Description']}. "
        f"Example Workouts: {vibe['Example Workouts']}."
    )
    text_hash = compute_hash(vibe_text)
    if vibe_name in vibe_cache and vibe_cache[vibe_name]["hash"] == text_hash:
        # Load cached embedding if the vibe definition hasn't changed.
        embedding = np.array(vibe_cache[vibe_name]["embedding"])
        print(f"Loaded cached embedding for: {vibe_name}")
    else:
        try:
            embedding = get_embedding(vibe_text)
            vibe_cache[vibe_name] = {"hash": text_hash, "embedding": embedding.tolist()}
            print(f"Computed embedding for: {vibe_name}")
            time.sleep(1)  # Sleep only when making an API call
        except Exception as e:
            print(f"Error computing embedding for {vibe_name}: {e}")
    vibe_embeddings[vibe_name] = embedding

save_vibe_cache(vibe_cache)

# --- Process Videos and Classify ---
results = []
print("Processing YouTube videos...")

for link in youtube_links:
    video_id = extract_video_id(link)
    if video_id is None:
        print(f"Could not extract video id from: {link}")
        continue

    title, description = get_video_metadata(video_id)
    if not title:
        print(f"Metadata not found for video: {video_id}")
        continue

    # Improved prompt: clearly label the title and description.
    video_text = f"Video Title: {title}. Video Description: {description}."
    video_hash = compute_hash(video_text)

    # Check if the video embedding is cached.
    if video_id in video_embedding_cache and video_embedding_cache[video_id]["hash"] == video_hash:
        video_embedding = np.array(video_embedding_cache[video_id]["embedding"])
        print(f"Loaded cached embedding for video: {video_id}")
    else:
        try:
            video_embedding = get_embedding(video_text)
            video_embedding_cache[video_id] = {"hash": video_hash, "embedding": video_embedding.tolist()}
            print(f"Computed embedding for video: {video_id}")
            time.sleep(1)  # Sleep after API call for video embedding
        except Exception as e:
            print(f"Error computing embedding for video {video_id}: {e}")
            continue

    # Compute similarities for all vibes
    similarities = []
    for vibe_name, vibe_embedding in vibe_embeddings.items():
        sim = cosine_similarity(video_embedding, vibe_embedding)
        similarities.append(sim)

    similarities = np.array(similarities)
    # Compute probabilities via softmax
    probabilities = softmax(similarities)

    # Pair each vibe with its probability and similarity
    vibe_scores = []
    for idx, vibe_name in enumerate(vibe_embeddings.keys()):
        vibe_scores.append({
            "vibe": vibe_name,
            "similarity": float(similarities[idx]),
            "probability": float(probabilities[idx])
        })

    # Sort by probability descending and take the top 3
    top_vibes = sorted(vibe_scores, key=lambda x: x["probability"], reverse=True)[:20]

    results.append({
        "video_link": link,
        "video_id": video_id,
        "title": title,
        "top_vibes": top_vibes
    })

    print(f"Video {video_id} top vibes:")
    for tv in top_vibes:
        print(f"  {tv['vibe']} | Similarity: {tv['similarity']:.3f} | Probability: {tv['probability']:.3f}")

save_video_embedding_cache(video_embedding_cache)

print("\nClassification Results:")
for result in results:
    print(f"\nVideo: {result['video_id']} | {result['title']}")
    for vibe in result["top_vibes"]:
        print(f"  Vibe: {vibe['vibe']} | Similarity: {vibe['similarity']:.3f} | Probability: {vibe['probability']:.3f}")

print("Classification complete.")
