# -*- coding: utf-8 -*-
"""Publish daily news digest to WeChat Official Account (test account)"""
import requests, json, os, sys, re, struct, zlib, base64, random
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import smtplib
import xml.etree.ElementTree as ET

# === Config ===
APPID = os.environ.get("WX_APPID", "")
APPSECRET = os.environ.get("WX_SECRET", "")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_TO = os.environ.get("SMTP_TO", SMTP_USER)

BJ_TZ = timezone(timedelta(hours=8))
now = datetime.now(BJ_TZ)
DATE_LABEL = now.strftime("%Y年%m月%d日")
WEEKDAYS = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
WEEKDAY = WEEKDAYS[now.weekday()]

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "zh-CN,zh;q=0.9"})
TIMEOUT = 15

def log(msg):
    ts = datetime.now(BJ_TZ).strftime("%H:%M:%S")
    print("[%s] %s" % (ts, msg))

WEATHER_MAP = {
    "sunny": "晴", "clear": "晴", "fine": "晴",
    "partly cloudy": "多云", "cloudy": "多云",
    "overcast": "阴", "mist": "薄雾", "fog": "雾", "haze": "霾",
    "rain": "雨", "light rain": "小雨", "moderate rain": "中雨",
    "heavy rain": "大雨", "light rain shower": "小阵雨",
    "patchy rain possible": "可能有阵雨", "thundery outbreaks possible": "可能有雷雨",
    "thunderstorm": "雷阵雨", "light snow": "小雪", "snow": "雪",
    "heavy snow": "大雪", "sleet": "雨夹雪", "drizzle": "毛毛雨",
}
def tr_weather(desc_en):
    dl = desc_en.lower().strip()
    for k, v in sorted(WEATHER_MAP.items(), key=lambda x: -len(x[0])):
        if k in dl:
            return v
    return desc_en

DOY = now.timetuple().tm_yday

# === Dynamic Content Pools ===

INSIGHT_POOLS = {
    "money": [
        "关注这类消息对黄金、汇率的影响，月底可以复盘一次资产配置。",
        "做投资的朋友建议关注事件后续，可能带来短期波动机会。",
        "金价/汇率变动直接影响你的钱包，建议定期关注趋势。",
        "提醒：任何大事件落地前，市场都可能剧烈波动，谨慎操作。",
    ],
    "tech": [
        "科技迭代速度在加快，建议每季度更新一次对行业的认知。",
        "如果你的工作和AI/技术相关，这可能是你需要注意的方向。",
        "技术革命正在发生，建议花点时间了解底层逻辑。",
    ],
    "life": [
        "这条新闻和你的日常生活直接相关，建议关注后续政策。",
        "消费决策可以适当参考这一趋势。",
        "和每个人都有关的消息，建议分享给家人朋友。",
    ],
    "career": [
        "如果你的行业和这条新闻相关，建议提前思考应对策略。",
        "趋势变了，你的职业规划也需要调整。",
        "行业变化中往往蕴藏着新的机会。",
    ],
    "trade": [
        "贸易关系变化直接影响进出口商品价格。",
        "如果你做跨境生意或海淘，这条值得重点关注。",
        "全球供应链在重构，相关行业的朋友要提前布局。",
    ],
    "general": [
        "信息的价值不在于知道，而在于行动。",
        "每一条新闻背后都有一个趋势，值得多思考一层。",
        "今天的头条可能就是明天的风口。",
    ]
}

