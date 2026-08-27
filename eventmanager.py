import streamlit as st
import requests
from bs4 import BeautifulSoup
import hashlib
import json
import os
import re
import time
import html
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

# ==========================================
# 1. CONFIGURATION & STYLE
# ==========================================
st.set_page_config(page_title="Agenda Étudiant Nancy", layout="wide")

st.markdown("""
<style>
    .event-card {
        background-color: white;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        display: flex;
        justify-content: space-between;
        height: 250px;
        overflow: hidden;
        transition: transform 0.2s;
    }
    .event-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        border-color: #bbb;
    }
    .content-section { flex: 1; padding: 15px; display: flex; flex-direction: column; justify-content: space-between; min-width: 0; }
    .image-section { width: 240px; min-width: 240px; background-color: #f4f4f4; display: flex; align-items: center; justify-content: center; overflow: hidden; }
    .event-img { width: 100%; height: 100%; object-fit: cover; object-position: center top; }
    .tag { font-size: 0.65em; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; display: inline-block; padding: 4px 8px; border-radius: 4px; background-color: #f1f3f5; color: #555; margin-bottom: 8px; margin-right: 5px; }
    .source-badge { font-size: 0.65em; font-weight: 800; text-transform: uppercase; padding: 4px 8px; border-radius: 4px; color: white; margin-bottom: 8px; display: inline-block; }
    .title { font-size: 1.15em; font-weight: 700; margin-bottom: 5px; color: #222; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
    .info-row { display: flex; align-items: center; margin-top: 5px; font-size: 0.9em; color: #666; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .icon { margin-right: 6px; font-size: 1.1em; opacity: 0.7; }
    div.stButton > button { width: 100%; border-radius: 6px; font-size: 0.9em; padding: 0.4rem; border: 1px solid #ddd; }
</style>
""", unsafe_allow_html=True)

# Couleurs
TYPE_COLORS = {
    "EXPOSITION": "#FFAD33", "CONCERT": "#E74C3C", "SPECTACLE": "#E74C3C",
    "SÉMINAIRE": "#3498DB", "CONFÉRENCE": "#3498DB", "ATELIER": "#2ECC71",
    "SPORT": "#9B59B6", "FORMATION": "#9B59B6", "AFTERWORK": "#E67E22", 
    "SCIENCES": "#1ABC9C", "MEETUP": "#F64060", "ALS": "#2C3E50",
    "MUSEUM": "#00A896", # Bleu d'eau pour l'Aquarium
    "MEDEF": "#154360", "LORIA": "#6C3483", "ENACT": "#D35400",
    "DEFAULT": "#95A5A6"
}

# Mapping global des mois (Pour conversion en chiffres)
MONTHS_MAP = {
    'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04', 'mai': '05', 'juin': '06',
    'juillet': '07', 'août': '08', 'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12',
    'janv': '01', 'févr': '02', 'avr': '04', 'juil': '07', 'sept': '09', 'oct': '10', 'nov': '11', 'déc': '12',
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
}

# ==========================================
# 2. FONCTIONS UTILITAIRES & NETTOYAGE
# ==========================================
DB_FILE = 'eventdata.json'
CONFIG_FILE = 'config.json'
SCRAPE_ERRORS = []  # réinitialisée à chaque rerun Streamlit
ALL_SOURCES = ["Factuel", "Pépite", "Sciences", "Meetup", "ALS", "Museum", "MEDEF", "LORIA", "ENACT"]
SOURCE_ICONS = {
    "Factuel": "📡", "Pépite": "🚀", "Sciences": "🔬", "Meetup": "🍻", "ALS": "🏛️", "Museum": "🐠",
    "MEDEF": "💼", "LORIA": "🔬", "ENACT": "🤖"
}

def load_config():
    if not os.path.exists(CONFIG_FILE): return {"sources_actives": ALL_SOURCES.copy()}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            cfg.setdefault("sources_actives", ALL_SOURCES.copy())
            return cfg
    except: return {"sources_actives": ALL_SOURCES.copy()}

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: 
            data = json.load(f)
            unique_data = {e['id']: e for e in data}
            return list(unique_data.values())
    except: return []

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def auto_clean_old_events():
    """Supprime automatiquement les événements passés de plus de 7 jours."""
    db = load_db()
    if not db: return 0
    today = datetime.now().date()
    cutoff_date = today - timedelta(days=7) 
    new_db = []
    removed_count = 0
    for evt in db:
        d_str = evt.get('date_sort', '2099-12-31')
        try:
            if d_str.startswith("2099"):
                new_db.append(evt)
                continue
            evt_date = datetime.strptime(d_str, "%Y-%m-%d").date()
            if evt_date >= cutoff_date: new_db.append(evt)
            else: removed_count += 1
        except: new_db.append(evt)
    if removed_count > 0: save_db(new_db)
    return removed_count

