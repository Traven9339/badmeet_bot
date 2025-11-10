# main.py
import os
import io
import datetime as dt
from typing import List, Tuple, Optional

import requests
from flask import Flask, request, send_file, jsonify, render_template
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter

app = Flask(__name__)

# --- 环境变量 ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SESSION_SECRET = os.getenv("SESSION_SECRET")

# --- 资源文件路径 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
BANNER_PATH = os.path.join(ASSETS_DIR, "banner.png")
QR_PATH = os.path.join(ASSETS_DIR, "qr.png")

# --- 字体（用系统默认 PIL 内置字体，避免字体缺失。不要求中文排版很美，但可用） ---
try:
    DEFAULT_FONT = ImageFont.truetype("DejaVuSans.ttf", 36)
    SMALL_FONT = ImageFont.truetype("DejaVuSans.ttf", 28)
    TINY_FONT = ImageFont.truetype("DejaVuSans.ttf", 22)
except Exception:
    DEFAULT_FONT = ImageFont.load_default()
    SMALL_FONT = ImageFont.load_default()
    TINY_FONT = ImageFont.load_default()


# --------------------------
# 通用：发 Telegram 文本
# --------------------------
def send_telegram_text(text: str) -> Tuple[bool, str]:
    if not BOT_TOKEN or not CHAT_ID:
        return False, "Missing BOT_TOKEN or CHAT_ID"
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        r = requests.post(url, json=payload, timeout=20)
        ok = r.ok
        return ok, r.text
    except Exception as e:
        return False, str(e)


# --------------------------
# 通用：发 Telegram 图片（用 sendPhoto）
# --------------------------
def send_telegram_photo(img_bytes: bytes, caption: str = "") -> Tuple[bool, str]:
    if not BOT_TOKEN or not CHAT_ID:
        return False, "Missing BOT_TOKEN or CHAT_ID"
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {"photo": ("bwf.png", img_bytes)}
        data = {"chat_id": CHAT_ID, "caption": caption}
        r = requests.post(url, data=data, files=files, timeout=30)
        ok = r.ok
        return ok, r.text
    except Exception as e:
        return False, str(e)


# --------------------------
# 抓取 BWF World Tour 日历（弹性选择器，尽量鲁棒）
# --------------------------
CAL_URL = "https://bwfworldtour.bwfbadminton.com/calendar/"

