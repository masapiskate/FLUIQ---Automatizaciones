"""
YouTube Transcript Summarizer
Fetches new videos from @bencord, generates a summary and a LinkedIn post
for each using Claude AI, and sends an email digest.

Triggers:
  - When 10 or more new videos have accumulated since the last run.
  - Every Friday (run this script via cron at 12:00 every day; it decides
    whether to fire based on the day and state).
"""

import json
import os
import smtplib
import textwrap
from datetime import date
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
# Fetch enough recent videos to detect accumulation
FETCH_LIMIT = 50
# Trigger threshold: fire when this many new videos have accumulated
ACCUMULATION_THRESHOLD = 10

EMAIL_FROM = "santicelemink@gmail.com"
EMAIL_TO = "santicelemin@outlook.com"
YT_API_BASE = "https://www.googleapis.com/youtube/v3"
TRANSCRIPT_WORD_LIMIT = 8000

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_video_ids": [], "last_friday_run": ""}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Trigger logic
# ---------------------------------------------------------------------------

def should_trigger(new_videos: list[dict], state: dict) -> bool:
    """Return True if the script should process videos now."""
    today = date.today()
    is_friday = today.weekday() == 4  # 0=Monday … 4=Friday
    already_ran_this_friday = state.get("last_friday_run") == str(today)

    if len(new_videos) >= ACCUMULATION_THRESHOLD:
        print(f"  Disparo: {len(new_videos)} videos nuevos acumulados (umbral: {ACCUMULATION_THRESHOLD}).")
        return True

    if is_friday and not already_ran_this_friday:
        print("  Disparo: es viernes y aún no se ejecutó hoy.")
        return True

    print(
        f"  Sin disparo: {len(new_videos)} videos nuevos "
        f"(umbral {ACCUMULATION_THRESHOLD}) y "
        f"{'ya se ejecutó este viernes' if is_friday else 'no es viernes'}."
    )
    return False


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


def get_latest_videos(channel_id: str, max_results: int = FETCH_LIMIT) -> list[dict]:
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

2. POST DE LINKEDIN: Un texto atractivo y profesional para publicar en LinkedIn sobre este video.
   El post debe seguir EXACTAMENTE esta estructura:

   TÍTULO
   (Una línea impactante y directa que resuma el tema principal. Sin hashtags aquí.)

   SUBTÍTULO (PREGUNTA)
   (Una pregunta que genere curiosidad o interpele al lector sobre el tema.)

   DESARROLLO
   (Explicación completa del tema: contexto, puntos clave con bullet points usando →,
   aprendizajes y una reflexión o llamada a la acción final.
   Incluir 5-7 hashtags relevantes al final del desarrollo.)

   Requisitos del post:
   - Tono cercano, en primera persona como si fuera el creador del contenido
   - En español
   - Entre 200-300 palabras en total

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
        f"Aqui van los resumenes y posts de LinkedIn de {len(summaries)} videos nuevos del canal {CHANNEL_HANDLE}:",
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

    state = load_state()
    processed_ids: set = set(state.get("processed_video_ids", []))

    print(f"Buscando canal {CHANNEL_HANDLE}...")
    channel_id = get_channel_id(CHANNEL_HANDLE)
    print(f"  Channel ID: {channel_id}")

    print(f"Obteniendo los ultimos {FETCH_LIMIT} videos...")
    all_videos = get_latest_videos(channel_id, max_results=FETCH_LIMIT)
    new_videos = [v for v in all_videos if v["video_id"] not in processed_ids]
    print(f"  {len(all_videos)} videos totales, {len(new_videos)} nuevos.")

    if not should_trigger(new_videos, state):
        print("Nada que procesar por ahora. Saliendo.")
        return

    summaries = []
    for video in new_videos:
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

    if summaries:
        print("\nEnviando email...")
        subject = f"Resumenes + Posts LinkedIn de {CHANNEL_HANDLE}: {len(summaries)} videos nuevos"
        body = build_email_body(summaries)
        send_email(subject, body)

    # Update state: mark all new videos as processed
    state["processed_video_ids"] = list(processed_ids | {v["video_id"] for v in new_videos})
    today = date.today()
    if today.weekday() == 4:
        state["last_friday_run"] = str(today)
    save_state(state)

    print("Listo!")


if __name__ == "__main__":
    main()
