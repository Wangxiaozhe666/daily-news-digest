# -*- coding: utf-8 -*-
"""Publish daily news digest to WeChat Official Account (test account)"""
import requests, json, os, sys, re, struct, zlib, base64
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import smtplib
import xml.etree.ElementTree as ET
import urllib.parse

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
TIMEOUT = 20

def log(msg):
    ts = datetime.now(BJ_TZ).strftime("%H:%M:%S")
    print("[%s] %s" % (ts, msg))

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
                    if len(news) >= 3: break
            if len(news) >= 3: break
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
                if len(news) >= 3: break
    except: pass
    return news

def make_cover_png():
    """Generate a simple gold-colored PNG as cover image"""
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

def build_wechat_article(gold, dom_news, intl_news):
    """Build the WeChat article HTML content"""
    up = lambda c: c.startswith("+") if c not in ["--","0.00"] else True
    gold_up = up(gold["intl_chg"])
    dom_up = up(gold["dom_chg"])
    fx_up = up(gold["fx_chg"])

    gold_up_icon = "\u25b2" if gold_up else "\u25bc"
    dom_up_icon = "\u25b2" if dom_up else "\u25bc"
    fx_up_icon = "\u25b2" if fx_up else "\u25bc"
    gold_up_c = "#ff6b6b" if gold_up else "#4ecdc4"
    fx_up_c = "#ff6b6b" if fx_up else "#4ecdc4"

    # Domestic news items
    dom_html = ""
    insights = [
        "建议抽一周时间把主流AI工具试一遍，很可能找到提效30%的方法。",
        "夏季经济来了：关注峰谷电价、新能源板块的投资机会。",
        "个人的副业窗口还在。有货源做产品，没货源做内容。"
    ]
    for i, item in enumerate(dom_news[:3]):
        insight = insights[i] if i < len(insights) else ""
        dom_html += f"""<div style="margin:10px 0;padding:8px 0;">
<div style="display:flex;align-items:flex-start;gap:6px;">
<span style="display:inline-flex;width:18px;height:18px;border-radius:50%;background:#f0eee8;color:#8a8680;font-size:10px;align-items:center;justify-content:center;flex-shrink:0;">{i+1}</span>
<span style="font-size:13px;color:#1a1a2e;font-weight:500;line-height:1.5;">{item["title"]}</span>
</div>
"""
        if insight:
            dom_html += f"""<div style="margin:5px 0 0 24px;font-size:12px;color:#8a8680;line-height:1.6;padding:6px 10px;background:#faf8f5;border-radius:6px;">{insight}</div>"""
        dom_html += "</div>"

    # International news
    intl_html = ""
    i_insights = [
        "对国内消费者影响有限。说明中国制造已经强到让欧美用关税来挡。",
        "如果你最近想买SSD或内存条，现在可能是低位。",
        "AI能力还在加速。建议每月花30分钟了解新功能。"
    ]
    for i, item in enumerate(intl_news[:3]):
        insight = i_insights[i] if i < len(i_insights) else ""
        intl_html += f"""<div style="margin:10px 0;padding:8px 0;">
<div style="display:flex;align-items:flex-start;gap:6px;">
<span style="display:inline-flex;width:18px;height:18px;border-radius:50%;background:#f0eee8;color:#8a8680;font-size:10px;align-items:center;justify-content:center;flex-shrink:0;">{i+1}</span>
<span style="font-size:13px;color:#1a1a2e;font-weight:500;line-height:1.5;">{item["title"]}</span>
</div>
"""
        if insight:
            intl_html += f"""<div style="margin:5px 0 0 24px;font-size:12px;color:#8a8680;line-height:1.6;padding:6px 10px;background:#faf8f5;border-radius:6px;">{insight}</div>"""
        intl_html += "</div>"

    article = f"""<section style="padding:0 8px;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;max-width:400px;margin:0 auto;background:#fff;">
<!-- Data Card -->
<div style="margin:0 0 16px;background:linear-gradient(135deg,#1a1a2e,#2a2a4a);border-radius:14px;padding:16px 20px;color:#fff;position:relative;">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;text-align:center;">
<div style="padding:4px 0;"><div style="font-size:10px;color:rgba(255,255,255,0.45);">国际金价</div><div style="font-size:19px;font-weight:700;">${round(float(gold['intl_price']))}</div><div style="font-size:10px;margin-top:1px;color:{gold_up_c};">{gold_up_icon} {gold['intl_chg']}</div></div>
<div style="padding:4px 0;border-left:1px solid rgba(255,255,255,0.08);"><div style="font-size:10px;color:rgba(255,255,255,0.45);">美元/人民币</div><div style="font-size:19px;font-weight:700;">{gold['fx']}</div><div style="font-size:10px;margin-top:1px;color:{fx_up_c};">{fx_up_icon} {gold['fx_chg']}</div></div>
<div style="padding:4px 0;border-left:1px solid rgba(255,255,255,0.08);"><div style="font-size:10px;color:rgba(255,255,255,0.45);">金价(Au)</div><div style="font-size:19px;font-weight:700;">{gold['dom_price']}</div><div style="font-size:10px;margin-top:1px;color:{gold_up_c};">{dom_up_icon} {gold['dom_chg']}</div></div>
</div>
<div style="font-size:9px;color:rgba(255,255,255,0.3);text-align:right;margin-top:6px;">数据来源: 新浪财经</div>
</div>

<!-- Weather -->
<div style="background:linear-gradient(135deg,#e4f0f8,#d0e6f4);border-radius:14px;padding:14px 18px;margin-bottom:18px;display:flex;justify-content:space-between;align-items:center;">
<div style="display:flex;align-items:center;gap:10px;">
<div style="font-size:28px;">\u26c5</div>
<div><div style="font-size:11px;color:#5a7a9a;font-weight:500;">苏州 · 今日天气</div><div style="font-size:22px;font-weight:700;color:#1a3a5a;">21~27\u2103</div><div style="font-size:11px;color:#6a8aaa;">多云 · 空气质量 良</div></div>
</div>
<div style="font-size:10.5px;color:#5a7a9a;line-height:1.6;text-align:right;max-width:130px;">\u2744 周末将至<br>空调别开太低</div>
</div>

<!-- Feature -->
<div style="margin-bottom:18px;">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
<span style="width:26px;height:26px;border-radius:50%;background:#fef0ef;display:flex;align-items:center;justify-content:center;font-size:13px;">\U0001f525</span>
<h2 style="font-size:15px;font-weight:600;color:#1a1a2e;margin:0;">今日重点关注</h2>
</div>
<div style="background:#faf8f5;border-radius:14px;padding:18px;border-left:3px solid #c8a96e;">
<div style="display:inline-block;background:linear-gradient(135deg,#c8a96e,#b8924e);color:#fff;font-size:9px;padding:2px 10px;border-radius:8px;font-weight:600;margin-bottom:7px;">首要关注</div>
<div style="font-size:14px;font-weight:600;color:#1a1a2e;line-height:1.5;margin-bottom:5px;">美联储释放年内降息信号 · 全球资产或重新定价</div>
<div style="font-size:12.5px;color:#66635e;line-height:1.7;margin-bottom:9px;">美联储主席鲍威尔暗示，如果通胀继续回落，今年内可能有一次降息。美元指数应声下跌，美股、黄金同步上涨。</div>
<div style="background:#fff;border-radius:10px;padding:11px 13px 11px 26px;font-size:12.5px;line-height:1.6;color:#2d2d2d;position:relative;">
<span style="color:#c8a96e;font-weight:600;">小管说：</span><br>降息 \u2192 美元贬值 \u2192 人民币相对升值<br><br>
\U0001f539 有美股/黄金持仓的，短期利好<br>
\U0001f539 计划出国旅游/留学的，可以关注汇率窗口<br>
\U0001f539 想换美元的，可以再等等
</div>
</div>
</div>

<div style="text-align:center;padding:6px 0;color:#ddd9d2;font-size:16px;letter-spacing:5px;">\u2726 \u2726 \u2726</div>

<!-- Domestic -->
<div style="margin-bottom:18px;">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
<span style="width:26px;height:26px;border-radius:50%;background:#eef3fa;display:flex;align-items:center;justify-content:center;font-size:13px;">\U0001f1e8\U0001f1f3</span>
<h2 style="font-size:15px;font-weight:600;color:#1a1a2e;margin:0;">国内要闻</h2>
</div>
{dom_html}
</div>

<div style="text-align:center;padding:6px 0;color:#ddd9d2;font-size:16px;letter-spacing:5px;">\u2726 \u2726 \u2726</div>

<!-- International -->
<div style="margin-bottom:18px;">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
<span style="width:26px;height:26px;border-radius:50%;background:#eef8f3;display:flex;align-items:center;justify-content:center;font-size:13px;">\U0001f30d</span>
<h2 style="font-size:15px;font-weight:600;color:#1a1a2e;margin:0;">国际速览</h2>
</div>
{intl_html}
</div>

<div style="text-align:center;padding:6px 0;color:#ddd9d2;font-size:16px;letter-spacing:5px;">\u2726 \u2726 \u2726</div>

<!-- Editor note -->
<div style="background:linear-gradient(135deg,#faf8f5,#f5f3ef);border-radius:14px;padding:18px;margin:10px auto;">
<div style="font-size:12px;font-weight:600;color:#1a1a2e;margin-bottom:7px;">\u270d \ufe0f 小管的真心话</div>
<div style="font-size:12.5px;color:#66635e;line-height:1.8;">
今天的新闻有一个共同信号：世界正在换挡。<br><br>
美联储在换挡、AI 在换挡、贸易格局在换挡。<br><br>
这时候最不需要的是焦虑，最需要的是：<strong>每周花 30 分钟看看世界发生了什么</strong>。<br><br>
信息不值钱，<span style="color:#c8a96e;font-weight:600;">信息背后的判断才值钱</span>。
</div>
<div style="margin-top:10px;padding-top:10px;border-top:1px solid #e8e4dd;font-size:11px;color:#99958f;display:flex;justify-content:space-between;">
<span>—— <strong>小管</strong></span>
<span style="font-size:10px;color:#bbb7b0;">每日 07:00</span>
</div>
</div>
</section>"""

    return article

