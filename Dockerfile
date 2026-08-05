FROM python:3.10-slim

WORKDIR /app

# System dependencies (ffmpeg ထည့်သွင်းရန်)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# လိုအပ်သော Python Library အားလုံးကို တိုက်ရိုက် Install လုပ်ရန်
RUN pip install --no-cache-dir edge-tts yt-dlp openai-whisper groq python-telegram-bot Pillow

# ပရိုဂျက်ဖိုင်များ အားလုံးကို ကူးယူရန်
COPY . .

# Bot ကို စတင် Run ရန်
CMD ["python", "bot.py"]
