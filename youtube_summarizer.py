"""
YouTube Transcript Summarizer
Fetches the latest 5 videos from @bencord, generates a summary and a
LinkedIn post for each using Claude AI, and sends an email digest.
"""

import os
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import requests
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
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

CHANNEL_HANDLE = "@bencord"
MAX_VIDEOS = 5
EMAIL_FROM = "santicelemink@gmail.com"
EMAIL_TO = "santicelemin@outlook.com"
YT_API_BASE = "https://www.googleapis.com/youtube/v3"

TRANSCRIPT_WORD_LIMIT = 8000


# ---------------------------------------------------------------------------
# YouTube helpers
# ---------------------------------------------------------------------------

def get_channel_id(handle: str) -> str:
    """Resolve a channel @handle to its channel ID."""
    resp = requests.get(
        f"{YT_API_BASE}/channels",
        params={"part": "id", "forHandle": handle.lstrip("@"), "key": YOUTUBE_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise ValueError(f"Canal no encontrado para el handle: {handle}")
    return items[0]["id"]


def get_latest_videos(channel_id: str, max_results: int = 5) -> list[dict]:
    """Return the latest *max_results* videos for *channel_id*."""
    resp = requests.get(
        f"{YT_API_BASE}/search",
        params={
            "part": "id,snippet",
            "channelId": channel_id,
            "order": "date",
            "type": "video",
            "maxResults": max_results,
            "key": YOUTUBE_API_KEY,
        },
        timeout=15,
    )
    resp.raise_for_status()

    videos = []
    for item in resp.json().get("items", []):
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

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "youtube_cookies.txt")


def fetch_transcript(video_id: str) -> str | None:
    """Download the transcript for *video_id*. Returns plain text or None."""
    cookies_path = COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
    api = YouTubeTranscriptApi(cookie_path=cookies_path)
    try:
        fetched = api.fetch(video_id, languages=["es", "es-419", "es-ES", "en"])
        return " ".join(entry.text for entry in fetched)
    except (TranscriptsDisabled, NoTranscriptFound):
        pass
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] Error al obtener transcripcion de {video_id}: {exc}")
        return None

    # Fallback: grab any available transcript (auto-generated)
    try:
        transcript_list = api.list(video_id)
        transcript = next(iter(transcript_list))
        fetched = transcript.fetch()
        return " ".join(entry.text for entry in fetched)
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] No se pudo obtener la transcripcion de {video_id}: {exc}")
        return None


# ---------------------------------------------------------------------------
# AI generation with Claude
# ---------------------------------------------------------------------------

def generate_linkedin_content(title: str, url: str, transcript: str) -> dict:
    """Use Claude to generate a summary and a LinkedIn post from the transcript."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    words = transcript.split()
    if len(words) > TRANSCRIPT_WORD_LIMIT:
        transcript = " ".join(words[:TRANSCRIPT_WORD_LIMIT])

    prompt = f"""Tenés la transcripción de un video de YouTube titulado: "{title}"
URL: {url}

TRANSCRIPCIÓN:
{transcript}

Tu tarea es generar DOS cosas:

1. RESUMEN: Un resumen claro y conciso (3-5 oraciones) de los puntos principales del video. En español.

2. POST DE LINKEDIN: Un texto atractivo y profesional para publicar en LinkedIn sobre este video. Debe:
   - Tener un gancho inicial que capture la atención
   - Resumir el valor o aprendizaje principal del video
   - Incluir 3-5 puntos clave como bullet points (usando →)
   - Terminar con una llamada a la acción o reflexión
   - Incluir hashtags relevantes al final (5-7 hashtags)
   - Tener un tono cercano, en primera persona como si fuera el creador del contenido
   - Estar en español
   - Tener entre 150-250 palabras

Respondé EXACTAMENTE en este formato:
RESUMEN:
[tu resumen aquí]

POST LINKEDIN:
[tu post aquí]"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text

    summary = ""
    linkedin_post = ""

    if "RESUMEN:" in response_text and "POST LINKEDIN:" in response_text:
        parts = response_text.split("POST LINKEDIN:")
        summary = parts[0].replace("RESUMEN:", "").strip()
        linkedin_post = parts[1].strip()
    else:
        summary = response_text
        linkedin_post = "(No se pudo generar el post de LinkedIn.)"

    return {"summary": summary, "linkedin_post": linkedin_post}


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def build_email_body(summaries: list[dict]) -> str:
    lines = [
        "Hola Santi,",
        "",
        f"Aqui van los resumenes y posts de LinkedIn de los ultimos {len(summaries)} videos del canal {CHANNEL_HANDLE}:",
        "",
    ]
    for i, item in enumerate(summaries, start=1):
        lines.append(f"{i}. {item['title']}")
        lines.append(f"   {item['url']}")
        lines.append(f"   Publicado: {item['published_at'][:10]}")
        lines.append("")

        lines.append("RESUMEN:")
        wrapped_summary = textwrap.fill(
            item["summary"], width=80, initial_indent="   ", subsequent_indent="   "
        )
        lines.append(wrapped_summary)
        lines.append("")

        lines.append("POST PARA LINKEDIN:")
        lines.append("-" * 40)
        for line in item["linkedin_post"].splitlines():
            lines.append(f"   {line}")
        lines.append("-" * 40)

        lines.append("")
        lines.append("=" * 80)
        lines.append("")

    lines.append("Saludos,")
    lines.append("YouTube Summarizer Bot")
    return "\n".join(lines)


def send_email(subject: str, body: str) -> None:
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

    print(f"Buscando canal {CHANNEL_HANDLE}...")
    channel_id = get_channel_id(CHANNEL_HANDLE)
    print(f"  Channel ID: {channel_id}")

    print(f"Obteniendo los ultimos {MAX_VIDEOS} videos...")
    videos = get_latest_videos(channel_id, max_results=MAX_VIDEOS)
    print(f"  {len(videos)} videos encontrados.")

    summaries = []
    for video in videos:
        vid_id = video["video_id"]
        print(f"\nProcesando: {video['title']} ({vid_id})")

        transcript = fetch_transcript(vid_id)
        if transcript:
            print(f"  Transcripcion obtenida ({len(transcript.split())} palabras). Generando contenido con Claude...")
            content = generate_linkedin_content(video["title"], video["url"], transcript)
            summary = content["summary"]
            linkedin_post = content["linkedin_post"]
        else:
            summary = "(Transcripcion no disponible para este video.)"
            linkedin_post = "(Sin transcripcion, no se puede generar post.)"
            print("  Sin transcripcion.")

        summaries.append({**video, "summary": summary, "linkedin_post": linkedin_post})

    print("\nEnviando email...")
    subject = f"Resumenes + Posts LinkedIn de {CHANNEL_HANDLE}: ultimos {len(summaries)} videos"
    body = build_email_body(summaries)
    send_email(subject, body)

    print("Listo!")


if __name__ == "__main__":
    main()
