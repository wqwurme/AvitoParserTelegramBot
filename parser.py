import httpx
from bs4 import BeautifulSoup
from typing import List, Dict

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def parse_avito(url: str) -> List[Dict]:
    """
    Парсит страницу Avito и возвращает список объявлений.
    Каждое объявление: {"title": ..., "price": ..., "link": ...}
    """
    try:
        response = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[Парсер] Ошибка запроса: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = []

    # Avito использует data-атрибуты для карточек товаров
    cards = soup.select("div[data-marker='item']")

    for card in cards:
        try:
            # Название
            title_el = card.select_one("h3[itemprop='name']")
            title = title_el.get_text(strip=True) if title_el else "Без названия"

            # Цена
            price_el = card.select_one("meta[itemprop='price']")
            price = price_el["content"] + " ₽" if price_el else "Цена не указана"

            # Ссылка
            link_el = card.select_one("a[data-marker='item-title']")
            link = "https://www.avito.ru" + link_el["href"] if link_el else None

            if not link:
                continue

            items.append({"title": title, "price": price, "link": link})

        except Exception as e:
            print(f"[Парсер] Ошибка обработки карточки: {e}")
            continue

    print(f"[Парсер] Найдено объявлений: {len(items)}")
    return items
