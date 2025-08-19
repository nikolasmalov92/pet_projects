from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import time
import urllib.parse
import random
import schedule
from parsing_xls import parsing_xls

chromedriver_autoinstaller.install()

options = webdriver.ChromeOptions()
options.add_argument("--user-data-dir=C:/Temp/ChromeProfile")
options.add_argument("--headless")  # Включение безголового режима
options.add_argument("--disable-gpu")  # Отключение GPU для ускорения работы в безголовом режиме
options.add_argument("--window-size=1920x1080")  # Установка размера окна

driver = webdriver.Chrome(options=options)


def send_messages():
    try:
        driver.get('https://web.whatsapp.com')
        time.sleep(12)

        result = parsing_xls()

        message_limit = 100  # Лимит на количество сообщений в час
        message_count = 0
        start_time = time.time()

        counter = 0
        for name, phone in result:
            counter += 1
            if message_count >= message_limit:
                elapsed_time = time.time() - start_time
                if elapsed_time < 3600:
                    time.sleep(3600 - elapsed_time)
                message_count = 0
                start_time = time.time()

            message = (f"Ваш текст сообщения здесь")
            encoded_message = urllib.parse.quote(message)
            url = f'https://wa.me/{phone}?text={encoded_message}'

            driver.get(url)
            time.sleep(random.uniform(5, 10))

            send_button_chat = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, 'Перейти в чат'))
            )
            send_button_chat.click()
            time.sleep(random.uniform(5, 10))

            send_button_whatsapp = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, 'перейти в WhatsApp Web'))
            )
            send_button_whatsapp.click()
            time.sleep(random.uniform(5, 10))

            send_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//*[@id="main"]/footer/div[1]/div/span/div/div[2]/div[2]/button'))
            )
            send_button.click()
            print(f'Сообщение отправлено №{counter}: {phone}')

            message_count += 1
            time.sleep(random.uniform(5, 10))

    finally:
        driver.quit()
        print("Сообщения всем гостям отправлено")


def check_time_and_schedule():
    now = datetime.now()
    print(f'now: {now}')
    if 12 <= now.hour < 17:
        print("Время для отправки сообщений. Выполнение задачи.")
        send_messages()
    else:
        print("Планирование задачи на следующий день c 12:00")

        next_run = (now + timedelta(days=3)).replace(hour=12, minute=0, second=0, microsecond=0)
        schedule.every().day.at(next_run.strftime("%H:%M")).do(send_messages)


def main():
    check_time_and_schedule()
    schedule.every().day.at("12:00").do(check_time_and_schedule)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    # main()
    send_messages()