HEARTFELT_MESSAGES = [
    ("信息差就是财富差",
     "今天的信息，就是明天的决策依据。<br><br>大多数人每天刷手机看的是娱乐，少数人看的是趋势。<br><br>小管的MSG does the heavy lifting，就是把这每天<strong>30分钟的信息筛选</strong>，浓缩成5分钟读完的精华。<br><br>坚持一个月，你对世界的感知会和别人不一样。"),
    ("长期主义者的日常",
     "今天的新闻里，哪些是噪音，哪些是信号？<br><br>金价跌了0.2%，不用慌——这是波动，不是趋势。<br><br>真正值得关注的，是那些<strong>结构性变化</strong>：AI落地、贸易格局、货币政策转向。<br><br>这些才是决定未来3-5年财富走向的变量。"),
    ("普通人能做什么",
     "世界很大，新闻很多，但你只需要关注三件事：<br><br>① <strong>你的钱</strong>——汇率、金价、利率变化<br>② <strong>你的行业</strong>——技术迭代、政策变化<br>③ <strong>你的选择</strong>——消费、投资、职业<br><br>每天花3分钟读小管的MSG，三件事都覆盖了。"),
    ("金钱永不眠",
     "当你睡觉的时候，全球市场在交易。<br><br>纽约的黄金、伦敦的汇率、东京的股市……<br>这就是为什么早上7点的小管的MSG，是你一天中最重要的信息摄入。<br><br><strong>用信息差，打败焦虑。</strong>"),
    ("复利的力量",
     "每天积累一点认知，365天后的你和现在完全不同。<br><br>今天的新闻也许看起来和昨天差不多——<br>但连续看一周，你就能发现趋势；<br>连续看一个月，你就能做出判断；<br>连续看一年，你就能<strong>预见未来</strong>。<br><br>坚持读报，本身就是一种复利投资。"),
    ("不确定性中的锚",
     "世界越来越不确定——关税、战争、AI替代……<br><br>但有一件事是确定的：<strong>信息越多，决策越稳</strong>。<br><br>小管的MSG不制造焦虑，只帮你把复杂的世界<strong>翻译成行动</strong>。<br><br>今天的新闻，今天的启发，今天行动。"),
    ("你的信息饮食",
     "吃什么决定你的身体，<strong>读什么决定你的大脑</strong>。<br><br>与其刷一小时短视频，不如花3分钟读完今天的早报。<br><br>金价走势、汇率波动、科技趋势——<br>这些才是真正能帮你<strong>赚钱和避坑</strong>的信息。"),
    ("宏观是背景，微观是机会",
     "美联储加息、中美博弈、AI革命——<br>这些宏观大事听起来离你很远。<br><br>但汇率变了，你买进口商品贵了；<br>AI来了，你的工作方式要变了；<br>金价涨了，你的资产配置该调整了。<br><br><strong>看懂宏观，才能做好微观决策。</strong>"),
    ("慢下来，快起来",
     "每天早上的3分钟，是这一天最值钱的3分钟。<br><br>先把世界看清楚，再去行动。<br><br>小管的MSG breaks down information，你只需要<strong>咽下去，消化掉</strong>。<br><br>慢读新闻，快做决策。"),
    ("认知的复利曲线",
     "知识和金钱一样，有复利效应。<br><br>第1天：你看一条新闻<br>第30天：你能看出趋势<br>第100天：你能预判走势<br>第365天：你已经成为身边人的'信息来源'<br><br><strong>今天，是你复利曲线的第{}天。</strong>"),
]

WEATHER_TIPS = [
    "出门记得带伞，有备无患。", "温差大，建议带件外套。",
    "适合外出走走，呼吸新鲜空气。", "空调别开太低，容易感冒。",
    "多喝水，注意补水。", "紫外线较强，注意防晒。",
    "空气干燥，注意保湿。", "适合晨跑，开启活力一天！",
    "今天适合在阳台喝杯咖啡看看书。", "湿度较高，衣物晾晒注意通风。",
]

# === Data Fetching ===