def publish_to_wechat(article_html, gold):
    """Upload cover, create draft, and publish"""
    log("获取微信 token...")
    r = S.get("https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": APPID, "secret": APPSECRET}, timeout=15)
    tok = r.json()["access_token"]

    # Upload cover
    log("上传封面图...")
    png = make_cover_png()
    r2 = S.post(
        "https://api.weixin.qq.com/cgi-bin/material/add_material",
        params={"access_token": tok, "type": "image"},
        files={"media": ("cover.png", png, "image/png")},
        timeout=15
    )
    up = r2.json()
    if "media_id" not in up:
        log("上传封面失败: " + json.dumps(up, ensure_ascii=False))
        return False

    log("创建草稿...")
    title = f"小管早报 {DATE_LABEL}"
    digest = "小管早报 " + DATE_LABEL
    
    r3 = S.post(
        "https://api.weixin.qq.com/cgi-bin/draft/add",
        params={"access_token": tok},
        json={
            "articles": [{
                "title": title,
                "author": "小管",
                "content": article_html,
                "digest": digest,
                "thumb_media_id": up["media_id"],
                "need_open_comment": 1,
                "only_fans_can_comment": 0
            }]
        },
        timeout=15
    )
    draft_res = r3.json()
    log("草稿结果: " + json.dumps(draft_res, ensure_ascii=False))

    if "media_id" in draft_res:
        # Try to publish
        log("发布草稿...")
        r4 = S.post(
            "https://api.weixin.qq.com/cgi-bin/freepublish/submit",
            params={"access_token": tok},
            json={"media_id": draft_res["media_id"]},
            timeout=15
        )
        pub_res = r4.json()
        log("发布结果: " + json.dumps(pub_res, ensure_ascii=False))
        return "media_id" in draft_res
    
    return False

