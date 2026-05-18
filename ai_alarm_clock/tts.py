import os
import subprocess

from gtts import gTTS


class TextToSpeech:
    def __init__(self):
        self.filename = "output.mp3"
        self.lang = "ru"

    def speak(self, text):
        tts = gTTS(text=text, lang=self.lang)
        tts.save(self.filename)
        self.play_audio_smart()
        return self.filename

    def play_audio_smart(self):
        device = "hw:1,0"
        try:
            subprocess.run([
                "mpg123",
                "-a", device,
                "-q",
                self.filename
            ], check=True, timeout=120)
            return True
        except Exception as e:
            print(f"Ошибка mpg123: {e}")

    def delete_file(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)