def fetch_gold_price():
    r = {"success":False,"intl_price":"--","intl_chg":"--","dom_price":"--","dom_chg":"--","update":"--","fx":"--","fx_chg":"--"}
    S.headers.update({"Referer": "https://finance.sina.com.cn/futures/quotes/XAUUSD.shtml"})
    try:
        resp = S.get("https://hq.sinajs.cn/list=hf_XAU", timeout=TIMEOUT)
        resp.encoding = "gbk"
        m = re.search(r'"([^"]*)"', resp.text)
        if m:
            parts = m.group(1).split(",")
            if len(parts) >= 14:
                cur = parts[0]; prev = parts[1]
                chg = "0.00"
                try: chg = "%.2f" % ((float(cur) - float(prev)) / float(prev) * 100)
                except: pass
                r["intl_price"] = cur; r["intl_chg"] = chg; r["success"] = True
    except: pass
    try:
        resp = S.get("https://hq.sinajs.cn/list=sh518880", timeout=TIMEOUT)
        resp.encoding = "gbk"
        m = re.search(r'"([^"]*)"', resp.text)
        if m:
            parts = m.group(1).split(",")
            if len(parts) >= 6:
                p = float(parts[3]); prev = float(parts[2])
                gp = "%.2f" % (p * 100); chg = "0.00"
                try: chg = "%.2f" % ((p - prev) / prev * 100)
                except: pass
                r["dom_price"] = gp; r["dom_chg"] = chg
    except: pass
    try:
        resp = S.get("https://hq.sinajs.cn/list=fx_susdcny", timeout=TIMEOUT)
        resp.encoding = "gbk"
        m = re.search(r'"([^"]*)"', resp.text)
        if m:
            parts = m.group(1).split(",")
            if len(parts) >= 3:
                rate = float(parts[1]); prev = float(parts[2])
                chg = "0.000"
                try: chg = "%.3f" % ((rate - prev) / prev * 100)
                except: pass
                r["fx"] = "%.4f" % rate; r["fx_chg"] = chg
    except: pass
    r["update"] = now.strftime("%H:%M")
    return r

def fetch_domestic_news():
    news = []
    try:
        resp = S.get("https://top.baidu.com/api/board?tab=realtime", timeout=TIMEOUT)
        data = resp.json()
        for card in data.get("data", {}).get("cards", []):
            for item in card.get("content", []):
                title = item.get("word", "") or item.get("query", "")
                if title:
                    news.append({"title": title})
                    if len(news) >= 5: break
            if len(news) >= 5: break
    except: pass
    return news

def fetch_international_news():
    news = []
    try:
        resp = S.get("https://feeds.bbci.co.uk/news/world/rss.xml", timeout=TIMEOUT)
        root = ET.fromstring(resp.content)
        for item in root.iter("item"):
            title = item.findtext("title", "")
            if title and len(title) > 5:
                news.append({"title": title.strip()})
                if len(news) >= 5: break
    except: pass
    return news

def fetch_weather():
    """Fetch real-time weather for Suzhou"""
    try:
        resp = S.get("https://wttr.in/Suzhou?format=j1&lang=zh", timeout=TIMEOUT)
        data = resp.json()
        cc = data['current_condition'][0]
        fc = data['weather'][0]
        desc_en = cc['weatherDesc'][0]['value']
        desc_cn = tr_weather(desc_en)
        temp_now = cc['temp_C']
        temp_high = fc['maxtempC']
        temp_low = fc['mintempC']
        tip_idx = DOY % len(WEATHER_TIPS)
        tip = WEATHER_TIPS[tip_idx]
        emoji_map = {"晴":"☀️","多云":"⛅","阴":"☁️","雾":"🌫","霾":"🌫","雨":"🌧","雪":"❄️","雷":"⛈","阵雨":"🌦"}
        emoji = "☀️"
        for k, v in emoji_map.items():
            if k in desc_cn:
                emoji = v
                break
        log("天气: %s %s°C (%s~%s°C)" % (desc_cn, temp_now, temp_low, temp_high))
        return {"temp_now":temp_now,"temp_high":temp_high,"temp_low":temp_low,"desc":desc_cn,"emoji":emoji,"tip":tip}
    except Exception as e:
        log("天气失败: %s" % e)
        return {"temp_now":"--","temp_high":"--","temp_low":"--","desc":"--","emoji":"☀️","tip":"新的一天，加油！"}

# === AI & Tech Data ===