def fetch_bwf_events(year: int, limit: int = 8) -> List[dict]:
    """
    返回形如：
    [{"name": "...", "dates": "...", "level": "...", "city": "..."}]
    解析尽量容错，避免因官网小改导致完全失败。
    """
    params = {"cyear": year, "rstate": "all"}
    headers = {
        "User-Agent": "Mozilla/5.0 (RenderBot; +https://render.com)"
    }
    events: List[dict] = []
    try:
        resp = requests.get(CAL_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 多种候选选择器，尽量兼容
        candidates = []
        candidates += soup.select(".event-card")                     # 新样式
        candidates += soup.select(".c-card--event, .event")          # 旧/备选
        candidates = candidates[: max(limit * 2, limit + 2)]

        for block in candidates:
            name = None
            dates = None
            level = None
            city = None

            # 名称候选
            for sel in [
                ".event-card__name",
                ".event-card__title",
                ".c-card__title",
                ".event__title",
                "h3",
                "h2",
                "a",
            ]:
                node = block.select_one(sel)
                if node and node.get_text(strip=True):
                    name = node.get_text(strip=True)
                    break

            # 日期候选
            for sel in [
                ".event-card__date",
                ".event__date",
                ".c-card__date",
                ".date",
                ".dates",
                "time",
                "p",
            ]:
                node = block.select_one(sel)
                if node and node.get_text(strip=True):
                    dates = node.get_text(strip=True)
                    break

            # 等级候选
            for sel in [
                ".event-card__level",
                ".event__level",
                ".c-card__tag",
                ".level",
                ".tag",
                "small",
                "span",
            ]:
                node = block.select_one(sel)
                if node and node.get_text(strip=True):
                    level = node.get_text(strip=True)
                    break

            # 城市候选
            for sel in [
                ".event-card__city",
                ".event__city",
                ".c-card__meta",
                ".location",
                ".venue",
                ".city",
            ]:
                node = block.select_one(sel)
                if node and node.get_text(strip=True):
                    city = node.get_text(strip=True)
                    break

            if name:
                events.append(
                    {
                        "name": name,
                        "dates": dates or "",
                        "level": level or "",
                        "city": city or "",
                    }
                )
            if len(events) >= limit:
                break

    except Exception:
        # 静默失败，后面生成图片时会提示“抓取失败”
        pass

    return events


# --------------------------
# 生成 1080x1350 海报图，叠加 banner 与 QR
# --------------------------
def make_poster(events: List[dict], year: int) -> bytes:
    W, H = 1080, 1350  # IG portrait
    bg = Image.new("RGB", (W, H), (18, 18, 22))
    draw = ImageDraw.Draw(bg)

    # 标题栏
    title = f"BWF World Tour {year}"
    sub = dt.datetime.now().strftime("Updated %Y-%m-%d %H:%M")
    draw.text((48, 48), title, font=DEFAULT_FONT, fill=(255, 255, 255))
    draw.text((48, 110), sub, font=SMALL_FONT, fill=(170, 170, 170))

    # 内容卡片区域
    y = 180
    line_gap = 8
    card_gap = 18

    if not events:
        draw.text(
            (48, y),
            "⚠️ 无法从官网取得赛事资料（可能官网结构变更）。",
            font=SMALL_FONT,
            fill=(240, 200, 80),
        )
        y += 48
        draw.text(
            (48, y),
            "你仍可点右上角按钮重试，或稍后再来。",
            font=TINY_FONT,
            fill=(180, 180, 180),
        )
    else:
        for idx, ev in enumerate(events, 1):
            # 简单卡片背景
            card_h = 130
            card = Image.new("RGBA", (W - 96, card_h), (30, 30, 36, 255))
            card = card.filter(ImageFilter.GaussianBlur(0.2))
            bg.paste(card, (48, y), card)

            # 文本
            name = ev.get("name", "").strip()
            dates = ev.get("dates", "").strip()
            city = ev.get("city", "").strip()
            level = ev.get("level", "").strip()

            draw.text((64, y + 16), f"{idx}. {name}", font=SMALL_FONT, fill=(255, 255, 255))
            draw.text(
                (64, y + 16 + 40),
                f"{dates or '-'}  ·  {city or '-'}  ·  {level or '-'}",
                font=TINY_FONT,
                fill=(190, 190, 190),
            )
            y += card_h + card_gap

            if y > H - 340:  # 留出下方 banner + QR 的空间
                break

    # 叠加底部 banner
    try:
        if os.path.exists(BANNER_PATH):
            banner = Image.open(BANNER_PATH).convert("RGBA")
            # 让 banner 等比铺到宽度
            bw = W - 96
            scale = bw / banner.width
            banner = banner.resize((int(banner.width * scale), int(banner.height * scale)), Image.LANCZOS)
            bx = 48
            by = H - banner.height - 48
            bg.paste(banner, (bx, by), banner)
    except Exception:
        pass

    # 叠加右下角 QR
    try:
        if os.path.exists(QR_PATH):
            qr = Image.open(QR_PATH).convert("RGBA")
            q = 260
            qr = qr.resize((q, q), Image.LANCZOS)
            qx = W - q - 48
            qy = H - q - 48
            bg.paste(qr, (qx, qy), qr)
    except Exception:
        pass

    # 输出为 PNG bytes
    out = io.BytesIO()
    bg.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out.read()


# --------------------------
# 路由
# --------------------------
@app.route("/")
def home():
    return "✅ BadMeet Bot is running on Render!"

@app.route("/send")
def send_message():
    msg = request.args.get("msg", "Hello from Render!")
    ok, resp = send_telegram_text(msg)
    status = "✅ OK" if ok else "❌ FAIL"
    return f"{status}\n{resp}", (200 if ok else 500)

@app.route("/health")
def health():
    return jsonify(ok=True, time=str(dt.datetime.utcnow()))

@app.route("/bwf")
def bwf_page():
    """
    自动从 BWF 官网抓取最新数据并生成网页
    """
    try:
        data = fetch_bwf_data()   # 自动抓取最新赛事资料def fetch_bwf_data():
    """
    兜底C：抓取 HTML（直接/镜像），解析出赛事名称列表
    """
    import requests
    from bs4 import BeautifulSoup

    CAL_URL = "https://bwfworldtour.bwfbadminton.com/calendar/"

    # --- 带基础 headers 的请求 ---
    BASE_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://bwfworldtour.bwfbadminton.com/",
        "Cache-Control": "no-cache",
    }

    def get_html(url: str) -> tuple[str, str]:
        """
        返回 (html_text, via)，via 标注走直连还是镜像
        """
        try:
            r = requests.get(url, headers=BASE_HEADERS, timeout=12)
            if r.status_code == 200 and r.text.strip():
                return r.text, "direct"
            else:
                # 把错误也做成可读行，方便前端表格展示
                return f"⚠ {r.status_code} for {url}", "direct_err"
        except Exception as e:
            return f"⚠ EXC for {url}: {e}", "direct_exc"

    def get_html_via_mirror(url: str) -> tuple[str, str]:
        mirror = "https://r.jina.ai/http://"
        # r.jina.ai 需要 http:// 前缀
        try:
            # 目标必须是 http://… 形式
            if url.startswith("https://"):
                url_http = "http://" + url[len("https://"):]
            elif url.startswith("http://"):
                url_http = url
            else:
                url_http = "http://" + url
            mirror_url = mirror + url_http
            r = requests.get(mirror_url, headers=BASE_HEADERS, timeout=15)
            if r.status_code == 200 and r.text.strip():
                return r.text, "mirror"
            else:
                return f"⚠ {r.status_code} for {mirror_url}", "mirror_err"
        except Exception as e:
            return f"⚠ EXC for mirror: {e}", "mirror_exc"

    # 1) 直连抓取
    html, via = get_html(CAL_URL)

    # 如果直连是纯文本错误或 403，改走镜像
    need_mirror = (via != "direct") or (isinstance(html, str) and html.startswith("⚠"))
    if need_mirror:
        html, via = get_html_via_mirror(CAL_URL)

    # 如果还是失败，返回诊断文本
    if isinstance(html, str) and html.startswith("⚠"):
        return [html]  # 前端会把每条当一行显示

    # 2) 解析 HTML
    soup = BeautifulSoup(html, "html.parser")

    # 多套选择器兜底（新主题 / 旧主题 / 常见列表）
    selectors = [
        ".tournament__name",          # 部分主题里用于赛名的 class
        ".tournament__title",         # 变体
        ".calendar__item .title",     # 日历卡片标题
        "h3 a",                       # 常见标题链接
        "h4 a",
        "a[href*='/tournament/']",
    ]

    events = []
    for sel in selectors:
        found = [it.get_text(strip=True) for it in soup.select(sel)]
        found = [x for x in found if x]  # 去空
        if found:
            events.extend(found)
            # 找到一套即可，避免重复
            break

    if not events:
        # 实在找不到，给标题做个诊断
        title = soup.title.get_text(strip=True) if soup.title else "(no <title>)"
        return [f"⚠ 未解析到赛名（可能是页面结构变化/JS渲染）。页面标题: {title}"]

    # 3) 去重 + 截断，避免过长
    uniq, seen = [], set()
    for x in events:
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    return uniq[:50]

        return render_template('bwf.html', data=data)
    except Exception as e:
        return f"❌ 抓取失败：{str(e)}", 500