def update_status(event_id, new_status):
    data = load_db()
    for event in data:
        if event['id'] == event_id:
            event['statut'] = new_status
            break
    save_db(data)

def clean_text(text):
    if not text: return ""
    s = str(text)
    s = re.sub(r'<[^>]*>', '', s)
    s = " ".join(s.split())
    return html.escape(s)

def fix_img_url(url):
    if not url: return ""
    if url.startswith('/'): url = "https://factuel.univ-lorraine.fr" + url
    return re.sub(r'-\d+x\d+(?=\.[a-zA-Z]{3,4}$)', '', url)

def extract_sortable_date(date_text):
    if not date_text: return "2099-12-31"
    if re.match(r'\d{4}-\d{2}-\d{2}', date_text): return date_text[:10]
    match_num = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_text)
    if match_num:
        d, m, y = match_num.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return "2099-12-31"

def _to_24h(h, m, ampm):
    h, m = int(h), int(m or 0)
    if ampm == 'pm' and h != 12: h += 12
    if ampm == 'am' and h == 12: h = 0
    return h, m

def _valid_hm(h, m):
    return h is not None and 0 <= h <= 23 and 0 <= m <= 59

def _pack_times(h1, m1, h2, m2):
    """Valide les composantes horaires ; renvoie None si le début est invalide, ignore une fin invalide."""
    if not _valid_hm(h1, m1): return None
    if h2 is not None and not _valid_hm(h2, m2): h2, m2 = None, None
    return (h1, m1, h2, m2)

def _extract_times(txt):
    """(h1, m1, h2, m2) / (h1, m1, None, None) / None depuis un texte de date libre (fr, anglais am-pm, 24h)."""
    if not txt: return None
    t = txt.lower()
    ampm = re.findall(r'(\d{1,2})(?::(\d{2}))?\s*\b(am|pm)\b', t)
    if ampm:
        h1, m1 = _to_24h(*ampm[0])
        if len(ampm) > 1:
            h2, m2 = _to_24h(*ampm[1])
            return _pack_times(h1, m1, h2, m2)
        return _pack_times(h1, m1, None, None)
    fr = re.findall(r'(\d{1,2})\s*h\s*(\d{2})?', t)
    if fr:
        h1, m1 = int(fr[0][0]), int(fr[0][1] or 0)
        if len(fr) > 1:
            return _pack_times(h1, m1, int(fr[1][0]), int(fr[1][1] or 0))
        return _pack_times(h1, m1, None, None)
    hm = re.findall(r'(\d{1,2}):(\d{2})', t)
    if hm:
        h1, m1 = int(hm[0][0]), int(hm[0][1])
        if len(hm) > 1:
            return _pack_times(h1, m1, int(hm[1][0]), int(hm[1][1]))
        return _pack_times(h1, m1, None, None)
    return None

