import time

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class WhatsappBot:
    def __init__(self, user_id: int, timeout: int = 30):
        self.user_id = str(user_id)
        self.driver = None
        self.url = 'https://web.whatsapp.com'
        self.timeout = timeout

    def _init_driver(self):
        chromedriver_autoinstaller.install()
        options = webdriver.ChromeOptions()
        options.add_argument(f"--user-data-dir=C:/Temp/ChromeProfile_{self.user_id}")
        options.add_argument("--window-size=1920x1080")
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)

    def _wait_for(self, condition, timeout=None):
        return WebDriverWait(self.driver, timeout or self.timeout).until(condition)

    def check_auth_status(self) -> bool:
        if not self.driver:
            self._init_driver()

        try:
            # Ждём появления QR-кода
            self._wait_for(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[@id='app']//canvas")
                ),
                timeout=25
            )
            return False
        except:
            return True

    def login_to_whatsapp(self, phone: str) -> dict:
        try:
            time.sleep(1)
            if self.check_auth_status():
                return {
                    "authenticated": True,
                    "code": None,
                    "error": None,
                    "message": "Уже авторизован"
                }

            button = self._wait_for(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Войти по номеру телефона')]")),
                timeout=60
            )
            button.click()

            time.sleep(1)
            choosing_country = self._wait_for(
                EC.element_to_be_clickable((By.XPATH, "//*[@id='app']//button/div/div/div"))
            )
            choosing_country.click()

            time.sleep(1)
            input_field = self._wait_for(
                EC.visibility_of_element_located((By.XPATH, "//*[@id='app']//form/input"))
            )
            input_field.send_keys(Keys.BACKSPACE)
            input_field.send_keys(Keys.BACKSPACE)
            input_field.send_keys(Keys.BACKSPACE)            
            input_field.send_keys(phone)

            time.sleep(1)
            btn_next = self._wait_for(
                EC.element_to_be_clickable((By.XPATH, "//*[@id='app']/div/div/div[2]/div[2]/div[2]/div/div/div["
                                                      "3]/div[3]/button/div/div")),
            )
            btn_next.click()

            time.sleep(1)
            code_div = self._wait_for(
                EC.presence_of_element_located((By.XPATH, "//div[@data-link-code]")),
                timeout=60
            )
            secret_code = code_div.get_attribute("data-link-code")

            return {"code": secret_code, "success": True, "error_message": None}

        except Exception as e:
            return {"code": None, "success": False, "error_message": str(e)}

    def new_chat(self, phone: str):
        time.sleep(1)
        btn_add = self._wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='app']/div/div/div[3]/div/div["
                                                  "4]/header/header/div/span/div/div[1]/span/button/div/div/div["
                                                  "1]/span")),
        )
        btn_add.click()

        time.sleep(1)
        btn_add_phone = self._wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='app']/div/div/div[3]/div/div[3]/div["
                                                  "1]/div/span/div/span/div/div[1]/div[2]/div/div/div[1]/p")),
        )
        btn_add_phone.click()
        btn_add_phone.send_keys(phone)
        btn_add_phone.send_keys(Keys.ENTER)

    def input_chat(self, message: str):
        time.sleep(1)
        input_message = self._wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='main']/footer/div[1]/div/span/div/div[2]/div/div[3]/div["
                                                  "1]/p")),
            timeout=100
        )
        input_message.click()
        input_message.send_keys(message)
        input_message.send_keys(Keys.ENTER)

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
