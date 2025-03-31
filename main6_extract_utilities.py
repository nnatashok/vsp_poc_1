from urllib.parse import parse_qs, urlparse


def extract_video_id(youtube_url):
    """Extract YouTube video ID from URL."""
    if not youtube_url:
        return None
    try:
        if "youtube.com/watch" in youtube_url:
            return parse_qs(urlparse(youtube_url).query).get("v", [None])[0]
        elif "youtu.be/" in youtube_url:
            return urlparse(youtube_url).path[1:]
        elif "youtube.com/embed/" in youtube_url:
            return urlparse(youtube_url).path.split('/embed/')[1].split('?')[0]
        elif "youtube.com/shorts/" in youtube_url:
            return urlparse(youtube_url).path.split('/shorts/')[1].split('?')[0]
        elif "youtube.com/v/" in youtube_url:
            return urlparse(youtube_url).path.split('/v/')[1].split('?')[0]
        elif 'googleusercontent.com/youtube.com/' in youtube_url:
            parts = youtube_url.split('/')
            potential_id = parts[-1].split('?')[0]
            if len(potential_id) >= 11 and all(c.isalnum() or c in ['_', '-'] for c in potential_id):
                print(f"Extracted from googleusercontent: {potential_id}")
                return potential_id
            return parse_qs(urlparse(youtube_url).query).get("v", [None])[0]
    except Exception as e:
        print(f"URL parse error: {e}")
    return None