def normalize_display_date(dates_display, date_sort):
    """Uniformise l'affichage de toutes les sources :
    'JJ/MM/AAAA', 'JJ/MM/AAAA | HHhMM' ou 'JJ/MM/AAAA | HHhMM - HHhMM'.
    Si la date de tri est inconnue (2099) ou absente, on renvoie le texte d'origine nettoyé."""
    txt = (dates_display or "").strip()
    if not (date_sort and re.match(r'\d{4}-\d{2}-\d{2}$', date_sort)) or date_sort.startswith('2099'):
        return txt or "Date à confirmer"
    try:
        base = datetime.strptime(date_sort, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return txt or "Date à confirmer"
    times = _extract_times(txt)
    if not times:
        return base
    h1, m1, h2, m2 = times
    if h2 is not None:
        return f"{base} | {h1:02d}h{m1:02d} - {h2:02d}h{m2:02d}"
    return f"{base} | {h1:02d}h{m1:02d}"

def save_new_events(new_events_list):
    if not new_events_list: return 0
    db = load_db()
    existing_ids = {e['id'] for e in db}
    count = 0
    for evt in new_events_list:
        if evt['id'] not in existing_ids:
            evt['date_ajout'] = str(datetime.now().date())
            evt['dates_display'] = normalize_display_date(evt.get('dates_display', ''), evt.get('date_sort', ''))
            db.append(evt)
            existing_ids.add(evt['id'])
            count += 1
    if count > 0: save_db(db)
    return count

# ==========================================
# 2b. AJOUT AU CALENDRIER (Google Calendar)
# ==========================================
def parse_event_time(event):
    """Retourne (debut, fin, journee_entiere) déduits de date_sort + dates_display, ou None si date inconnue."""
    date_sort = event.get('date_sort', '2099-12-31')
    if not date_sort or date_sort.startswith('2099'): return None
    try:
        base_date = datetime.strptime(date_sort, "%Y-%m-%d")
    except: return None
    times = _extract_times(event.get('dates_display', ''))
    if times:
        h1, mi1, h2, mi2 = times
        start = base_date.replace(hour=h1, minute=mi1)
        if h2 is not None:
            end = base_date.replace(hour=h2, minute=mi2)
            if end <= start: end = start + timedelta(hours=2)
        else:
            end = start + timedelta(hours=2)
        return start, end, False
    return base_date, base_date + timedelta(days=1), True

def google_calendar_url(event):
    parsed = parse_event_time(event)
    if not parsed: return None
    start, end, all_day = parsed
    if all_day:
        dates = f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
    else:
        dates = f"{start.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}"
    params = {
        "action": "TEMPLATE",
        "text": event.get('titre', ''),
        "dates": dates,
        "details": event.get('url', ''),
        "location": event.get('lieu', ''),
    }
    return "https://www.google.com/calendar/render?" + urlencode(params)

# ==========================================
# 3. SCRAPERS
# ==========================================
def fetch_factuel_page(page_index):
    if page_index == 0: url = "https://factuel.univ-lorraine.fr/agenda/"
    else: url = f"https://factuel.univ-lorraine.fr/agenda/page/{page_index + 1}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, 'html.parser')
        articles = soup.select('.post-item, .views-row, article.post')
        if not articles: return []
        events = []
        for a in articles:
            try:
                link = a.find('a', class_='full-card-link') or a.select_one('h3 a')
                if not link: continue
                url_evt = link['href']
                if not url_evt.startswith('http'): url_evt = "https://factuel.univ-lorraine.fr" + url_evt
                title = clean_text(a.select_one('h3, h2').get_text()) if a.select_one('h3, h2') else "Sans titre"
                img_tag = a.select_one('img')
                img_url = ""
                if img_tag:
                    # Le plugin de lazy-load met un GIF transparent en `src` et l'image réelle dans `data-src-img`.
                    src = img_tag.get('data-src-img') or img_tag.get('data-src') or img_tag.get('src') or ""
                    if src.startswith('data:'): src = ""
                    img_url = fix_img_url(src)
                type_tag = a.select_one('.type_evenements div, .field-name-field-type-evenement')
                evt_type = clean_text(type_tag.get_text()).upper() if type_tag else "AGENDA"
                lieu = clean_text(a.select_one('.lieu').get_text()) if a.select_one('.lieu') else ""
                date_txt = "Date à confirmer"
                if a.select_one('.evenement.plusieurs-jours'):
                    date_txt = clean_text(a.select_one('.evenement.plusieurs-jours').get_text()).replace("Du", "Du ").replace("Au", " au ")
                elif a.select_one('.evenement.meme-jour'):
                    date_txt = clean_text(a.select_one('.evenement.meme-jour').get_text()).replace("|", " | ")
                events.append({
                    "id": hashlib.md5(url_evt.encode()).hexdigest(),
                    "source": "FACTUEL", "type": evt_type, "titre": title, "lieu": lieu,
                    "dates_display": date_txt, "date_sort": extract_sortable_date(date_txt),
                    "image": img_url, "url": url_evt, "reservation": bool(a.select_one('.inscription')), "statut": "nouveau"
                })
            except: continue
        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"Factuel (page {page_index+1}) : {e}")
        return []

