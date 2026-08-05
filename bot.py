import os
import re
import asyncio
import subprocess
import edge_tts
import yt_dlp
import whisper
from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==========================================
# 🔑 API Keys & Tokens
# ==========================================
TELEGRAM_BOT_TOKEN = "8479798480:AAGxyNW1l5zq2ucjzRSVfwdOlx5eHU3oMB4"
GROQ_API_KEY = "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"

# ==========================================
# ⚙️ Initial Setup
# ==========================================
print("Loading Whisper Model... (Please wait)")
groq_client = Groq(api_key=GROQ_API_KEY)

# dummy logo ဖန်တီးရန် (logo.png မရှိပါက Error မတက်စေရန်)
if not os.path.exists("logo.png"):
    from PIL import Image
    img = Image.new('RGBA', (210, 210), (255, 0, 0, 0))
    img.save('logo.png')

# ==========================================
# ⏱️ Audio Duration Helper (အသံကြာချိန် အတိအကျ တွက်ရန်)
# ==========================================
def get_file_duration(file_path):
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprintwrappers=1:nokey=1', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 30.0

# ==========================================
# 📝 Helper Function: SRT စာတန်းထိုး ဖန်တီးခြင်း
# ==========================================
def generate_srt(text, total_duration, filename="subtitle.srt", max_chars=11):
    raw_tokens = re.split(r'([။၊\n, ])', text)
    sub_phrases = []
    current = ""
    
    for token in raw_tokens:
        current += token
        if len(current) >= max_chars or token in ['။', '၊', '\n']:
            cleaned = current.strip()
            if cleaned:
                sub_phrases.append(cleaned)
            current = ""
            
    if current.strip():
        sub_phrases.append(current.strip())

    if not sub_phrases:
        sub_phrases = [text]

    total_chars = sum(len(p) for p in sub_phrases)
    if total_chars == 0:
        total_chars = 1

    def format_time(seconds):
        millis = int((seconds % 1) * 1000)
        seconds = int(seconds)
        minutes = seconds // 60
        hours = minutes // 60
        minutes %= 60
        seconds %= 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    with open(filename, "w", encoding="utf-8") as f:
        current_time = 0.0
        for i, phrase in enumerate(sub_phrases):
            duration = (len(phrase) / total_chars) * total_duration
            start_t = format_time(current_time)
            end_t = format_time(current_time + duration)
            f.write(f"{i+1}\n{start_t} --> {end_t}\n{phrase}\n\n")
            current_time += duration

