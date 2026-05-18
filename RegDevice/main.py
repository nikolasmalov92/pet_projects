import time
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class DeviceBot:
    def __init__(self):
        self.auth_prime = False
        self.driver = None
        self.url = 'https://192.168.100.1/auth'
        self.timeout = 15

    def init_driver(self):
        chromedriver_autoinstaller.install()
        options = webdriver.ChromeOptions()
        prefs = {"profile.default_content_setting_values.media_stream_camera": 2}
        options.add_experimental_option("prefs", prefs)
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)
        self.driver.execute_script("document.body.style.zoom='50%'")

    def wait_for(self, condition, timeout=None):
        return WebDriverWait(self.driver, timeout or self.timeout).until(condition)

    def connect(self):
        if self.auth_prime == "True":
            return

        time.sleep(1)

        self.driver.execute_script("document.body.style.zoom='50%'")

        details = self.wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='details-button']")),
            timeout=15
        )
        details.click()

        next_page = self.wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='proceed-link']")),
            timeout=15
        )
        next_page.click()
        time.sleep(5)

    def admin_page(self):
        self.driver.execute_script("document.body.style.zoom='50%'")
        if self.auth_prime == "True":
            return

        admin_name = self.wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='username']")),
            timeout=15
        )
        admin_name.click()
        admin_name.send_keys('admin')
        time.sleep(2)

        admin_pass = self.wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='password']")),
            timeout=15
        )
        admin_pass.click()
        admin_pass.send_keys('admin')
        time.sleep(1)

        auth_button = self.wait_for(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='app']/div/div/button")),
            timeout=15
        )
        auth_button.click()
        self.auth_prime = True
        time.sleep(5)

    def added_number(self, count_ser):
        self.driver.execute_script("document.body.style.zoom='50%'")
        time.sleep(2)

        button_0 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#app div button:nth-of-type(2) p")),
            timeout=15
        )
        button_0.click()
        time.sleep(2)

        button_1 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#DevicesConfig button span")),
            timeout=15
        )
        button_1.click()
        time.sleep(2)

        button_2 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "body > div.p-dialog-mask.p-component-overlay.p-component"
                                                         "-overlay-enter > div > div.p-dialog-content > "
                                                         "div.p-dialog-content-custom > div.grid.mb-6 > "
                                                         "div:nth-child(2) > div > div:nth-child(1) > label")),
            timeout=15
        )
        button_2.click()
        time.sleep(2)

        button_3 = self.wait_for(
            EC.element_to_be_clickable((By.ID, "serial_number")), timeout=10
        )
        button_3.click()
        count_ser += 1
        serial_number = self.get_serial_number(count_ser)
        if serial_number is None:
            return None

        button_3.clear()
        button_3.send_keys(serial_number)

        button_4 = self.wait_for(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[6]/div/div[2]/div[2]/div[2]/div/div[2]/div["
                                                  "2]/button/span")), timeout=60
        )
        button_4.click()
        time.sleep(2)
        button_5 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                        "body > div:nth-child(7) > div > div.p-dialog-content > "
                                        "div.p-dialog-content-custom > div.flex.w-full > button > span")),
            timeout=15
        )
        button_5.click()
        time.sleep(3)

        button_6 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                        r"body > div.p-dialog-mask.p-component-overlay.p-component-overlay-enter > div "
                                        r"> div.p-dialog-content > div.p-dialog-header-custom > "
                                        r"div.hide-in-mobile.grid.w-full.align-items-baseline.mb-6 > "
                                        r"div.col-12.md\:col-6.flex.md\:justify-content-end.flex-wrap > button > span")),
            timeout=15
        )
        button_6.click()
        time.sleep(3)

        return count_ser

    def added_zone(self, serial_number):
        button_6 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                        "body > div.p-dialog-mask.p-component-overlay.p-component-overlay-enter > div "
                                        "> div.p-dialog-content > div.p-dialog-content-custom > div:nth-child(3) > "
                                        "button > span")),
            timeout=60
        )
        button_6.click()
        time.sleep(2)

        button_7 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#nameinput")),
            timeout=60
        )
        button_7.click()
        button_7.clear()
        name_base_zone = self.get_name_base_zone(serial_number)
        button_7.send_keys(name_base_zone)
        time.sleep(2)

        button_8 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#deviceIdinput")),
            timeout=60
        )
        button_8.click()
        time.sleep(2)

        button_9 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#deviceIdinput_0")),
            timeout=60
        )
        button_9.click()
        time.sleep(2)

        button_10 = self.wait_for(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                        r"body > div:nth-child(6) > div > "
                                        r"div.p-dialog-content.flex-grow-1.md\:flex-grow-0 > "
                                        r"div.p-dialog-content-custom.md\:mx-5 > div:nth-child(3) > div:nth-child(2) "
                                        r"> form > div.flex.justify-content-center > button > span")),
            timeout=60
        )
        button_10.click()
        time.sleep(2)

    @staticmethod
    def get_serial_number(i):
        number = [
            "938000921",
            "938000922",
            "938000923",
            "974000944",
            "974000945",
            "944000916",
            "979000917",
            "946000998",
            "963000909",
            "954000960",
            "964000969",
            "958000998",
            "956000997",
            "957000936",
            "955000965",
            "959000975",
            "990000924",
            "941000923",
            "940000952",
            "978000971",
        ]
        if i >= len(number):
            return None

        return number[i]


if __name__ == '__main__':
    bot = DeviceBot()
    bot.init_driver()
    bot.connect()
    bot.admin_page()
    # print(f'1. Регистрация устройств\n'
    #       f'2. Создание зоны\n'
    #       f'3. Создание входа\n'
    #       f'4. Создание выхода\n')
    # action = int(input(f'Введите, номер шага действия'))
    try:
        count_ser = -1
        while True:
            result = bot.added_number(count_ser)
            if result is None:
                print("\n -- Все устройства добавлены.")
                break
            count_ser = result

    except KeyboardInterrupt:
        print("Получен Ctrl+C, выходим...")
    finally:
        if bot.driver:
            bot.driver.quit()