def fetch_pepite_page(page_index):
    url = f"https://pepite-peel.pepitizy.fr/fr/pepites/events/pepite?page={page_index + 1}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, 'html.parser')
        titles_h4 = soup.select('h4')
        if not titles_h4: return []
        events = []
        for h4 in titles_h4:
            try:
                link_tag = h4.find('a')
                if not link_tag: continue
                url_evt = link_tag['href']
                if not url_evt.startswith('http'): url_evt = "https://pepite-peel.pepitizy.fr" + url_evt
                title = clean_text(link_tag.get_text())
                container = h4.find_parent('div')
                if not container: continue
                parent_block = container.parent
                img_url = "https://pepite-peel.pepitizy.fr/assets/frontend/pepite/logo/pepitizy.png"
                thumb_div = parent_block.select_one('.thumb') if parent_block else container.select_one('.thumb')
                if thumb_div and 'style' in thumb_div.attrs:
                    m = re.search(r'url\([\'"]?([^\'"\)]+)[\'"]?\)', thumb_div['style'])
                    if m:
                        found_url = m.group(1)
                        if not found_url.startswith('http'): found_url = "https://pepite-peel.pepitizy.fr" + found_url
                        img_url = found_url
                elif container.select_one('img'):
                    src = container.select_one('img').get('src')
                    if src and "logo" not in src: img_url = src
                card_text = parent_block.get_text(" ", strip=True) if parent_block else container.get_text(" ", strip=True)
                date_txt = "Date à voir"
                date_match = re.search(r'(\d{1,2})\s+([a-zéû]+)\s+(\d{4})', card_text.lower())
                if date_match:
                    day, month_str, year = date_match.groups()
                    month_num = MONTHS_MAP.get(month_str, '01')
                    date_base = f"{day.zfill(2)}/{month_num}/{year}"
                    time_match = re.search(r'de\s+(\d{1,2}h\d{2})\s+à\s+(\d{1,2}h\d{2})', card_text.lower())
                    if time_match: date_txt = f"{date_base} | {time_match.group(1)} - {time_match.group(2)}"
                    else: date_txt = date_base
                lieu = "Nancy / Metz"
                if "Lieu" in card_text:
                    parts = card_text.split("Lieu")
                    if len(parts) > 1: lieu = parts[1].split(":")[1].strip().split(')')[0] + ")"
                events.append({
                    "id": hashlib.md5(url_evt.encode()).hexdigest(),
                    "source": "PEPITE", "type": "ENTREPRENEURIAT", "titre": title, "lieu": clean_text(lieu)[:45],
                    "dates_display": date_txt, "date_sort": extract_sortable_date(date_txt),
                    "image": img_url, "url": url_evt, "reservation": True, "statut": "nouveau"
                })
            except: continue
        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"Pépite (page {page_index+1}) : {e}")
        return []

def fetch_sciences_societe():
    url = "https://conferences-sciences-et-societe.univ-lorraine.fr/agenda/"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'conférences\s+à\s+venir', re.I))
        if not headers: return []
        start_node = headers[0]
        events = []
        current = start_node.find_next_sibling()
        while current:
            if current.name in ['h2', 'h3', 'h4'] and 'passées' in current.get_text().lower(): break
            text_content = current.get_text(" ", strip=True)
            date_match = re.search(r'(\d{1,2})\s+([a-zéû]+)\s+(\d{4})', text_content.lower())
            if date_match:
                day, month_str, year = date_match.groups()
                month_num = MONTHS_MAP.get(month_str, '01')
                date_txt = f"{day.zfill(2)}/{month_num}/{year}"
                link = current.find('a')
                if link:
                    titre = link.get_text(strip=True)
                    url_evt = link['href']
                    if not url_evt.startswith('http'): url_evt = "https://conferences-sciences-et-societe.univ-lorraine.fr" + url_evt
                else:
                    lines = [l for l in current.stripped_strings if len(l) > 10]
                    titre = lines[1] if len(lines) > 1 else "Conférence"
                    url_evt = url
                # La page agenda ne contient pas d'image par événement, on utilise le logo du site (les cartes n'ont pas de <img>)
                img_url = "https://conferences-sciences-et-societe.univ-lorraine.fr/wp-content/uploads/2021/08/logo-science-societe.png"
                if current.select_one('img'): img_url = current.select_one('img').get('src')
                events.append({
                    "id": hashlib.md5((date_txt + titre).encode()).hexdigest(),
                    "source": "SCIENCES", "type": "CONFÉRENCE", "titre": clean_text(titre), "lieu": "Nancy",
                    "dates_display": date_txt, "date_sort": extract_sortable_date(date_txt),
                    "image": img_url, "url": url_evt, "reservation": False, "statut": "nouveau"
                })
            current = current.find_next_sibling()
        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"Sciences & Société : {e}")
        return []