AI_KEYWORDS = ["ai", "gpt", "llm", "claude", "openai", "deepseek", "model", "machine learning",
               "neural", "transformer", "diffusion", "agent", "open source", "github",
               "gemini", "anthropic", "mistral", "llama", "fine-tun", "rag", "vector",
               "embedding", "chatbot", "copilot", "cursor", "vibe cod", "prompt",
               "langchain", "langgraph", "crewai", "mcp", "a2a", "tool calling",
               "function call", "agi", "benchmark", "sota", "paper", "release",
               "announc", "launch", "new tool", "framework", "library"]

def fetch_ai_news():
    """Fetch AI-related news from HackerNews and arXiv"""
    items = []
    
    # --- HackerNews ---
    try:
        resp = S.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=TIMEOUT)
        story_ids = resp.json()[:40]
        for sid in story_ids:
            try:
                r2 = S.get("https://hacker-news.firebaseio.com/v0/item/%s.json" % sid, timeout=8)
                story = r2.json()
                title = story.get("title", "")
                url = story.get("url", "https://news.ycombinator.com/item?id=%s" % sid)
                score = story.get("score", 0)
                if any(kw in title.lower() for kw in AI_KEYWORDS):
                    items.append({
                        "title": title,
                        "url": url,
                        "score": score,
                        "source": "HackerNews"
                    })
            except:
                pass
            if len([x for x in items if x["source"] == "HackerNews"]) >= 6:
                break
    except Exception as e:
        log("HackerNews failed: %s" % e)
    
    # --- arXiv cs.AI ---
    try:
        resp = S.get("http://export.arxiv.org/api/query", timeout=TIMEOUT,
                     params={"search_query": "cat:cs.AI", "sortBy": "submittedDate",
                             "start": 0, "max_results": 5})
        import xml.etree.ElementTree as ET3
        root = ET3.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "").strip()
            link = entry.find("atom:id").text if entry.find("atom:id") is not None else ""
            if title and len(title) > 10:
                items.append({
                    "title": title,
                    "url": link,
                    "score": 0,
                    "source": "arXiv"
                })
                if len([x for x in items if x["source"] == "arXiv"]) >= 3:
                    break
    except Exception as e:
        log("arXiv failed: %s" % e)
    
    # Dedup by title similarity
    seen = set()
    deduped = []
    for item in items:
        key = item["title"][:30].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    
    log("AI news: HN=%d arXiv=%d deduped=%d" % (
        len([x for x in items if x["source"] == "HackerNews"]),
        len([x for x in items if x["source"] == "arXiv"]),
        len(deduped)))
    return deduped[:10]


def fetch_douyin_hot():
    """Fetch Douyin hot search list"""
    try:
        resp = S.get("https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/",
                     timeout=TIMEOUT)
        data = resp.json()
        words = data.get("word_list", [])
        items = []
        for w in words[:15]:
            items.append({
                "title": w.get("word", ""),
                "hot": w.get("hot_value", 0),
                "position": w.get("position", 0)
            })
        log("Douyin hot: %d items" % len(items))
        return items[:10]
    except Exception as e:
        log("Douyin hot failed: %s" % e)
        return []



def classify_news(title):
    t = title.lower()
    if any(k in t for k in ["金价","黄金","美元","汇率","降息","加息","股市","基金","理财","投资","房价"]):
        return "money"
    if any(k in t for k in ["ai","人工智能","芯片","科技","手机","电脑","软件","互联网","数据","算法","机器人","自动驾驶"]):
        return "tech"
    if any(k in t for k in ["消费","食品","健康","医疗","教育","住房","交通","出行","生活","社保"]):
        return "life"
    if any(k in t for k in ["就业","招聘","创业","职场","行业","产业","制造业","工厂"]):
        return "career"
    if any(k in t for k in ["关税","贸易","出口","进口","制裁","封锁","反倾销"]):
        return "trade"
    return "general"

