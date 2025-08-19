import pandas as pd
import re


def parsing_xls():
    file_path = 'avtor_sushi.xlsx'
    df = pd.read_excel(file_path, dtype={'Телефон': str})
    if 'Телефон' in df.columns:
        phone_numbers = df['Телефон'].dropna().tolist()
        def format_phone_number(phone):
            cleaned_phone = re.sub(r'[^\d+]', '', phone)
            return cleaned_phone

        formatted_numbers = [format_phone_number(number) for number in phone_numbers]

        return formatted_numbers

    else:
        print("Столбец 'Телефон' не найден в файле.")
        return None


if __name__ == '__main__':
    parsing_xls()
