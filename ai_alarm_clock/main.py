import time
from datetime import datetime
import pytz
from pogoda import Pogoda
from traffic import Traffic
from news import News
from ai import Assistant
from tts import TextToSpeech
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pogoda = Pogoda()
traffic = Traffic()
news = News()
ai_assistant = Assistant()
tts = TextToSpeech()


def time_now():
    kazan_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(kazan_tz)
    return now.strftime("%H:%M")


def main():
    now = time_now()
    now_weather = pogoda.get_weather()
    now_traffic = traffic.get_traffic_score()
    time_direction = traffic.get_direction()
    topic_news = news.get_topic_news()
    text = ai_assistant.get_response(now, now_weather, now_traffic, time_direction, topic_news)
    tts.delete_file()
    tts.speak(text)


def run():
    while True:
        now_time = time_now()
        hours, minutes = now_time.split(":")
        if hours == "07" and minutes == "59":
            logger.info(f"⏰ Время будильника! {now_time}")
            main()
            time.sleep(3600)


if __name__ == '__main__':
    run()