def pick_insight(title, idx):
    cat = classify_news(title)
    pool = INSIGHT_POOLS.get(cat, INSIGHT_POOLS["general"])
    return pool[(idx + DOY) % len(pool)]

def get_heartfelt_message():
    idx = DOY % len(HEARTFELT_MESSAGES)
    msg = HEARTFELT_MESSAGES[idx]
    title = msg[0]
    body = msg[1]
    if "{}" in body:
        body = body.format(DOY)
    return title, body

def make_cover_png():
    s = 200; r, g, b = 200, 169, 110
    def ck(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", s, s, 8, 2, 0, 0, 0)
    raw = b""
    for y in range(s):
        raw += b"\x00"
        for x in range(s):
            raw += bytes([r, g, b])
    return b"\x89PNG\r\n\x1a\n" + ck(b"IHDR", ihdr) + ck(b"IDAT", zlib.compress(raw)) + ck(b"IEND", b"")

def build_wechat_article(gold, dom_news, intl_news, heartfelt_title, heartfelt_body, ai_news=None, douyin=None):
    def is_up(chg):
        try: return float(chg) > 0
        except: return True
    gold_up = is_up(gold["intl_chg"])
    dom_up = is_up(gold["dom_chg"])
    fx_up = is_up(gold["fx_chg"])
    gold_up_icon = "\u25b2" if gold_up else "\u25bc"
    dom_up_icon = "\u25b2" if dom_up else "\u25bc"
    fx_up_icon = "\u25b2" if fx_up else "\u25bc"
    gold_up_c = "#ff6b6b" if gold_up else "#4ecdc4"
    fx_up_c = "#ff6b6b" if fx_up else "#4ecdc4"

    # Domestic gold summary
    try:
        dom_price = float(gold["dom_price"])
        dom_chg = float(gold["dom_chg"])
        if dom_chg > 0.3:
            gold_summary = f"国内金价升至{dom_price:.2f}元/克，溢价明显，短期追高需谨慎。"
        elif dom_chg > 0:
            gold_summary = f"国内金价{dom_price:.2f}元/克微涨，溢价收窄，配置窗口仍在。"
        elif dom_chg < -0.3:
            gold_summary = f"国内金价回落至{dom_price:.2f}元/克，回调较大，或是逢低布局机会。"
        elif dom_chg < 0:
            gold_summary = f"国内金价{dom_price:.2f}元/克小幅回落，观望情绪升温。"
        else:
            gold_summary = f"国内金价持平{dom_price:.2f}元/克，市场静待方向。"
    except:
        gold_summary = "国内金价暂无变化，持续观望中。"

    # --- Build news items with improved card design ---
    def news_card(items, offset=0):
        html = ""
        for i, item in enumerate(items[:5]):
            html += f"""<div style="margin:0 0 6px 0;padding:6px 0;border-bottom:1px solid #f5f3f0;">
<div style="display:flex;align-items:flex-start;gap:6px;">
<span style="font-size:11px;font-weight:600;color:#c8a96e;width:18px;flex-shrink:0;">{i+1}.</span>
<div>
<div style="font-size:12.5px;color:#222;line-height:1.5;">{item["title"]}</div>
</div>
</div>
</div>"""
        return html

    dom_html = news_card(dom_news, 0)
    intl_html = news_card(intl_news, 10)

    # AI news card builder
    def ai_card(items):
        if not items:
            return '<div style="margin:0 16px 8px;font-size:12px;color:#999;text-align:center;padding:8px;">暂无AI资讯</div>'
        html = ""
        for i, item in enumerate(items[:8]):
            source_tag = '<span style="display:inline-block;background:#e8f0fe;color:#1967d2;font-size:9px;padding:1px 5px;border-radius:8px;">%s</span>' % item.get("source","")
            score_str = ' <span style="font-size:9px;color:#999;">%s↑</span>' % item["score"] if item.get("score", 0) > 0 else ""
            title = item["title"]
            if len(title) > 60:
                title = title[:57] + "..."
            html += '<div style="margin:0 0 4px 0;padding:4px 0;border-bottom:1px solid #f5f3f0;">'
            html += '<div style="display:flex;align-items:flex-start;gap:4px;">'
            html += '<span style="font-size:10px;font-weight:600;color:#c8a96e;width:16px;flex-shrink:0;">%d.</span>' % (i+1)
            html += '<div><div style="font-size:11px;color:#222;line-height:1.4;">%s %s%s</div></div>' % (title, source_tag, score_str)
            html += '</div></div>'
        return html

    ai_html = ai_card(ai_news)

    # Douyin hot card builder
    def douyin_card(items):
        if not items:
            return '<div style="margin:0 16px 8px;font-size:12px;color:#999;text-align:center;padding:8px;">暂无热搜数据</div>'
        html = ""
        for i, item in enumerate(items[:8]):
            title = item["title"]
            hot_val = item.get("hot", 0)
            hot_str = ""
            if hot_val > 0:
                if hot_val >= 10000000:
                    hot_str = '<span style="font-size:9px;color:#ff6b6b;">%.1fM</span>' % (hot_val/10000000)
                elif hot_val >= 10000:
                    hot_str = '<span style="font-size:9px;color:#ff6b6b;">%.1fW</span>' % (hot_val/10000)
                else:
                    hot_str = '<span style="font-size:9px;color:#ff6b6b;">%d</span>' % hot_val
            html += '<div style="margin:0 0 4px 0;padding:4px 0;border-bottom:1px solid #f5f3f0;">'
            html += '<div style="display:flex;align-items:flex-start;gap:4px;">'
            html += '<span style="font-size:10px;font-weight:600;color:#ff6b6b;width:16px;flex-shrink:0;">%d.</span>' % (i+1)
            html += '<div><div style="font-size:11px;color:#222;line-height:1.4;">%s %s</div></div>' % (title, hot_str)
            html += '</div></div>'
        return html

    douyin_html = douyin_card(douyin)

    # Color helpers
    bg_c = "#e8e4dd"  # neutral
    gold_bg = "#1a1a2e"
    card_shadow = "0 2px 8px rgba(0,0,0,0.04)"

    article = f"""<div style="max-width:420px;margin:0 auto;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#fff;color:#222;">

<!-- ====== HEADER ====== -->
<div style="background:#fff;border-bottom:2px solid #1a1a2e;padding:20px 16px 10px;margin:0 0 12px;">
<div style="font-size:22px;font-weight:800;color:#1a1a2e;letter-spacing:2px;">小管的MSG</div>
<div style="display:flex;justify-content:space-between;font-size:11px;color:#999;margin-top:2px;">
<span>{DATE_LABEL} {WEEKDAY}</span>
<span>第{DOY}期</span>
</div>
</div>

<!-- ====== DATA BAR ====== -->
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;margin:0 16px 10px;border-radius:8px;overflow:hidden;border:1px solid #eee;">
<div style="padding:10px 6px;text-align:center;border-right:1px solid #eee;">
<div style="font-size:9px;color:#999;font-weight:500;">国际金价</div>
<div style="font-size:20px;font-weight:700;color:#1a1a2e;">${round(float(gold["intl_price"]))}</div>
<div style="font-size:10px;color:{"#e74c3c" if float(gold["intl_chg"])>0 else "#27ae60"};">
{"▲" if gold_up else "▼"} {gold["intl_chg"]}%
                    </div>
<div style="font-size:7px;color:#ccc;margin-top:2px;">新浪财经</div>
</div>
<div style="padding:10px 6px;text-align:center;border-right:1px solid #eee;">
<div style="font-size:9px;color:#999;font-weight:500;">美元/人民币</div>
<div style="font-size:20px;font-weight:700;color:#1a1a2e;">{gold["fx"]}</div>
<div style="font-size:10px;color:{"#e74c3c" if float(gold["fx_chg"])>0 else "#27ae60"};">
{"▲" if fx_up else "▼"} {gold["fx_chg"]}%
</div>
                    </div>
<div style="font-size:7px;color:#ccc;margin-top:2px;">新浪财经</div>
<div style="padding:10px 6px;text-align:center;">
<div style="font-size:9px;color:#999;font-weight:500;">国内金价</div>
<div style="font-size:20px;font-weight:700;color:#1a1a2e;">{gold["dom_price"]}</div>
<div style="font-size:10px;color:{"#e74c3c" if float(gold["dom_chg"])>0 else "#27ae60"};">
{"▲" if dom_up else "▼"} {gold["dom_chg"]}%
</div>
                    </div>
<div style="font-size:7px;color:#ccc;margin-top:2px;">新浪财经</div>
</div>

<!-- ====== DOMESTIC GOLD ====== -->
<div style="margin:0 16px 10px;display:flex;gap:8px;">
<div style="flex:2;background:#fffaf5;border-radius:8px;padding:12px 14px;border-left:3px solid #c8a96e;">
<div style="font-size:9px;color:#c8a96e;font-weight:600;margin-bottom:4px;">国内金价</div>
<div style="font-size:13px;font-weight:700;color:#1a1a2e;line-height:1.8;white-space:pre-wrap;word-break:break-all;">{gold_summary}</div>
</div>
</div>

<hr style="border:none;border-top:1px solid #eee;margin:0 16px 8px;">

<!-- ====== DOMESTIC ====== -->
<div style="margin:0 16px 8px;">
<div style="font-size:11px;font-weight:600;color:#1a1a2e;padding:4px 0 2px;border-bottom:2px solid #1a1a2e;margin-bottom:6px;">\U0001f1e8\U0001f1f3 国内热点</div>
{dom_html}
</div>

<hr style="border:none;border-top:1px solid #eee;margin:0 16px 8px;">

<!-- ====== INTERNATIONAL ====== -->
<div style="margin:0 16px 8px;">
<div style="font-size:11px;font-weight:600;color:#1a1a2e;padding:4px 0 2px;border-bottom:2px solid #1a1a2e;margin-bottom:6px;">\U0001f30d 国际新闻</div>
{intl_html}
</div>

<hr style="border:none;border-top:1px solid #eee;margin:0 16px 8px;">

<!-- ====== AI \u524d\u6cbf ====== -->
<div style="margin:0 16px 8px;">
<div style="font-size:11px;font-weight:600;color:#1a1a2e;padding:4px 0 2px;border-bottom:2px solid #1a1a2e;margin-bottom:6px;">\U0001f916 AI\u524d\u6cbf</div>
{ai_html}
</div>

<hr style="border:none;border-top:1px solid #eee;margin:0 16px 8px;">

<!-- ====== \u6296\u97f3\u70ed\u699c ====== -->
<div style="margin:0 16px 8px;">
<div style="font-size:11px;font-weight:600;color:#1a1a2e;padding:4px 0 2px;border-bottom:2px solid #1a1a2e;margin-bottom:6px;">\U0001f525 \u6296\u97f3\u70ed\u699c</div>
{douyin_html}
</div>

<hr style="border:none;border-top:1px solid #eee;margin:0 16px 8px;">

<!-- ====== EDITOR ====== -->
<div style="margin:0 16px 16px;background:#fcf9f5;border-radius:8px;padding:14px;">
<div style="font-size:11px;font-weight:600;color:#c8a96e;margin-bottom:4px;">\u270d\ufe0f 小管的MSG Insights · {heartfelt_title}</div>
<div style="font-size:12px;color:#555;line-height:1.7;">{heartfelt_body}</div>
<div style="margin-top:8px;font-size:10px;color:#bbb;text-align:right;">— 小管的MSG</div>
</div>

<!-- ====== FOOTER ====== -->
<div style="text-align:center;padding:0 16px 16px;">
<div style="font-size:8px;color:#ddd;letter-spacing:1px;">\u2014\u2014 小管的MSG \u2014\u2014</div>
</div>
</div>"""


    return article

def publish_to_wechat(article_html, gold):
    log("获取微信 token...")
    r = S.get("https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type":"client_credential","appid":APPID,"secret":APPSECRET}, timeout=15)
    tok = r.json()["access_token"]
    log("上传封面图...")
    png = make_cover_png()
    r2 = S.post("https://api.weixin.qq.com/cgi-bin/material/add_material",
        params={"access_token":tok,"type":"image"},
        files={"media":("cover.png",png,"image/png")}, timeout=15)
    up = r2.json()
    if "media_id" not in up:
        log("上传封面失败: "+json.dumps(up,ensure_ascii=False))
        return False
    log("创建草稿...")
    r3 = S.post("https://api.weixin.qq.com/cgi-bin/draft/add",
        params={"access_token":tok},
        json={"articles":[{"title":"小管的MSG "+DATE_LABEL,"author":"小管的MSG","content":article_html,
            "digest":"小管的MSG "+DATE_LABEL,"thumb_media_id":up["media_id"],"need_open_comment":1,"only_fans_can_comment":0}]},
        timeout=15)
    draft_res = r3.json()
    log("草稿结果: "+json.dumps(draft_res,ensure_ascii=False))
    if "media_id" in draft_res:
        log("发布草稿...")
        r4 = S.post("https://api.weixin.qq.com/cgi-bin/freepublish/submit",
            params={"access_token":tok},
            json={"media_id":draft_res["media_id"]}, timeout=15)
        pub_res = r4.json()
        log("发布结果: "+json.dumps(pub_res,ensure_ascii=False))
        return "media_id" in draft_res
    return False