def fetch_meetup_search():
    url = "https://www.meetup.com/find/?location=fr--Nancy&source=EVENTS&distance=tenMiles"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        event_links = soup.find_all('a', href=re.compile(r'/events/\d+'))
        events = []
        seen_urls = set()
        current_year = datetime.now().year
        for link in event_links:
            url_evt = link['href']
            if not url_evt.startswith('http'): url_evt = "https://www.meetup.com" + url_evt
            url_clean = url_evt.split('?')[0]
            if url_clean in seen_urls: continue
            seen_urls.add(url_clean)
            card = link.find_parent('div', class_='flex') or link.find_parent('div', attrs={'data-testid': 'category-card'}) or link.parent.parent
            if not card: continue
            title_tag = card.find(['h2', 'h3'])
            titre = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)
            if not titre: continue
            date_display = "Date à voir sur le site"
            sort_date = "2099-12-31"
            time_tag = card.find('time')
            if time_tag and time_tag.has_attr('datetime'):
                raw_dt = time_tag['datetime']
                try:
                    if '[' in raw_dt: raw_dt = raw_dt.split('[')[0]
                    # Meetup renvoie des chiffres en UTC malgré un suffixe de fuseau local (ex: "17:00:00+02:00[Europe/Paris]" affiche pourtant "19:00" sur le site) : on ignore l'offset fourni et on traite les chiffres bruts comme de l'UTC.
                    raw_naive = re.sub(r'(Z|[+-]\d{2}:\d{2})$', '', raw_dt)
                    dt_utc = datetime.fromisoformat(raw_naive).replace(tzinfo=ZoneInfo("UTC"))
                    dt = dt_utc.astimezone(ZoneInfo("Europe/Paris"))
                    day = dt.strftime("%d")
                    month = dt.strftime("%m")
                    year = dt.strftime("%Y")
                    hour = dt.strftime("%H:%M")
                    date_display = f"{day}/{month}/{year} | {hour}"
                    sort_date = f"{year}-{month}-{day}"
                except: date_display = time_tag.get_text(strip=True)
            elif time_tag: date_display = time_tag.get_text(strip=True)
            else:
                card_text = card.get_text(" | ", strip=True).lower()
                date_match = re.search(r'(\d{1,2})\s+([a-zéû\.]+)', card_text)
                if date_match:
                    d, m_raw = date_match.groups()
                    m_clean = m_raw.replace('.', '')
                    m_num = MONTHS_MAP.get(m_clean)
                    if m_num:
                        y = current_year
                        if int(m_num) < datetime.now().month: y += 1
                        sort_date = f"{y}-{m_num}-{d.zfill(2)}"
                        date_display = f"{d.zfill(2)}/{m_num}/{y}"
            img_tag = card.find('img', attrs={'data-nimg': '1'}) or card.find('img', class_='object-cover')
            image_url = "https://secure.meetupstatic.com/photos/event/9/e/6/6/600_456280550.jpeg"
            if img_tag:
                src = img_tag.get('src')
                srcset = img_tag.get('srcset')
                if srcset: src = srcset.split(',')[-1].strip().split(' ')[0]
                if src: image_url = src
            lieu = "Nancy"
            events.append({
                "id": hashlib.md5(url_clean.encode()).hexdigest(),
                "source": "MEETUP", "type": "MEETUP", "titre": clean_text(titre), "lieu": clean_text(lieu),
                "dates_display": clean_text(date_display), "date_sort": sort_date,
                "image": image_url, "url": url_clean, "reservation": True, "statut": "nouveau"
            })
        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"Meetup : {e}")
        return []

def fetch_als():
    url = "https://als.univ-lorraine.fr/seances-futures/"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        articles = soup.find_all('article')
        if not articles: articles = soup.select('.et_pb_module')
        events = []
        for a in articles:
            title_node = a.find(['h1', 'h2', 'h3', 'h4'])
            if not title_node: continue
            title_text = title_node.get_text(strip=True)
            date_match = re.search(r'Séance du\s+(\d{2}/\d{2}/\d{4})', title_text, re.I)
            if date_match:
                date_full = date_match.group(1)
                full_text = a.get_text(" ", strip=True)
                real_title = full_text.replace(title_text, "").replace("Lire la suite", "").strip()
                if len(real_title) > 150: real_title = real_title[:150] + "..."
                link = a.find('a')
                url_evt = link['href'] if link else url
                # Le lazy-load met un SVG placeholder en `src`, l'image réelle est dans `data-src`
                img_tag = a.select_one('img')
                img_url = "https://als.univ-lorraine.fr/wp-content/uploads/2023/12/logo-ALS-214.png"
                if img_tag:
                    src = img_tag.get('data-src') or img_tag.get('src') or ""
                    if src and not src.startswith('data:'): img_url = src
                events.append({
                    "id": hashlib.md5((date_full + real_title).encode()).hexdigest(),
                    "source": "ALS", "type": "CONFÉRENCE", "titre": clean_text(real_title), 
                    "lieu": "Académie Lorraine des Sciences",
                    "dates_display": date_full, "date_sort": extract_sortable_date(date_full),
                    "image": img_url, "url": url_evt, "reservation": False, "statut": "nouveau"
                })
        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"ALS : {e}")
        return []

