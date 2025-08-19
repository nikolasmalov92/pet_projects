import requests
import json
import time


def get_json(url):
    payload = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8,ru-RU;q=0.7',
        'Content-Type': 'application/json',
        'Cookie': '__Secure-ext_xcid=87b9102b63e294032a7842a5aa729995; __Secure-user-id=0; __Secure-ab-group=63; '
                  'is_cookies_accepted=1; __Secure-ETC=abf0102c6b179d2663fe877b77aacaaa; '
                  'xcid=6a8f50a66fe983438f6dcf69520c8992; '
                  'abt_data=976ccbecebce6054ed6d9fec3a2430d6'
                  ':add070772f3547eedbb60e59dfacd64a5e8b2c3db56ac9f403fb8065fefce008b9a0597392da1fd2e98c124551a4ad726aa16f843ec6a16ec9b353597fb340b6239e19c8141a1ecc28f3d2c6b0cffd9430587e87a2cf9b65e1788ea0cbe476b018f2500aac6e8e4856000cd7ceef14c31ecbd99abcd562da48ef66b52f82311017bbf738301d0025df3d18a767b5821c2b803718072904ec724d6e74d0c5a9f5aa3143a4e8bac8363bc8ddad33bfa13027e9f2b5b82df33fbd2aebe5208dbe5a5cf85830a2a9dc8dfe648b34b7e665e64582b5e08b7861671e0e404cacfa07f3813326ff52195d61e08c7f4a3b676d0f49483080e530cf6026fcc6ae646a71624be3e7f7277d4f7f5c780fcc0badc610a924f0b505055d636bd11f0d131d0b4750a8c246c350099a864fe617cd0b622c8901fd4159222729126814fd819d69a0707e7d6b2dc3264b29613d30fb287d787bace1b4880c5f897a684469901f2f1a; __Secure-access-token=5.0.x8oBWqqwQ0q2vFqawirknQ.63.Adhr7abMDTir_ADpSlj6ZEvydEdaRAkCcipjb3ukCdY9sRzNy4WmJE6ZLxyiNtyUOg..20240719153612.OIfTfCQuHX0Eyt0wFtH9DwdHP6-yOZ8FDvw1puu4b5I.1d02d4820030d5176; __Secure-refresh-token=5.0.x8oBWqqwQ0q2vFqawirknQ.63.Adhr7abMDTir_ADpSlj6ZEvydEdaRAkCcipjb3ukCdY9sRzNy4WmJE6ZLxyiNtyUOg..20240719153612.4FxGi_3o__M5HD78FbqWZQcV551QT5mREJiUJ1sTr7g.1b19350a52852c1e3; rfuid=NjkyNDcyNDUyLDEyNC4wNDM0NzUyNzUxNjA3NCwxNjk2NTQ1MzkyLC0xLDIwMDQwMjc5NTcsVzNzaWJtRnRaU0k2SWxCRVJpQldhV1YzWlhJaUxDSmtaWE5qY21sd2RHbHZiaUk2SWxCdmNuUmhZbXhsSUVSdlkzVnRaVzUwSUVadmNtMWhkQ0lzSW0xcGJXVlVlWEJsY3lJNlczc2lkSGx3WlNJNkltRndjR3hwWTJGMGFXOXVMM0JrWmlJc0luTjFabVpwZUdWeklqb2ljR1JtSW4wc2V5SjBlWEJsSWpvaWRHVjRkQzl3WkdZaUxDSnpkV1ptYVhobGN5STZJbkJrWmlKOVhYMHNleUp1WVcxbElqb2lRMmh5YjIxbElGQkVSaUJXYVdWM1pYSWlMQ0prWlhOamNtbHdkR2x2YmlJNklsQnZjblJoWW14bElFUnZZM1Z0Wlc1MElFWnZjbTFoZENJc0ltMXBiV1ZVZVhCbGN5STZXM3NpZEhsd1pTSTZJbUZ3Y0d4cFkyRjBhVzl1TDNCa1ppSXNJbk4xWm1acGVHVnpJam9pY0dSbUluMHNleUowZVhCbElqb2lkR1Y0ZEM5d1pHWWlMQ0p6ZFdabWFYaGxjeUk2SW5Ca1ppSjlYWDBzZXlKdVlXMWxJam9pUTJoeWIyMXBkVzBnVUVSR0lGWnBaWGRsY2lJc0ltUmxjMk55YVhCMGFXOXVJam9pVUc5eWRHRmliR1VnUkc5amRXMWxiblFnUm05eWJXRjBJaXdpYldsdFpWUjVjR1Z6SWpwYmV5SjBlWEJsSWpvaVlYQndiR2xqWVhScGIyNHZjR1JtSWl3aWMzVm1abWw0WlhNaU9pSndaR1lpZlN4N0luUjVjR1VpT2lKMFpYaDBMM0JrWmlJc0luTjFabVpwZUdWeklqb2ljR1JtSW4xZGZTeDdJbTVoYldVaU9pSk5hV055YjNOdlpuUWdSV1JuWlNCUVJFWWdWbWxsZDJWeUlpd2laR1Z6WTNKcGNIUnBiMjRpT2lKUWIzSjBZV0pzWlNCRWIyTjFiV1Z1ZENCR2IzSnRZWFFpTENKdGFXMWxWSGx3WlhNaU9sdDdJblI1Y0dVaU9pSmhjSEJzYVdOaGRHbHZiaTl3WkdZaUxDSnpkV1ptYVhobGN5STZJbkJrWmlKOUxIc2lkSGx3WlNJNkluUmxlSFF2Y0dSbUlpd2ljM1ZtWm1sNFpYTWlPaUp3WkdZaWZWMTlMSHNpYm1GdFpTSTZJbGRsWWt0cGRDQmlkV2xzZEMxcGJpQlFSRVlpTENKa1pYTmpjbWx3ZEdsdmJpSTZJbEJ2Y25SaFlteGxJRVJ2WTNWdFpXNTBJRVp2Y20xaGRDSXNJbTFwYldWVWVYQmxjeUk2VzNzaWRIbHdaU0k2SW1Gd2NHeHBZMkYwYVc5dUwzQmtaaUlzSW5OMVptWnBlR1Z6SWpvaWNHUm1JbjBzZXlKMGVYQmxJam9pZEdWNGRDOXdaR1lpTENKemRXWm1hWGhsY3lJNkluQmtaaUo5WFgxZCxXeUp5ZFNKZCwwLDEsMCwyNCwyMzc0MTU5MzAsOCwyMjcxMjY1MjAsMCwxLDAsLTQ5MTI3NTUyMyxSMjl2WjJ4bElFbHVZeTRnVG1WMGMyTmhjR1VnUjJWamEyOGdWMmx1TXpJZ05TNHdJQ2hYYVc1a2IzZHpJRTVVSURFd0xqQTdJRmRwYmpZME95QjROalFwSUVGd2NHeGxWMlZpUzJsMEx6VXpOeTR6TmlBb1MwaFVUVXdzSUd4cGEyVWdSMlZqYTI4cElFTm9jbTl0WlM4eE1qWXVNQzR3TGpBZ1UyRm1ZWEpwTHpVek55NHpOaUF5TURBek1ERXdOeUJOYjNwcGJHeGgsZXlKamFISnZiV1VpT25zaVlYQndJanA3SW1selNXNXpkR0ZzYkdWa0lqcG1ZV3h6WlN3aVNXNXpkR0ZzYkZOMFlYUmxJanA3SWtSSlUwRkNURVZFSWpvaVpHbHpZV0pzWldRaUxDSkpUbE5VUVV4TVJVUWlPaUpwYm5OMFlXeHNaV1FpTENKT1QxUmZTVTVUVkVGTVRFVkVJam9pYm05MFgybHVjM1JoYkd4bFpDSjlMQ0pTZFc1dWFXNW5VM1JoZEdVaU9uc2lRMEZPVGs5VVgxSlZUaUk2SW1OaGJtNXZkRjl5ZFc0aUxDSlNSVUZFV1Y5VVQxOVNWVTRpT2lKeVpXRmtlVjkwYjE5eWRXNGlMQ0pTVlU1T1NVNUhJam9pY25WdWJtbHVaeUo5ZlgxOSw2NSwtMTI4NTU1MTMsMSwxLC0xLDE2OTk5NTQ4ODcsMTY5OTk1NDg4Nyw1NzkzNTUxNzUsMTI=; ADDRESSBOOKBAR_WEB_CLARIFICATION=1721396174',
        'Referer': 'https://www.ozon.ru/st/service-worker/1.0.43.js',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin'}
    response = requests.request('GET', url=url, headers=headers, data=payload)

    if response.status_code == 200:
        return response.json()

    else:
        print(f'Результат ошибки: {response.status_code}')


def get_product_info(result_json):
    product = {}
    widgets = result_json['widgetStates']
    for widget_name, widget_value in widgets.items():
        if 'webProductHeading' in widget_name:
            widget_value = json.loads(widget_value)
            product['title'] = widget_value['title']

        elif 'webAspects' in widget_name:
            widget_value = json.loads(widget_value)
            price = widget_value['aspects'][0]['variants'][-1]['data']['price']
            product['price'] = int(price.replace('\u2009', '').replace('₽', ''))

    return product


def main():
    url = input('Введите ссылку: ')
    split_url = url.split('https://www.ozon.ru/product/')
    api_url = "https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2" \
              f"?url=/product/{split_url[1]}"

    result_json = get_json(api_url)
    if result_json:
        product = get_product_info(result_json)
        print(f"\nНазвание: {product['title']}")
        print(f"Цена: {product['price']}\n")


if __name__ == '__main__':
    while True:
        main()
        time.sleep(5)
