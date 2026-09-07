import json
import os
import re
import requests

# Берем секреты из переменных окружения GitHub
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DB_FILE = "sent_tenders.json"

# --- Критерии из вашего ТЗ ---
MIN_PRICE = 550000
MAX_PRICE = 11000000

EXCLUDED_REGIONS = [
    "амурская", "бурятия", "еврейская", "забайкальский", "камчатский", "магаданская", 
    "приморский", "якутия", "сахалин", "хабаровский", "чук",
    "дагестан", "ингушетия", "кабардино", "карачаево", "осетия", "ставропольский", "чечен",
    "алтай", "иркутск", "кемерово", "красноярский", "новосибирск", "омская", "томская", "тыва", "хакасия",
    "днр", "лнр", "донецк", "луганск", "запорож", "херсон",
    "казахстан", "беларусь", "абхазия", "армения", "киргиз", "узбек", "за пределами"
]

ALLOWED_INDUSTRIES = [
    "металлич", "огражден", "ковк", "малые архитектурные", "малых архитектурных",
    "мобильные", "бетонные сооружен", "здания", "мебель", "интерьер", "реклам", 
    "маркетинг", "дизайн", "детские товары", "резервуар", "емкост", "ёмкост", 
    "ремонт", "обслуживание", "кондиционер", "тепловое", "торговое", "складское", 
    "хранение", "навигацион", "общего назначения", "учебное", "спортивн", "турист", 
    "тренажер", "площадк", "развлекательн", "отдых", "лом", "жкх"
]

ALLOWED_LAWS = ["44-фз", "223-фз"]
ALLOWED_METHODS = ["аукцион", "запрос котировок", "запрос предложений"]
ALLOWED_STAGE = "прием заявок"

def load_sent_tenders():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: return set(json.load(f))
            except json.JSONDecodeError: return set()
    return set()

def save_sent_tenders(sent_set):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_set), f, ensure_ascii=False, indent=4)

def parse_price(price_str):
    if isinstance(price_str, (int, float)): return float(price_str)
    if not price_str: return 0.0
    cleaned = re.sub(r'[^\d.,]', '', str(price_str)).replace(',', '.')
    try: return float(cleaned)
    except ValueError: return 0.0

def is_valid_tender(tender):
    # 1. Проверка этапа
    if ALLOWED_STAGE not in str(tender.get("stage", "")).lower(): return False
    # 2. Проверка закона
    if not any(l in str(tender.get("law", "")).lower() for l in ALLOWED_LAWS): return False
    # 3. Проверка способа
    if not any(m in str(tender.get("method", "")).lower() for m in ALLOWED_METHODS): return False
    # 4. Проверка цены
    price = parse_price(tender.get("price", 0))
    if not (MIN_PRICE <= price <= MAX_PRICE): return False
    # 5. Проверка исключения регионов
    if any(keyword in str(tender.get("region", "")).lower() for keyword in EXCLUDED_REGIONS): return False
    # 6. Проверка отраслей / ОКПД2
    text_to_search = f'{tender.get("title", "")} {tender.get("industry", "")} {tender.get("okpd2", "")}'.lower()
    if not any(ind in text_to_search for ind in ALLOWED_INDUSTRIES): return False
    return True

def send_to_telegram(tender):
    text = (
        f"🔔 *Новый целевой тендер!*\n\n"
        f"📦 *Название:* {tender.get('title', 'Не указано')}\n"
        f"💰 *Сумма:* {tender.get('price', 'Не указана')} руб.\n"
        f"📍 *Регион:* {tender.get('region', 'Не указан')}\n"
        f"📋 *Закон:* {tender.get('law', '—')} | *Способ:* {tender.get('method', '—')}\n"
        f"🏢 *Заказчик:* {tender.get('customer', 'Не указан')}\n"
        f"🔢 *ОКПД2:* {tender.get('okpd2', 'Не указан')}\n\n"
        f"🔗 [Перейти к тендеру]({tender.get('link', '#')})"
    )
    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
        return res.status_code == 200
    except: return False

def check_and_notify_tenders(tenders_list):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Ошибка: Не настроены токены Telegram.")
        return
    sent_tenders = load_sent_tenders()
    new_sent_count = 0
    for tender in tenders_list:
        tender_id = str(tender.get('id', tender.get('link', '')))
        if not tender_id or tender_id in sent_tenders: continue
        if is_valid_tender(tender):
            if send_to_telegram(tender):
                sent_tenders.add(tender_id)
                new_sent_count += 1
    if new_sent_count > 0: save_sent_tenders(sent_tenders)
    print(f"📊 Отправлено новых тендеров: {new_sent_count}")