# ==========================================
# 🤖 Bot Handlers
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ။ Video Link (သို့) Video ဖိုင်ကို ပေးပို့ပြီး မြန်မာအသံထွက် ဗီဒီယိုအဖြစ် ပြောင်းလဲနိုင်ပါတယ်။")

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    msg_id = update.message.message_id
    input_vid = f"input_video_{user_id}_{msg_id}.mp4"
    output_vid = f"output_video_{user_id}_{msg_id}.mp4"
    audio_file = f"new_audio_{user_id}_{msg_id}.mp3"
    thumbnail_file = f"thumbnail_{user_id}_{msg_id}.jpg"
    srt_file = f"subtitle_{user_id}_{msg_id}.srt"

    status_msg = await update.message.reply_text("⏳ လုပ်ငန်းစဉ် စတင်နေပါပြီ...")

    try:
        # [1/5] Link သို့မဟုတ် Upload တင်သည့် Video ဖိုင်ကို ရယူခြင်း
        if update.message.video or (update.message.document and update.message.document.mime_type.startswith('video/')):
            print(f"[1/5] Telegram မှ ဗီဒီယိုဖိုင်ကို ဒေါင်းလုဒ်လုပ်နေပါသည်... (User: {user_id})")
            await status_msg.edit_text("⏳ [1/5]: Telegram မှ ဗီဒီယိုဖိုင်ကို သိမ်းဆည်းနေပါသည်...")
            
            video_obj = update.message.video or update.message.document
            tg_file = await context.bot.get_file(video_obj.file_id)
            await tg_file.download_to_drive(input_vid)
            
        elif update.message.text:
            url = update.message.text.strip()
            print(f"[1/5] Link မှ Video ကို yt-dlp ဖြင့် ဒေါင်းလုဒ်လုပ်နေပါသည်...")
            await status_msg.edit_text("⏳ [1/5]: Link မှ ဗီဒီယိုကို ဒေါင်းလုဒ်ဆွဲနေပါသည်...")
            
            ydl_opts = {
                'format': 'mp4/best[ext=mp4]/best',
                'outtmpl': input_vid,
                'overwrites': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'nocheckcertificate': True,
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            }
            if os.path.exists('cookies.txt'):
                ydl_opts['cookiefile'] = 'cookies.txt'

            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        else:
            await status_msg.edit_text("❌ ကျေးဇူးပြု၍ Video ဖိုင် (သို့) Link ပေးပို့ပါ။")
            return

        # Thumbnail ဖန်တီးခြင်း
        subprocess.run(['ffmpeg', '-y', '-ss', '00:00:50', '-i', input_vid, '-vframes', '1', thumbnail_file], check=True)

        # [2/5] Groq Whisper API ဖြင့် စာသားပြောင်းခြင်း (RAM လုံးဝမစားပါ)
        print("[2/5] Groq Whisper API ဖြင့် စာသားပြောင်းနေပါသည်...")
        await status_msg.edit_text("🎙️ [2/5]: Groq API ဖြင့် စာသား ထုတ်ယူနေပါသည်...")
        
        def transcribe_audio():
            with open(input_vid, "rb") as audio_f:
                transcript = groq_client.audio.transcriptions.create(
                    file=(input_vid, audio_f.read()),
                    model="whisper-large-v3-turbo",
                    response_format="text"
                )
            return transcript

        original_text = await asyncio.to_thread(transcribe_audio)

        # [3/5] Groq ဖြင့် ဘာသာပြန်ခြင်း (အင်္ဂလိပ်စာလုံးများကို အင်္ဂလိပ်လိုအတိုင်း ချန်ထားမည်)
        print("[3/5] Groq ဖြင့် ဘာသာပြန်နေပါသည်...")
        await status_msg.edit_text("🔄 [3/5]: Groq ဖြင့် မြန်မာစကားပြောဟန် ပြန်ဆိုနေပါသည်...")
        
        prompt = (
            "Translate the following transcript into natural, fluent spoken Burmese conversational style (စကားပြောဟန်).\n"
            "CRITICAL RULES:\n"
            "1. KEEP original English technical terms, proper nouns, brand names, and English words in English script (e.g., 'iPhone', 'Facebook', 'AI', 'Captain America'). Do NOT convert English words into Burmese spelling.\n"
            "2. Convert numbers into spoken Burmese words or keep digits clean.\n"
            "3. Use natural spoken sentence endings ('ပါတယ်', 'တယ်', 'ကြပါတယ်။').\n"
            "Return ONLY the translated text without markdown:\n\n"
            f"{original_text[:10000]}"
        )
        
        def fetch_translation():
            return groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
            ).choices[0].message.content.strip().replace('"', '').replace("'", "").replace("*", "")

        translated_text = await asyncio.to_thread(fetch_translation)

        # [4/5] edge-tts ဖြင့် အသံထုတ်ခြင်း
        print("[4/5] edge-tts ဖြင့် အသံထုတ်နေပါသည်...")
        await status_msg.edit_text("🔊 [4/5]: Microsoft Neural Voice ဖြင့် အသံဖန်တီးနေပါသည်...")
        
        VOICE = "my-MM-NilarNeural"
        communicate = edge_tts.Communicate(translated_text[:3000], VOICE, rate="+10%")
        await communicate.save(audio_file)

        # [5/5] SRT နှင့် FFmpeg ဗီဒီယို တည်းဖြတ်ခြင်း
        print("[5/5] FFmpeg ဖြင့် ဗီဒီယိုကို တည်းဖြတ်နေပါသည်...")
        await status_msg.edit_text("🎬 [5/5]: Pyidaungsu-Book-1.8_Regular ဖြင့် စာတန်းထိုး၍ တည်းဖြတ်နေပါသည်...")

        # TTS အသံကြာချိန် အတိအကျဖြင့် စာတန်းထိုး တိုင်မင်တွက်ခြင်း
        tts_duration = get_file_duration(audio_file)
        generate_srt(translated_text, tts_duration, filename=srt_file, max_chars=18)

        safe_srt_path = srt_file.replace("\\", "/").replace(":", "\\:")

        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', input_vid,
            '-i', audio_file,
            '-i', 'logo.png',
            '-filter_complex', 
            "[2:v]scale=520:-2[scaled_logo];" # Logo ကို ၂၁၀ pixel (တစ်ဝက်မက ပိုကြီးအောင် ပြင်ပေးထားသည်)
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:10[blurred];"
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[blurred][fg]overlay=(W-w)/2:(H-h)/2[v_bg];"
            f"[v_bg]subtitles=filename='{safe_srt_path}':force_style='Fontname=Pyidaungsu-Book,Fontsize=16,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=2,MarginV=120,Alignment=2'[v_sub];" # Fontsize=16 (သေးပေးထားသည်)
            "[v_sub][scaled_logo]overlay=W-w-40:40[outv]",
            '-map', '[outv]',
            '-map', '1:a:0',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-pix_fmt', 'yuv420p',
            '-shortest',
            output_vid
        ]
        
        await asyncio.to_thread(lambda: subprocess.run(ffmpeg_cmd, check=True))

        # Social Media Caption
        post_prompt = (
            "အောက်ပါ ရုပ်သံမှ ကူးယူထားသော စာသား (Transcript) ထဲပါသည့် အချက်အလက်များကိုသာ အခြေခံ၍ ဆိုရှယ်မီဒီယာအတွက် ခေါင်းစဉ်နှင့် အနှစ်ချုပ်ကို တိကျစွာ ရေးပေးပါ။ Transcript ထဲတွင် လုံးဝမပါဝင်သော အချက်အလက်များကို ကိုယ်ပိုင်မဖန်တီးရပါ။\n\n"
            "ပုံစံအတိုင်းသာ ရေးပါ:\n"
            "🚀 **[ခေါင်းစဉ်]**\n"
            "📝 **အနှစ်ချုပ်:** [Transcript ထဲပါသည့် အဓိက အကြောင်းအရာကို ၂ ကြောင်းဖြင့် တိကျစွာ ရေးရန်]\n"
            "#Hashtags\n\n"
            "CRITICAL: Keep strictly under 500 characters and base it ONLY on the transcript below.\n\n"
            f"Transcript: {translated_text}"
        )
        def fetch_caption():
            return groq_client.chat.completions.create(
                messages=[{"role": "user", "content": post_prompt}],
                model="llama-3.3-70b-versatile",
            ).choices[0].message.content.strip()

        post_caption = await asyncio.to_thread(fetch_caption)

        await status_msg.edit_text("📤 အားလုံးပြီးစီးပါပြီ! Telegram သို့ ပို့ဆောင်နေပါသည်...")

        with open(output_vid, 'rb') as video_file, open(thumbnail_file, 'rb') as thumb_file:
            await update.message.reply_video(
                video=video_file, 
                thumbnail=thumb_file, 
                caption=post_caption, 
                parse_mode="Markdown"
            )

        await status_msg.delete()
        print("--> လုပ်ဆောင်ချက် အောင်မြင်စွာ ပြီးဆုံးပါပြီ။")

    except Exception as e:
        print(f"Error occurred: {e}")
        await status_msg.edit_text(f"❌ အမှားယွင်း ဖြစ်ပေါ်ခဲ့သည်:\n{str(e)}")
        
    finally:
        for temp_file in [input_vid, output_vid, audio_file, thumbnail_file, srt_file]:
            if os.path.exists(temp_file):
                os.remove(temp_file)

# ==========================================
# 🚀 Main Bot Application
# ==========================================
def main():
    print("Bot is starting...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT | filters.VIDEO | filters.Document.ALL, process_video))
    
    print("Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