def send_email(html):
    if not SMTP_USER or not SMTP_PASS:
        log("SMTP未配置，跳过邮件")
        return False
    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    subject = f"小管早报 | {DATE_LABEL} {WEEKDAY}"
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText("请在支持HTML的邮件客户端中查看。", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        s = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30)
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
        s.quit()
        log("邮件发送成功")
        return True
    except Exception as e:
        log("邮件失败: " + str(e))
        return False

def main():
    log(f"===== 小管早报 {DATE_LABEL} {WEEKDAY} =====")
    
    gold = fetch_gold_price()
    dom = fetch_domestic_news()
    intl = fetch_international_news()
    
    log(f"黄金[{gold['success']}] 国内[{len(dom)}] 国际[{len(intl)}]")
    
    if gold["success"]:
        log(f"国际金价: ${gold['intl_price']} ({gold['intl_chg']})")
    
    # Build WeChat article
    article = build_wechat_article(gold, dom, intl)
    
    # Publish to WeChat
    if APPID and APPSECRET:
        publish_to_wechat(article, gold)
    else:
        log("微信未配置，跳过公众号发布")
    
    # Send email (for verification)
    send_email(article)
    
    print()
    print("=" * 50)
    print(f"小管早报 - {DATE_LABEL}")
    print(f"国际金价: ${gold['intl_price']} ({gold['intl_chg']})")
    print(f"国内金价: {gold['dom_price']}")
    print(f"美元/人民币: {gold['fx']}")
    print("=" * 50)

if __name__ == "__main__":
    main()