def send_email(html):
    if not SMTP_USER or not SMTP_PASS:
        log("SMTP未配置，跳过邮件")
        return False
    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    msg["Subject"] = Header("小管的MSG | %s %s" % (DATE_LABEL, WEEKDAY), "utf-8")
    msg.attach(MIMEText("请在支持HTML的邮件客户端中查看。","plain","utf-8"))
    msg.attach(MIMEText(html,"html","utf-8"))
    try:
        s = smtplib.SMTP_SSL("smtp.qq.com",465,timeout=30)
        s.login(SMTP_USER,SMTP_PASS)
        s.send_message(msg)
        s.quit()
        log("邮件发送成功")
        return True
    except Exception as e:
        log("邮件失败: "+str(e))
        return False

def main():
    log("===== 小管的MSG %s %s ===== %s" % (DATE_LABEL, WEEKDAY, "第%d天" % DOY))
    gold = fetch_gold_price()
    dom = fetch_domestic_news()
    intl = fetch_international_news()
    ai = fetch_ai_news()
    douyin = fetch_douyin_hot()
    log("Gold[%s] CN[%d] Intl[%d] AI[%d] Douyin[%d]" % (
        "OK" if gold["success"] else "FAIL",
        len(dom), len(intl), len(ai), len(douyin)))
    if gold["success"]:
        log("Gold: $%s (%s)" % (gold["intl_price"], gold["intl_chg"]))
    hf_title, hf_body = get_heartfelt_message()
    log("Heartfelt: %s" % hf_title)
    article = build_wechat_article(gold, dom, intl, hf_title, hf_body, ai, douyin)
    if APPID and APPSECRET:
        publish_to_wechat(article, gold)
    else:
        log("WeChat not configured, skip")
    send_email(article)
    print()
    print("="*50)
    print("  小管的MSG - %s (%s)" % (DATE_LABEL, "第%d天" % DOY))
    print("  Gold: $%s (%s)" % (gold["intl_price"], gold["intl_chg"]))
    print("  CN Gold: %s  |  USD/CNY: %s" % (gold["dom_price"], gold["fx"]))
    print("  CN: %d  Intl: %d  AI: %d  Douyin: %d" % (len(dom), len(intl), len(ai), len(douyin)))
    print("="*50)

if __name__ == "__main__":
    main()
