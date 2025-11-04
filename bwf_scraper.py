# bwf_scraper.py
import io
import os
import textwrap
from datetime import datetime
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont


BWF_CAL_URL = "https://bwfworldtour.bwfbadminton.com/calendar/?cyear=2025&rstate=all"
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
BANNER_PATH = os.path.join(ASSETS_DIR, "banner.png")
QR_PATH = os.path.join(ASSETS_DIR, "qr.png")

# 字体：尽量用系统自带的 DejaVuSans（Render 的容器里一般有）
# 若渲染出现方块，可以把你常用的中文字体文件放到 assets 目录里，然后替换 FONT_PATH。
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def fetch_calendar() -> List[Dict]:
    """
    抓取 BWF World Tour Calendar（简单解析方式，尽量兼容）。
    返回若干场赛事：[{name, level, dates, location, link}...]
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BadMeetBot/1.0; +https://t.me/)"
    }
    resp = requests.get(BWF_CAL_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 经验上，赛事卡片通常会有包含 event / card 的 class；我们容错多找几种可能
    cards = []
    for tag in soup.find_all(["article", "div", "li"], class_=True):
        cls = " ".join(tag.get("class") or [])
        if "event" in cls.lower() or "card" in cls.lower():
            cards.append(tag)

    events = []
    for c in cards:
        # 名称
        name = (c.find(["h3", "h2"]) or c.find("a") or c).get_text(strip=True)

        # 等级（粗匹配：SUPER 1000 / 750 / 500）
        text_all = c.get_text(" ", strip=True).upper()
        level = ""
        for lv in ["SUPER 1000", "SUPER 750", "SUPER 500", "SUPER1000", "SUPER750", "SUPER500"]:
            if lv in text_all:
                level = lv.replace("SUPER", "Super ")
                break

        # 日期（粗匹配，含 2025 或者 dd MMM）
        dates = ""
        for t in c.find_all(["time", "span", "div"]):
            s = t.get_text(" ", strip=True)
            if any(m in s for m in ["2025", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
                if 6 <= len(s) <= 40:
                    dates = s
                    break

        # 地点
        location = ""
        for t in c.find_all(["span", "div", "p"]):
            s = t.get_text(" ", strip=True)
            if any(k in s.lower() for k in ["city", "country"]) or "," in s:
                if 4 <= len(s) <= 60:
                    location = s
                    break

        # 链接
        link_tag = c.find("a", href=True)
        link = link_tag["href"] if link_tag else ""

        # 过滤条件：只留 1000/750/500
        if level and any(x in level for x in ["1000", "750", "500"]):
            events.append({
                "name": name,
                "level": level,
                "dates": dates,
                "location": location,
                "link": link
            })

    # 去重 + 截取前 8 个
    uniq = []
    seen = set()
    for e in events:
        key = (e["name"], e["dates"], e["level"])
        if key not in seen:
            uniq.append(e)
            seen.add(key)

    return uniq[:8] or events[:8]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size=size)
    except Exception:
        # 兜底：使用 PIL 内置字体（不支持中文）
        return ImageFont.load_default()


def draw_calendar_image(events: List[Dict], out_path: str) -> str:
    """
    把赛事列表渲染为 1080x1350 竖版图，顶部贴 banner，底部贴 QR。
    """
    W, H = 1080, 1350
    bg = Image.new("RGB", (W, H), (18, 20, 24))
    draw = ImageDraw.Draw(bg)

    # 贴 banner
    if os.path.exists(BANNER_PATH):
        banner = Image.open(BANNER_PATH).convert("RGBA")
        bw = W
        bh = int(banner.height * (bw / banner.width))
        banner = banner.resize((bw, bh), Image.LANCZOS)
        bg.paste(banner, (0, 0), banner)
        top_y = bh + 24
    else:
        top_y = 40

    # 贴 QR 在右下角
    qr_box = None
    if os.path.exists(QR_PATH):
        qr = Image.open(QR_PATH).convert("RGBA")
        target = 260
        qr = qr.resize((target, target), Image.LANCZOS)
        x = W - target - 32
        y = H - target - 32
        bg.paste(qr, (x, y), qr)
        qr_box = (x, y, x + target, y + target)

    # 标题
    title_font = _load_font(56)
    sub_font = _load_font(30)
    body_font = _load_font(34)

    title = "BWF World Tour — Latest (Super 1000 / 750 / 500)"
    draw.text((36, top_y), title, fill=(255, 255, 255), font=title_font)
    draw.text((36, top_y + 66),
              datetime.now().strftime("Updated: %Y-%m-%d %H:%M"),
              fill=(160, 170, 180), font=sub_font)

    # 内容区域
    cursor_y = top_y + 110
    left = 36
    right = W - 36
    if qr_box:
        right = min(right, qr_box[0] - 24)

    line_gap = 16
    block_gap = 26

    for idx, e in enumerate(events, 1):
        # 每条赛事一个小块
        # 名称（自动换行）
        name_lines = textwrap.wrap(e["name"], width=28)
        lvl = e["level"] or ""
        dates = e["dates"] or ""
        loc = e["location"] or ""

        # 彩色条
        draw.rectangle([left, cursor_y - 8, right, cursor_y - 4], fill=(75, 150, 255))

        for ln in name_lines:
            draw.text((left, cursor_y), ln, fill=(240, 240, 240), font=body_font)
            cursor_y += body_font.size + line_gap

        # 次要信息
        meta = " • ".join([x for x in [lvl, dates, loc] if x])
        draw.text((left, cursor_y), meta, fill=(180, 190, 200), font=sub_font)
        cursor_y += sub_font.size + block_gap

        if cursor_y > H - 340:  # 防止被 QR 遮挡
            break

    # 文件输出
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bg.save(out_path, format="PNG", optimize=True)
    return out_path


def tg_send_photo(token: str, chat_id: str, image_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(image_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": chat_id, "caption": caption}
        resp = requests.post(url, data=data, files=files, timeout=60)
    resp.raise_for_status()
    return resp.json()


def generate_and_send(token: str, chat_id: str) -> str:
    events = fetch_calendar()
    if not events:
        raise RuntimeError("No events parsed from BWF.")

    out_path = os.path.join(os.path.dirname(__file__), "out_bwf.png")
    draw_calendar_image(events, out_path)

    caption = "BWF World Tour 最新赛程（Super 1000/750/500）\n自动生成 · BadMeet"
    tg_send_photo(token, chat_id, out_path, caption=caption)
    return out_path
