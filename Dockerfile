FROM python:3.10-slim

WORKDIR /app

# System dependencies (ffmpeg စသည်တို့ ထည့်သွင်းရန်)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Python packages များကို requirements.txt မှတစ်ဆင့် Install လုပ်ရန်
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ပရိုဂျက်ဖိုင်များ အားလုံးကို ကူးယူရန်
COPY . .

# Bot ကို စတင် Run ရန်
CMD ["python", "bot.py"]
