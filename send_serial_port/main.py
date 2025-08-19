import serial
import serial.tools.list_ports
import time
from serial import SerialException
from config import MESSAGES, SCANNER_CONFIG


class BarcodeScanner:
    def __init__(self):
        self.baudrate = SCANNER_CONFIG["baudrate"]
        self.timeout = SCANNER_CONFIG["timeout"]
        self.max_length_code = SCANNER_CONFIG["max_length_code"]
        self.last_barcode = None
        self.ser = None

    def connect(self):
        """Подключение к первому доступному COM порту."""
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print(MESSAGES.get("connection_failed"))
            return False

        try:
            self.ser = serial.Serial(ports[0].device, self.baudrate, timeout=self.timeout)
            print(MESSAGES.get("connected"))
            return True
        except SerialException:
            print(MESSAGES.get('connection_failed'))
            return False

    def validate_barcode(self, barcode):
        """Проверка штрих-кода на корректность."""
        if not barcode:
            print(MESSAGES.get("empty_barcode"))
            return False
        if len(barcode) != self.max_length_code or not barcode.isdigit():
            print(MESSAGES.get("invalid_barcode"))
            return False
        return True

    def send_message(self, barcode):
        """Отправка штрих-кода через COM порт."""
        try:
            self.ser.write(barcode.encode("utf-8"))
            print(MESSAGES.get("success"))
            self.last_barcode = barcode
        except SerialException:
            print(f"{MESSAGES.get('connection_failed')}")

    def confirm_barcode(self, barcode):
        """Подтверждение повторной отправки штрих-кода."""
        while True:
            response = input(
                "Штрих-код считан повторно.\n"
                "Нажмите [Enter] для повторной отправки или [n] для отмены: "
            ).strip().lower()

            if response == "":
                self.send_message(barcode)
                return True
            elif response == "n":
                print(MESSAGES.get("cancel_barcode"))
                return False
            else:
                print(MESSAGES.get("incorrect_input"))

    def main(self):
        while self.ser is None or not self.ser.is_open:
            if not self.connect():
                time.sleep(2)

        while True:
            barcode = input(MESSAGES.get("scan_barcode")).strip()

            if barcode == self.last_barcode:
                if self.confirm_barcode(barcode):
                    continue
                else:
                    continue

            if self.validate_barcode(barcode):
                self.send_message(barcode)

            time.sleep(1)


if __name__ == "__main__":
    scanner = BarcodeScanner()
    scanner.main()