# --- 6. MUSEUM-AQUARIUM (NOUVEAU) ---
def fetch_museum_aquarium():
    url = "https://www.museumaquariumdenancy.eu/agenda/toutes-les-dates"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Sélecteurs génériques pour cartes ou listes
        # Basé sur l'analyse, ils utilisent souvent des balises <article> ou des classes type .views-row ou .card
        # On va chercher large: tous les liens qui contiennent du texte et une image ou une date
        
        # Astuce : On cherche les blocs qui contiennent "Atelier" ou "Conférence"
        # Mais on veut exclure "Atelier".
        
        # On itère sur les éléments de liste potentiels
        items = soup.find_all(['article', 'li', 'div'], class_=re.compile(r'item|card|row'))
        
        # Si pas trouvé, on cherche les liens directs qui semblent être des events
        if not items or len(items) < 3:
             items = soup.find_all('a', href=True)

        events = []
        seen_ids = set()

        for item in items:
            text = item.get_text(" ", strip=True)
            
            # FILTRE ANTI-ATELIER (Le cœur de votre demande)
            if "Atelier" in text or "atelier" in text:
                continue # On zappe !
            
            # On cherche une date (Format : Mercredi 14 janvier 2026)
            date_match = re.search(r'(\d{1,2})\s+([a-zéû]+)\s+(\d{4})', text.lower())
            if not date_match: continue # Pas de date = pas un event
            
            day, month_str, year = date_match.groups()
            month_num = MONTHS_MAP.get(month_str)
            if not month_num: continue
            
            sort_date = f"{year}-{month_num}-{day.zfill(2)}"
            date_display = f"{day.zfill(2)}/{month_num}/{year}"
            
            # Titre : souvent le texte le plus long ou dans un h tag
            title_tag = item.find(['h2', 'h3', 'h4', 'strong'])
            if title_tag:
                titre = title_tag.get_text(strip=True)
            else:
                # Sinon on prend le début du texte
                titre = text.split(date_match.group(0))[0].strip()
                if len(titre) > 80: titre = titre[:80] + "..."
            
            # Si le titre est vide ou générique, on ignore
            if not titre or len(titre) < 3: continue

            # Lien
            if item.name == 'a':
                url_evt = item['href']
            else:
                link = item.find('a')
                url_evt = link['href'] if link else url
            
            if not url_evt.startswith('http'): 
                url_evt = "https://www.museumaquariumdenancy.eu" + url_evt
            
            # Dédoublonnage
            if url_evt in seen_ids: continue
            seen_ids.add(url_evt)

            # Image
            img_url = "https://www.museumaquariumdenancy.eu/typo3conf/ext/man_site/Resources/Public/Images/logo-man.svg" # Fallback
            img = item.find('img')
            if img:
                src = img.get('src')
                if src:
                    img_url = src if src.startswith('http') else "https://www.museumaquariumdenancy.eu" + src

            events.append({
                "id": hashlib.md5(url_evt.encode()).hexdigest(),
                "source": "MUSEUM", "type": "EXPO/CONF", "titre": clean_text(titre), 
                "lieu": "Muséum-Aquarium de Nancy",
                "dates_display": date_display, "date_sort": sort_date,
                "image": img_url, "url": url_evt, "reservation": False, "statut": "nouveau"
            })

        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"Muséum-Aquarium : {e}")
        return []


# --- 7. MEDEF MEURTHE-ET-MOSELLE ---
def fetch_medef_54():
    url = "https://www.medef-meurthe-moselle.fr/fr/agenda"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.Grid-item')
        events = []
        for item in items:
            try:
                if 'isPast' in (item.get('class') or []): continue
                link = item.select_one('a.globalLink')
                if not link: continue
                url_evt = link['href']
                if not url_evt.startswith('http'): url_evt = "https://www.medef-meurthe-moselle.fr" + url_evt
                title_tag = item.select_one('.Box-info-title')
                date_tag = item.select_one('.Box-date')
                if not title_tag or not date_tag: continue
                date_match = re.search(r'(\d{1,2})\s+([^\d\s]+)\s+(\d{4})', date_tag.get_text(' ', strip=True).lower())
                if not date_match: continue
                day, month_str, year = date_match.groups()
                month_num = MONTHS_MAP.get(month_str.rstrip('.'))
                if not month_num: continue
                cover = item.select_one('.Post-cover')
                img_url = ""
                if cover and cover.get('style'):
                    m = re.search(r"url\(['\"]?([^'\"\)]+)['\"]?\)", cover['style'])
                    if m and 'default.svg' not in m.group(1):
                        src = m.group(1)
                        img_url = src if src.startswith('http') else "https://www.medef-meurthe-moselle.fr" + src
                events.append({
                    "id": hashlib.md5(url_evt.encode()).hexdigest(),
                    "source": "MEDEF", "type": "ENTREPRENEURIAT", "titre": clean_text(title_tag.get_text()), "lieu": "MEDEF Meurthe-et-Moselle",
                    "dates_display": f"{day.zfill(2)}/{month_num}/{year}", "date_sort": f"{year}-{month_num}-{day.zfill(2)}",
                    "image": img_url, "url": url_evt, "reservation": False, "statut": "nouveau"
                })
            except: continue
        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"MEDEF 54 : {e}")
        return []

