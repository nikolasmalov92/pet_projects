import sys
import os
import datetime
import subprocess
import ctypes
import re
import logging
from pywinauto import Application

app = Application(backend="uia")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='logfile.log',
    filemode='a',
    encoding='utf-8'
)

setup_path = r"C:\Users\Nikolas\Downloads\smartgit-win-23_1_5\smartgit-23_1_5-setup.exe"
uninstall_path = r"C:\Program Files\SmartGit\unins000.exe"
adapter_name = "Ethernet 3"
file_name = "old_mac_addr.txt"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def get_current_date():
    return datetime.datetime.now().day


def delete_program():
    if os.path.exists(uninstall_path):
        try:
            running_exe(uninstall_path)
            logging.info("Программа SmartGit успешно удалена")
        except Exception as e:
            logging.info(f"Ошибка при удалении программы: {e}")
    else:
        logging.info("Файл для удаления не найден")


def mac_to_file():
    command = f'Get-NetAdapter -Name "{adapter_name}" | Select-Object Name, MacAddress'
    result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, shell=True)
    if result.returncode == 0:
        message = result.stdout
        with open(file_name, 'a', encoding='utf-8') as f:
            f.write(message + "\n")
            f.close()


def mac_from_file():
    with open(file_name, 'r', encoding='utf-8') as f:
        content = f.read()

    mac_pattern = r'[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}'
    mac_match = re.search(mac_pattern, content)

    if mac_match:
        result = mac_match.group()
        clean_mac = result.replace('-', '').upper()
        mac_int = int(clean_mac, 16)
        new_mac_int = mac_int + 1
        new_mac_hex = format(new_mac_int, '012X')
        new_mac = '-'.join([new_mac_hex[i:i + 2] for i in range(0, 12, 2)])
        return new_mac
    else:
        logging.info("MAC адрес не найден")
        return 0


def change_mac_address(new_mac):
    command = f'Set-NetAdapter -Name "{adapter_name}" -MacAddress {new_mac}'
    result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, shell=True)
    if result.returncode == 0:
        logging.info(f"Команда выполнена успешно")


def install_program():
    if os.path.exists(setup_path):
        try:
            running_exe(setup_path)
            logging.info("Установка программы запущена")
        except Exception as e:
            logging.info(f"Ошибка при запуске установки: {e}")
    else:
        logging.info("Файл установки не найден")


def running_exe(file_name):
    app.start(file_name)


def main():
    if not is_admin():
        logging.info("is not Admin")
        sys.exit(1)

    while True:
        current_date = get_current_date()
        if current_date == 27:
            logging.info("\n1. Удаление программы SmartGit...")
            delete_program()
            logging.info("\n2. Изменение MAC адреса...")
            mac_to_file()
            new_mac = mac_from_file()
            change_mac_address(new_mac)
            logging.info("\n3. Запуск установки...")
            install_program()
        else:
            break


if __name__ == '__main__':
    main()
