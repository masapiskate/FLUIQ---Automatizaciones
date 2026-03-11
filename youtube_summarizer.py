"""
YouTube Transcript Summarizer
Fetches the latest 5 videos from @bencord, summarizes transcripts,
and sends an email digest to santicelemin@outlook.com.
"""

import os
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import googleapiclient.discovery
from dotenv import load_dotenv
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

load_dotenv()

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

CHANNEL_HANDLE = "@bencord"
MAX_VIDEOS = 5
EMAIL_FROM = "santicelemink@gmail.com"
EMAIL_TO = "santicelemin@outlook.com"

# Approx word budget per line when wrapping the transcript for summarisation
TRANSCRIPT_WORD_LIMIT = 1500


# ---------------------------------------------------------------------------
# YouTube helpers
# ---------------------------------------------------------------------------

def get_channel_id(youtube, handle: str) -> str:
    """Resolve a channel @handle to its channel ID."""
    # The forHandle param is the most direct way (v3 API)
    resp = youtube.channels().list(
        part="id",
        forHandle=handle.lstrip("@"),
    ).execute()

    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Channel not found for handle: {handle}")
    return items[0]["id"]


def get_latest_videos(youtube, channel_id: str, max_results: int = 5) -> list[dict]:
    """Return the latest *max_results* videos for *channel_id*."""
    resp = youtube.search().list(
        part="id,snippet",
        channelId=channel_id,
        order="date",
        type="video",
        maxResults=max_results,
    ).execute()

    videos = []
    for item in resp.get("items", []):
        videos.append(
            {
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            }
        )
    return videos


# ---------------------------------------------------------------------------
# Transcript helpers
# ---------------------------------------------------------------------------

def fetch_transcript(video_id: str) -> str | None:
    """Download the transcript for *video_id*. Returns plain text or None."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["en", "es"]
        )
        return " ".join(entry["text"] for entry in transcript_list)
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] Could not fetch transcript for {video_id}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Summarisation (extractive, no external AI API required)
# ---------------------------------------------------------------------------

def _score_sentences(sentences: list[str], word_freq: dict[str, int]) -> list[tuple[int, float, str]]:
    """Score each sentence by the sum of its word frequencies."""
    scored = []
    for idx, sentence in enumerate(sentences):
        words = sentence.lower().split()
        score = sum(word_freq.get(w, 0) for w in words) / max(len(words), 1)
        scored.append((idx, score, sentence))
    return scored


def summarize_transcript(text: str, num_sentences: int = 6) -> str:
    """
    Produce an extractive summary of *text* using TF-style sentence scoring.
    Returns up to *num_sentences* sentences ordered as they appear in the source.
    """
    # Trim very long transcripts to avoid slow processing
    words = text.split()
    if len(words) > TRANSCRIPT_WORD_LIMIT:
        text = " ".join(words[:TRANSCRIPT_WORD_LIMIT])

    # Split into sentences (naive but good enough for transcripts)
    import re
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 4]

    if not sentences:
        return "(No usable transcript content.)"

    if len(sentences) <= num_sentences:
        return " ".join(sentences)

    # Build word frequency table (ignore very short words)
    word_freq: dict[str, int] = {}
    for sentence in sentences:
        for word in sentence.lower().split():
            word = re.sub(r"[^a-z0-9]", "", word)
            if len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1

    scored = _score_sentences(sentences, word_freq)
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:num_sentences]
    # Restore original order
    top_ordered = sorted(top, key=lambda x: x[0])
    return " ".join(s for _, _, s in top_ordered)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def build_email_body(summaries: list[dict]) -> str:
    """Compose the plain-text email body from the list of video summaries."""
    lines = [
        "Hola Santi,",
        "",
        f"Aqui van los resumenes de los ultimos {len(summaries)} videos del canal {CHANNEL_HANDLE}:",
        "",
    ]
    for i, item in enumerate(summaries, start=1):
        lines.append(f"{i}. {item['title']}")
        lines.append(f"   {item['url']}")
        lines.append(f"   Publicado: {item['published_at'][:10]}")
        lines.append("")
        # Wrap summary text at 80 chars for readability
        wrapped = textwrap.fill(item["summary"], width=80, initial_indent="   ", subsequent_indent="   ")
        lines.append(wrapped)
        lines.append("")
        lines.append("-" * 80)
        lines.append("")
    lines.append("Saludos,")
    lines.append("YouTube Summarizer Bot")
    return "\n".join(lines)


def send_email(subject: str, body: str) -> None:
    """Send an email via Gmail SMTP using an App Password."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())

    print(f"Email enviado a {EMAIL_TO}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Iniciando YouTube Transcript Summarizer...")

    # Build YouTube API client
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", developerKey=YOUTUBE_API_KEY
    )

    # Resolve channel handle -> ID
    print(f"Buscando canal {CHANNEL_HANDLE}...")
    channel_id = get_channel_id(youtube, CHANNEL_HANDLE)
    print(f"  Channel ID: {channel_id}")

    # Fetch latest videos
    print(f"Obteniendo los ultimos {MAX_VIDEOS} videos...")
    videos = get_latest_videos(youtube, channel_id, max_results=MAX_VIDEOS)
    print(f"  {len(videos)} videos encontrados.")

    summaries = []
    for video in videos:
        vid_id = video["video_id"]
        print(f"\nProcesando: {video['title']} ({vid_id})")

        transcript = fetch_transcript(vid_id)
        if transcript:
            print(f"  Transcripcion obtenida ({len(transcript.split())} palabras). Resumiendo...")
            summary = summarize_transcript(transcript)
        else:
            summary = "(Transcripcion no disponible para este video.)"
            print("  Sin transcripcion.")

        summaries.append({**video, "summary": summary})

    # Build and send email
    print("\nEnviando email...")
    subject = f"Resumenes de {CHANNEL_HANDLE}: ultimos {len(summaries)} videos"
    body = build_email_body(summaries)
    send_email(subject, body)

    print("Listo!")


if __name__ == "__main__":
    main()
