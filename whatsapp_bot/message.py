from whatsapp import *
import time
import random
from typing import Tuple
from datetime import datetime


class MessageBot(WhatsappBot):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.data = []
        self.message_limit: Tuple[int, int] = (30, 40)  # лимит на количество сообщений в час
        self.daily_limit: int = 350  # лимит на количество сообщений в день
        self.current_hourly_limit: int = random.randint(*self.message_limit)

        self.start_time = time.time()
        self._is_authenticated: bool | None = None
        self._auth_code: str | None = None

    def authenticate(self, phone: str) -> dict:
        if self.check_auth_status():
            self._is_authenticated = True
            return {"authenticated": True, "code": None, "error": None, "message": "Уже авторизован"}

        result = self.login_to_whatsapp(phone)
        self._is_authenticated = result["success"]
        self._auth_code = result["code"] if result["success"] else None

        return {
            "authenticated": self._is_authenticated,
            "code": self._auth_code,
            "error": None if result["success"] else result["error"],
            "message": "Требуется ввод кода" if result["success"] else "Ошибка авторизации"
        }

    @property
    def is_authenticated(self) -> bool:
        return bool(self._is_authenticated)

    @property
    def auth_code(self) -> str | None:
        return self._auth_code

    @staticmethod
    def message() -> str:
        messages = ["Добро пожаловать!", "Рады видеть вас!", "Приветствуем вас!"]
        msg = random.choice(messages)
        return msg

    def send_messages(self):
        if not self.data:
            return False

        counter = 0
        message_count = 0
        daily_count = 0
        sent_this_hour = 0
        current_hour = datetime.now().hour

        try:
            for name, phone in self.data:
                counter += 1
                if message_count >= self.current_hourly_limit:
                    elapsed_time = time.time() - self.start_time
                    if elapsed_time < 3600:
                        time.sleep(3600 - elapsed_time)
                    message_count = 0
                    self.start_time = time.time()

                if daily_count >= self.daily_limit:
                    print("Достигнут дневной лимит, завершаю работу.")
                    break

                if sent_this_hour >= self.current_hourly_limit:
                    print("Достигнут лимит в час, жду до следующего часа...")
                    while datetime.now().hour == current_hour:
                        time.sleep(60)
                    current_hour = datetime.now().hour
                    sent_this_hour = 0

                self.new_chat(phone)
                self.input_chat(self.message())
                message_count += 1
                daily_count += 1
                sent_this_hour += 1

                print(f'Сообщение {message_count} отправлено: {name} ({phone})')
                time.sleep(random.randint(7, 20))

            self.close()
            return True, "Все номера отправлены"

        except Exception as error:
            return False, error
