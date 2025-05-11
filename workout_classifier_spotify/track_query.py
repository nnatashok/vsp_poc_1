# Classification prompt for vibe analysis
TRACK_PROMPT = TRACK_PROMPT = """
You are a specialized AI music analysis assistant. Your task is to analyze a single music track using metadata and contextual snippets gathered from web search (if available). Your goal is to provide a structured musical description that includes the following musical and emotional attributes:

EXPECTED OUTPUT FIELDS:
- genre (e.g., Chillhop, Pop, EDM, Trap, Acoustic Rock)
- track bpm (integer or string if uncertain)
- lyrics summary (12 sentence abstract of lyrical content, or "Instrumental" if no lyrics)
- lyrics sentiment (see label definitions below)
- music energy (Low / Medium / High — see definitions)
- music danceability (Low / Medium / High — see definitions)
- valence (Low / Medium / High — see definitions)
- mode (Major / Minor — see definitions)

DATA SOURCES YOU MAY USE:
- Title and artist of the track
- Year of release
- Lyrics content, if present
- Publicly available reviews, descriptions, or search result snippets
- Musical features inferred from artist style, genre tags, or typical BPM range

FIELD LABEL DEFINITIONS:

lyrics sentiment:
- Positive: Optimistic, joyful, romantic, hopeful, celebratory.
- Neutral: Factual, descriptive, or non-emotional.
- Negative: Sad, angry, regretful, anxious, or emotionally dark.
- Mixed: Contrasting emotional tones (e.g., hopeful but sad, happy-sounding but regretful).

music energy:
- Low: Relaxing, mellow, ambient, minimal instrumentation, soft dynamics.
- Medium: Balanced dynamic range, moderately intense, steady rhythm.
- High: Loud, fast-paced, intense, aggressive instrumentation or fast tempo.

music danceability:
- Low: Hard to dance to; irregular rhythm, slow or ambient.
- Medium: Some groove or beat but not dominant; may suit casual or light dancing.
- High: Strong, consistent beat and rhythm; designed to make people move.

valence:
- Low: Dark, sad, melancholic, tense.
- Medium: Balanced, emotionally complex, subtle mix of moods.
- High: Uplifting, joyful, euphoric, emotionally positive.

mode:
- Major: Bright, happy, triumphant or resolved tonal quality.
- Minor: Dark, moody, introspective, or unresolved tonal quality.

ANALYSIS GUIDELINES:
1. If the lyrics are available, summarize the central theme or emotion in 1–2 sentences.
2. For instrumental tracks, state clearly that there are no lyrics.
3. Estimate the genre based on the artist, song title, and content of the snippet.
4. If no exact BPM is given, estimate based on genre and mood (e.g., Chillhop ~70–90 BPM, EDM ~120–130 BPM).
5. Use your music knowledge to estimate energy, danceability, valence, and mode based on how the track likely sounds or is described.
6. Always choose discrete values: Low / Medium / High or Major / Minor — do not use ranges or vague descriptions.
7. Keep values concise and consistent across all entries.
8. When unsure (due to missing data), make an educated best guess based on artist, genre, and common musical patterns.

RESPONSE FORMAT:
Your final response must be a JSON dictionary with the following keys:
{
  "genre": str,
  "track bpm": int,
  "lyrics summary": str,
  "lyrics sentiment": str,
  "music energy": "Low" | "Medium" | "High",
  "music danceability": "Low" | "Medium" | "High",
  "valence": "Low" | "Medium" | "High",
  "mode": "Major" | "Minor"
}

REQUIREMENTS:
- Do not include any extra text outside the JSON object.
- Always fill in every field — no missing values.
- Use your best judgment even when data is sparse, based on artist/genre cues.
"""



# User prompt for vibe classification
TRACK_USER_PROMPT = "Analyze this audio track metadata and classify it according to the schema:"

# JSON schema for vibe classification
TRACK_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "MusicTrackAnalysis",
        "schema": {
            "type": "object",
            "properties": {
                "genre": {
                    "type": "string",
                    "description": "The primary genre of the music track (e.g., Pop, Lo-fi, EDM, Ambient)."
                },
                "track bpm": {
                    "type": ["string", "integer"],
                    "description": "Estimated beats per minute (BPM) of the track. Can be approximate (e.g., 'about 120')."
                },
                "lyrics summary": {
                    "type": "string",
                    "description": "A short abstract (1–2 sentences) of the lyrical content, or 'Instrumental' if there are no lyrics."
                },
                "lyrics sentiment": {
                    "type": "string",
                    "description": (
                        "Sentiment of the lyrics with justification.\n"
                        "Start with a label (Positive, Neutral, Negative, Mixed), followed by 'because' and an explanation.\n"
                        "Example: 'Positive because the lyrics express joy and romantic devotion.'"
                    )
                },
                "music energy": {
                    "type": "string",
                    "description": (
                        "Energy level of the music with justification.\n"
                        "Start with 'Low', 'Medium', or 'High', followed by 'because' and reasoning.\n"
                        "Example: 'High because the tempo is fast and the instrumentation is intense.'"
                    )
                },
                "music danceability": {
                    "type": "string",
                    "description": (
                        "Danceability of the track with explanation.\n"
                        "Start with 'Low', 'Medium', or 'High', followed by 'because...'.\n"
                        "Example: 'Medium because the beat is steady but not prominent.'"
                    )
                },
                "valence": {
                    "type": "string",
                    "description": (
                        "Valence (emotional positivity) of the track with justification.\n"
                        "Start with 'Low', 'Medium', or 'High', followed by 'because...'.\n"
                        "Example: 'Low because the tone is melancholic and the lyrics express loneliness.'"
                    )
                },
                "mode": {
                    "type": "string",
                    "description": (
                        "Musical mode (Major or Minor) with justification.\n"
                        "Start with the label, then 'because' and explain why.\n"
                        "Example: 'Minor because the melody and chord progression sound dark and unresolved.'"
                    )
                }
            },
            "required": [
                "genre",
                "track bpm",
                "lyrics summary",
                "lyrics sentiment",
                "music energy",
                "music danceability",
                "valence",
                "mode"
            ],
            "additionalProperties": False
        }
    }
}