# --- 8. AGENDAS "THE EVENTS CALENDAR" (LORIA / ENACT) ---
def fetch_tribe_events(url, source, evt_type, lieu_default):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        articles = soup.select('article.tribe-events-calendar-list__event')
        events = []
        for a in articles:
            try:
                link = a.select_one('.tribe-events-calendar-list__event-title-link')
                time_tag = a.select_one('time.tribe-events-calendar-list__event-datetime')
                if not link or not time_tag or not time_tag.get('datetime'): continue
                url_evt = link['href']
                venue = a.select_one('.tribe-events-calendar-list__event-venue-address')
                lieu = clean_text(venue.get_text()) if venue else lieu_default
                img_tag = a.select_one('img')
                img_url = img_tag.get('src') if img_tag and img_tag.get('src') else ""
                events.append({
                    "id": hashlib.md5(url_evt.encode()).hexdigest(),
                    "source": source, "type": evt_type, "titre": clean_text(link.get_text()), "lieu": lieu,
                    "dates_display": time_tag.get_text(' ', strip=True).replace('@', '|'), "date_sort": time_tag['datetime'][:10],
                    "image": img_url, "url": url_evt, "reservation": False, "statut": "nouveau"
                })
            except: continue
        return events
    except Exception as e:
        SCRAPE_ERRORS.append(f"{source} : {e}")
        return []

def fetch_loria():
    return fetch_tribe_events("https://www.loria.fr/events/", "LORIA", "RECHERCHE", "LORIA, Nancy")

def fetch_enact():
    return fetch_tribe_events("https://cluster-ia-enact.ai/events/", "ENACT", "INNOVATION IA", "Grand Est")


# --- ROUTEUR ---
def scan_source(source_name):
    if source_name == "Factuel":
        evts = []; bar = st.progress(0)
        for i in range(10): bar.progress(i/10); evts.extend(fetch_factuel_page(i) or [])
        bar.empty(); return evts
    elif source_name == "Pépite":
        evts = []; bar = st.progress(0)
        for i in range(5): bar.progress(i/5); evts.extend(fetch_pepite_page(i) or [])
        bar.empty(); return evts
    elif source_name == "Sciences": return fetch_sciences_societe()
    elif source_name == "Meetup": return fetch_meetup_search()
    elif source_name == "ALS": return fetch_als()
    elif source_name == "Museum": return fetch_museum_aquarium() # Nouvelle entrée
    elif source_name == "MEDEF": return fetch_medef_54()
    elif source_name == "LORIA": return fetch_loria()
    elif source_name == "ENACT": return fetch_enact()
    return []

# ==========================================
# 4. RENDU
# ==========================================
def render_card(event):
    c_type = event.get('type', 'EVENT')
    source = event.get('source', 'AUTRE')
    color = TYPE_COLORS.get(source, TYPE_COLORS['DEFAULT'])
    if source == 'FACTUEL': color = TYPE_COLORS.get(c_type, TYPE_COLORS['DEFAULT'])
    
    titre = event.get('titre', '')
    lieu = event.get('lieu', '')
    date = normalize_display_date(event.get('dates_display', ''), event.get('date_sort', ''))
    url = event.get('url', '#')
    img = event.get('image', '')
    
    badge_color = "#95a5a6"
    if source == "FACTUEL": badge_color = "#e74c3c"
    elif source == "PEPITE": badge_color = "#8e44ad"
    elif source == "SCIENCES": badge_color = "#16a085"
    elif source == "MEETUP": badge_color = "#F64060"
    elif source == "ALS": badge_color = "#2c3e50"
    elif source == "MUSEUM": badge_color = "#00A896"
    elif source == "MEDEF": badge_color = "#154360"
    elif source == "LORIA": badge_color = "#6C3483"
    elif source == "ENACT": badge_color = "#D35400"
    
    img_html = f'<img src="{img}" class="event-img" onerror="this.onerror=null;this.src=\'https://placehold.co/240x250/eee/999?text=Image\';">' if img else '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:3em;">📅</div>'
    resa = '<div class="info-row" style="color:#e67e22; font-weight:600;"><span class="icon">🎫</span>Sur réservation</div>' if event.get('reservation') else ""

    html_code = f"""
<div class="event-card" style="border-left: 6px solid {color};">
<div class="content-section">
<div>
<div style="display:flex; justify-content:space-between;">
    <span class="tag" style="color:{color}; background:{color}15;">{c_type}</span>
    <span class="source-badge" style="background-color:{badge_color}; font-size:0.5em;">{source}</span>
</div>
<div class="title"><a href="{url}" target="_blank" style="text-decoration:none; color:inherit;" title="{titre}">{titre}</a></div>
</div>
<div>
<div class="info-row"><span class="icon">📍</span>{lieu}</div>
<div class="info-row"><span class="icon">📅</span>{date}</div>
{resa}
</div>
</div>
<div class="image-section">{img_html}</div>
</div>
"""
    st.markdown(html_code, unsafe_allow_html=True)

