FROM python:3.10-slim

# FFmpeg နှင့် အခြေခံ System Packages များ Install လုပ်ခြင်း
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency ဖိုင်များ ကူးယူခြင်း
COPY . /app

# Python Libraries များ Install လုပ်ခြင်း
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir \
    python-telegram-bot \
    yt-dlp \
    openai-whisper \
    google-genai \
    google-cloud-texttospeech \
    google-auth

# Bot ကို စတင် Run ခြင်း
CMD ["python", "bot.py"]
