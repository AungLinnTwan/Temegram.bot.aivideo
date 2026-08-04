import os
import asyncio
import subprocess
import whisper
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
from google.cloud import texttospeech
from google import genai

TELEGRAM_BOT_TOKEN = "8479798480:AAGxyNW1l5zq2ucjzRSVfwdOlx5eHU3oMB4"
GEMINI_API_KEY = "AIzaSyAwwSlzAUpRaKRjIpFPeQd704aEJz-EVOo"

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_credentials.json"
genai_client = genai.Client(api_key=GEMINI_API_KEY)

import whisper
model = whisper.load_model("tiny")  # หรือ "base" လို့ ပြောင်းပေးပါ

def format_timestamp(seconds):
    millis = int((seconds % 1) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"--> Link လက်ခံရရှိပါသည်: {update.message.text}")
    status_msg = await update.message.reply_text("⏳ ဗီဒီယိုကို စတင် စေခိုင်းနေပါသည်...")
    url = update.message.text.strip()

    try:
        print("[1/5] Video ဒေါင်းလုဒ်ဆွဲနေသည်...")
        ydl_opts = {
            'format': 'mp4/best[ext=mp4]/best',
            'outtmpl': 'input_video.mp4',
            'overwrites': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'nocheckcertificate': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print("[2/5] Whisper တေးသံမှ စာသားပြောင်းနေသည်...")
        await status_msg.edit_text("🎙️ [1/5]: Whisper ဖြင့် အသံမှ စာသားပြောင်းနေပါသည်...")
        result = whisper_model.transcribe("input_video.mp4")
        original_text = result["text"]

        print("[3/5] Gemini ဘာသာပြန်နေသည်...")
        await status_msg.edit_text("🔄 [2/5]: Gemini ဖြင့် စကားပြောဟန် ပြန်ဆိုနေပါသည်...")
        prompt = (
            "Translate the following transcript into natural, fluent Burmese news narration style. "
            "Use clear, clean Burmese standard words. Keep sentences natural for Text-To-Speech audio output. "
            "Do NOT include special markdown symbols or English characters. "
            "Return ONLY the translated Burmese text:\n\n"
            f"{original_text[:10000]}"
        )
        response = genai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        translated_text = response.text.strip().replace("'", "").replace('"', '').replace("*", "")

        print("[4/5] Google TTS အသံထုတ်နေသည်...")
        await status_msg.edit_text("🔊 [3/5]: Google TTS ဖြင့် အသံဖန်တီးနေပါသည်...")
        tts_client = texttospeech.TextToSpeechClient()
        voice = texttospeech.VoiceSelectionParams(language_code="my-MM")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        chunk_size = 800
        chunks = [translated_text[i:i + chunk_size] for i in range(0, len(translated_text), chunk_size)]
        
        combined_audio = bytearray()
        for chunk in chunks:
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
            tts_response = tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            combined_audio.extend(tts_response.audio_content)

        with open("new_audio.mp3", "wb") as out:
            out.write(combined_audio)

        print("[4.5/5] SRT Subtitle ဖိုင် အချိန်ကိုက် ဖန်တီးနေသည်...")
        segments = result.get("segments", [])
        srt_lines = []
        
        lines = [l.strip() for l in translated_text.split("။") if l.strip()]
        num_lines = len(lines)
        num_segs = len(segments)
        
        if num_segs > 0 and num_lines > 0:
            for idx, line in enumerate(lines):
                seg_idx = int((idx / num_lines) * num_segs)
                seg = segments[min(seg_idx, num_segs - 1)]
                start_time = format_timestamp(seg["start"])
                end_time = format_timestamp(seg["end"])
                srt_lines.append(f"{idx + 1}\n{start_time} --> {end_time}\n{line}။\n")
        else:
            srt_lines.append(f"1\n00:00:00,000 --> 00:00:10,000\n{translated_text[:100]}...\n")

        with open("subtitles.srt", "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        print("[5/5] FFmpeg Video တည်းဖြတ်နေသည်...")
        await status_msg.edit_text("🎬 [4/5]: Video တည်းဖြတ်ခြင်းနှင့် Thumbnail ထုတ်ယူနေပါသည်...")
        
        thumb_cmd = [
            'ffmpeg', '-y', '-ss', '00:00:05', '-i', 'input_video.mp4',
            '-vframes', '1', '-q:v', '2', 'thumbnail.jpg'
        ]
        subprocess.run(thumb_cmd, check=True)

        font_style = "Fontname=Pyidaungsu.ttf,Fontsize=22,PrimaryColour=&H00FFFFFF,BackColour=&H80000000,BorderStyle=4,MarginV=35,Outline=1"

        has_logo = os.path.exists("logo.png")
        if has_logo:
            filter_complex = (
                f"[2:v]scale=80:-1[resized_logo];"
                f"[0:v][resized_logo]overlay=main_w-overlay_w-15:15[v_logo];"
                f"[v_logo]subtitles=subtitles.srt:force_style='{font_style}'[outv]"
            )
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', 'input_video.mp4',
                '-i', 'new_audio.mp3',
                '-i', 'logo.png',
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '1:a:0',
                '-c:v', 'libx264',
                '-shortest',
                'output_video.mp4'
            ]
        else:
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', 'input_video.mp4',
                '-i', 'new_audio.mp3',
                '-vf', f"subtitles=subtitles.srt:force_style='{font_style}'",
                '-c:v', 'libx264',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                'output_video.mp4'
            ]
            
        subprocess.run(ffmpeg_cmd, check=True)

        post_prompt = (
            "Based on the following Burmese transcript, write a short social media post caption in Burmese:\n"
            "📌 **[Catchy Title]**\n\n"
            "📝 **အနှစ်ချုပ်:** [Short 2 sentence summary]\n\n"
            "#Hashtags\n\n"
            "CRITICAL: Keep strictly under 300 characters.\n\n"
            f"{translated_text}"
        )
        post_response = genai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=post_prompt,
        )
        post_caption = post_response.text.strip()

        await status_msg.edit_text("📤 [5/5]: Telegram သို့ ပို့ဆောင်နေပါသည်...")
        
        with open('output_video.mp4', 'rb') as video_file, open('thumbnail.jpg', 'rb') as thumb_file:
            await update.message.reply_video(
                video=video_file, thumbnail=thumb_file, caption=post_caption, parse_mode="Markdown"
            )
            
        await status_msg.delete()
        print("--> လုပ်ဆောင်ချက် အောင်မြင်စွာ ပြီးဆုံးပါပြီ။")

    except Exception as e:
        print(f"Error occurred: {e}")
        await status_msg.edit_text(f"❌ အမှားယွင်း ဖြစ်ပေါ်ခဲ့သည်: {e}")

def main():
    print("Bot starting...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_video))
    print("Bot is running! Telegram မှ link စောင့်နေပါသည်...")
    app.run_polling()

if __name__ == '__main__':
    main()