# ==========================================
# 5. APP PRINCIPALE
# ==========================================
st.title("🎓 Agenda Unifié : Lorraine")

# -- AUTO-NETTOYAGE AU DÉMARRAGE --
cleaned_count = auto_clean_old_events()
if cleaned_count > 0:
    st.toast(f"🧹 Nettoyage : {cleaned_count} événements passés supprimés.", icon="🗑️")

config = load_config()

with st.expander("⚙️ Sources actives (utilisées par « Scanner Tout »)"):
    saved_actives = [s for s in config.get("sources_actives", ALL_SOURCES) if s in ALL_SOURCES]
    actives = st.multiselect("Sources à scanner", ALL_SOURCES, default=saved_actives, label_visibility="collapsed")
    if actives != config.get("sources_actives"):
        config["sources_actives"] = actives
        save_config(config)

c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.caption("Centralisateur : Université, Pépite, Sciences, Meetup, ALS, Muséum & Entrepreneuriat (MEDEF, LORIA, ENACT).")
with c2:
    if st.button("🌍 Scanner Tout", type="primary", use_container_width=True):
        actives = config.get("sources_actives", ALL_SOURCES)
        if not actives:
            st.warning("Aucune source active — choisis-en dans « ⚙️ Sources actives » ci-dessus.")
        else:
            with st.status("Scan général...", expanded=True) as status:
                evts = []
                for s in actives:
                    st.write(f"{SOURCE_ICONS.get(s, '🔎')} {s}..."); evts += scan_source(s)
                n = save_new_events(evts)
                if SCRAPE_ERRORS:
                    status.update(label=f"Terminé avec {len(SCRAPE_ERRORS)} erreur(s)", state="error", expanded=True)
                else:
                    status.update(label="Terminé !", state="complete", expanded=False)
            for err in SCRAPE_ERRORS: st.error(f"⚠️ {err}")
            if n: st.success(f"+{n} events !"); time.sleep(1); st.rerun()
            elif not SCRAPE_ERRORS: st.info("Rien de neuf.")

with c3:
    src = st.selectbox("Source :", ALL_SOURCES, label_visibility="collapsed")
    if st.button(f"Scanner {src}", use_container_width=True):
        with st.spinner(f"Scan {src}..."):
            n = save_new_events(scan_source(src))
        for err in SCRAPE_ERRORS: st.error(f"⚠️ {err}")
        if n: st.success(f"+{n} ajouts !"); time.sleep(1); st.rerun()
        elif not SCRAPE_ERRORS: st.info("À jour.")

st.divider()

events = load_db()
new = [e for e in events if e['statut']=='nouveau']
trash = [e for e in events if e['statut']=='poubelle']

t1, t2 = st.tabs([f"À Trier ({len(new)})", f"Poubelle ({len(trash)})"])

with t1:
    new.sort(key=lambda x: x.get('date_sort', '9999'))
    if new:
        sources_dispo = sorted({e['source'] for e in new})
        f_sources = st.multiselect("Filtrer par source", sources_dispo, default=sources_dispo)
        new = [e for e in new if e['source'] in f_sources]
    if not new: st.info("Vide.")
    for i in range(0, len(new), 2):
        cols = st.columns(2)
        for j in range(2):
            if i+j < len(new):
                e = new[i+j]
                with cols[j]:
                    render_card(e)
                    b1, b2 = st.columns(2)
                    if b1.button("Passer", key=f"d_{e['id']}"): update_status(e['id'], 'poubelle'); st.rerun()
                    gcal_url = google_calendar_url(e)
                    if gcal_url:
                        b2.link_button("🗓️ Google Agenda", gcal_url, use_container_width=True)
                    else:
                        b2.caption("⚠️ Date inconnue")

with t2:
    st.caption("Les événements ici sont supprimés automatiquement 7 jours après leur date.")
    for i in range(0, len(trash), 2):
        cols = st.columns(2)
        for j in range(2):
            if i+j < len(trash):
                e = trash[i+j]
                with cols[j]:
                    render_card(e)
                    if st.button("Restaurer", key=f"rs_{e['id']}"): update_status(e['id'], 'nouveau'); st.rerun()