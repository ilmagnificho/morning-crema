import re
from typing import Optional

import streamlit as st
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)
import openai

SYSTEM_PROMPT = """
You are Lim Hyun-woo (임현우), a professional journalist from Korea Economic Daily (Hankyung) hosting the morning show "Morning Routine".

**Brand Identity:**
- Start the opening with: "네, 오늘 아침, 뇌를 깨우는 정보의 첫 거품, **모닝 크레마(Morning Crema)** 브리핑 시작하겠습니다."

**Tone & Manner:**
- Professional, trustworthy, yet friendly (News Anchor style).
- Use clean sentence endings (~했습니다, ~입니다) mixed with softer ones (~하거든요, ~로 보입니다).
- Use your signature conjunctions frequently: "**자,** 다음 내용입니다", "**자,** 정리해 보겠습니다".
- Explain complex economic/tech terms simply for the audience.
- Ends with: "이상, 오늘의 가장 신선한 모닝 크레마였습니다."

**Task:**
- Summarize the provided YouTube transcript into a 3-minute read-aloud script.
- Focus on the "Key Insights" (The Crema) rather than just listing facts.
"""


st.set_page_config(page_title="Morning Crema", page_icon="☕")

st.title("☕ Morning Crema")
st.caption("Extracting the essence of news for your morning routine.")

if "script" not in st.session_state:
    st.session_state.script = None
if "audio" not in st.session_state:
    st.session_state.audio = None
if "video_url" not in st.session_state:
    st.session_state.video_url = ""


def extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"v=([\w-]{11})",
        r"youtu\.be/([\w-]{11})",
        r"shorts/([\w-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_transcript(video_id: str) -> str:
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    try:
        transcript = transcript_list.find_transcript(["ko", "en", "en-US", "en-GB"])
    except NoTranscriptFound:
        transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
    parts = transcript.fetch()
    return " ".join(item["text"] for item in parts)


def create_chat_completion(transcript_text: str) -> str:
    user_prompt = (
        "If the transcript is in English, translate and interpret it into Korean. "
        "Summarize and craft the Morning Crema script based on the transcript below:\n\n"
        f"{transcript_text}"
    )
    if hasattr(openai, "ChatCompletion"):
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )
        return response["choices"][0]["message"]["content"]

    client = openai.OpenAI(api_key=openai.api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content


def create_tts_audio(script: str) -> bytes:
    if hasattr(openai, "audio") and hasattr(openai.audio, "speech"):
        audio_response = openai.audio.speech.create(
            model="tts-1-hd",
            voice="onyx",
            speed=1.1,
            input=script,
        )
    else:
        client = openai.OpenAI(api_key=openai.api_key)
        audio_response = client.audio.speech.create(
            model="tts-1-hd",
            voice="onyx",
            speed=1.1,
            input=script,
        )
    if hasattr(audio_response, "read"):
        return audio_response.read()
    if hasattr(audio_response, "content"):
        return audio_response.content
    return audio_response


with st.sidebar:
    st.header("🔐 API Key")
    api_key = st.text_input("OPENAI_API_KEY", type="password")
    st.markdown("Enter your API key to brew your Morning Crema.")

col1, col2 = st.columns([1, 1])
with col1:
    brew = st.button("☕ Brew", type="primary")
with col2:
    reset = st.button("🔄 Re-brew")

if reset:
    st.session_state.script = None
    st.session_state.audio = None
    st.session_state.video_url = ""
    st.rerun()

video_url = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=...",
    key="video_url",
)

if brew:
    if not api_key:
        st.error("OPENAI_API_KEY가 필요합니다. 사이드바에 입력해 주세요.")
    elif not video_url:
        st.error("YouTube URL을 입력해 주세요.")
    else:
        openai.api_key = api_key
        video_id = extract_video_id(video_url)
        if not video_id:
            st.error("유효한 YouTube URL을 입력해 주세요.")
        else:
            try:
                with st.spinner("☕ 원두 가는 중... (Extracting Transcript)"):
                    transcript_text = fetch_transcript(video_id)
                with st.spinner("🥛 크레마 추출 중... (Brewing Script)"):
                    st.session_state.script = create_chat_completion(transcript_text)
                with st.spinner("🎧 서빙 준비 중... (Generating Audio)"):
                    st.session_state.audio = create_tts_audio(st.session_state.script)
            except (VideoUnavailable, TranscriptsDisabled, NoTranscriptFound) as exc:
                st.error(f"자막을 찾을 수 없습니다. 다른 영상으로 시도해 주세요. ({exc})")
            except Exception as exc:  # noqa: BLE001
                st.error(f"문제가 발생했습니다: {exc}")

if st.session_state.script:
    st.subheader("📰 Morning Crema Script")
    st.write(st.session_state.script)

if st.session_state.audio:
    st.subheader("🎧 Audio Briefing")
    st.audio(st.session_state.audio, format="audio/mp3")
