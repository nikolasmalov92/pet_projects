import requests


class News:
    def __init__(self):
        self.url = ("https://dzen.ru/api/web/v1/topic-channel?clid=1400&country_code=ru&content_type=article"
                    "&topic_identity=4784&rnd=1767889363295")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/143.0.0.0 Safari/537.36"
        }

    def get_topic_news(self):
        response = requests.get(self.url, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            items = data['feedData']['items']
            titles = []
            for item in items:
                title = item['title']
                titles.append(title)
            return "; ".join(titles)
