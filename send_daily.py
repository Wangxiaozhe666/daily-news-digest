#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily news digest: auto fetch news + gold, generate charts, send email"""

import requests, re, json, os, smtplib
import xml.etree.ElementTree as ET
import html as html_mod, urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime, timezone, timedelta

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


# === Gold price ===
def fetch_gold_price():
    r = {"success":False,"intl_price":"--","intl_chg":"--","dom_price":"--","dom_chg":"--","update":"--"}
    S.headers.update({"Referer": "https://finance.sina.com.cn/futures/quotes/XAUUSD.shtml"})
    try:
        resp = S.get("https://hq.sinajs.cn/list=hf_XAU", timeout=TIMEOUT)
        resp.encoding = "gbk"
        m = re.search(r'"([^"]*)"', resp.text)
        if m:
            parts = m.group(1).split(",")
            if len(parts) >= 14:
                cur = parts[0]
                prev = parts[1]
                chg = "0.00"
                try:
                    chg = "%.2f" % ((float(cur) - float(prev)) / float(prev) * 100)
                except:
                    pass
                r["intl_price"] = cur
                r["intl_chg"] = chg
                r["success"] = True
                log("国际金价: $%s (%s%%)" % (cur, chg))
    except Exception as e:
        log("国际金价失败: %s" % e)
    try:
        resp = S.get("https://hq.sinajs.cn/list=sh518880", timeout=TIMEOUT)
        resp.encoding = "gbk"
        m = re.search(r'"([^"]*)"', resp.text)
        if m:
            parts = m.group(1).split(",")
            if len(parts) >= 6:
                p = float(parts[3])
                prev = float(parts[2])
                gp = "%.2f" % (p * 100)
                chg = "0.00"
                try:
                    chg = "%.2f" % ((p - prev) / prev * 100)
                except:
                    pass
                r["dom_price"] = gp
                r["dom_chg"] = chg
                log("国内金价: %s元/克 (%s%%)" % (gp, chg))
    except Exception as e:
        log("国内金价失败: %s" % e)
    r["update"] = now.strftime("%H:%M")
    return r


# === Gold history (Yahoo Finance) + SVG chart ===
def make_svg_chart(prices, dates, w=560, h=180):
    if not prices or len(prices) < 2:
        return '<p style="color:#999;text-align:center;padding:20px;">暂无足够数据</p>'
    min_p = min(prices)
    max_p = max(prices)
    rng = max_p - min_p
    if rng == 0:
        rng = 1
    n = len(prices)
    pad = 36
    pw = w - pad * 2
    ph = h - pad * 2
    pts = []
    for i, p in enumerate(prices):
        x = pad + (i / (n - 1)) * pw
        y = pad + ph - ((p - min_p) / rng) * ph
        pts.append((x, y))
    path = "M " + " ".join("%.1f,%.1f" % (x, y) for x, y in pts)
    fill_path = path + " L %.1f,%.1f L %.1f,%.1f Z" % (pts[-1][0], pad + ph, pts[0][0], pad + ph)
    # Y labels
    yl = ""
    for i in range(5):
        val = min_p + (rng * i / 4)
        y = pad + ph - (i / 4) * ph
        yl += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#f0f2f5" stroke-width="1"/>' % (pad, y, w - pad, y)
        yl += '<text x="%d" y="%.1f" text-anchor="end" fill="#999" font-size="10">$%.0f</text>' % (pad - 6, y + 4, val)
    # X labels
    xl = ""
    for idx in [0, n // 2, n - 1]:
        x = pad + (idx / (n - 1)) * pw
        xl += '<text x="%.1f" y="%d" text-anchor="middle" fill="#999" font-size="10">%s</text>' % (x, h - 6, dates[idx])
    lp = pts[-1]
    svg_parts = []
    svg_parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (w, h, w, h))
    svg_parts.append('<defs><linearGradient id="gg" x1="0" y1="0" x2="0" y2="1">')
    svg_parts.append('<stop offset="0%" stop-color="#4a90d9" stop-opacity="0.12"/>')
    svg_parts.append('<stop offset="100%" stop-color="#4a90d9" stop-opacity="0.01"/>')
    svg_parts.append('</linearGradient></defs>')
    svg_parts.append(yl)
    svg_parts.append('<path d="%s" fill="url(#gg)"/>' % fill_path)
    svg_parts.append('<path d="%s" fill="none" stroke="#4a90d9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>' % path)
    svg_parts.append('<circle cx="%.1f" cy="%.1f" r="3.5" fill="#4a90d9" stroke="#fff" stroke-width="1.5"/>' % (lp[0], lp[1]))
    svg_parts.append(xl)
    svg_parts.append('</svg>')
    return "".join(svg_parts)


def fetch_gold_history():
    result = {"charts": {"1w": "", "1m": "", "1y": ""}}
    ranges = [("5d", "1w"), ("1mo", "1m"), ("1y", "1y")]
    for rng, key in ranges:
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/GC%%3DF?range=%s&interval=1d" % rng
            resp = S.get(url, timeout=TIMEOUT)
            data = resp.json()
            rd = data["chart"]["result"][0]
            timestamps = rd["timestamp"]
            prices = rd["indicators"]["quote"][0]["close"]
            valid = [(t, p) for t, p in zip(timestamps, prices) if p is not None]
            dates = [datetime.fromtimestamp(t).strftime("%m/%d") for t, p in valid]
            pvals = [p for t, p in valid]
            result["charts"][key] = make_svg_chart(pvals, dates)
            log("金价历史(%s): %d个数据点" % (key, len(valid)))
        except Exception as e:
            log("金价历史(%s)失败: %s" % (key, e))
            result["charts"][key] = '<p style="color:#999;text-align:center;padding:20px;">暂无数据</p>'
    return result


# === Domestic news ===
def fetch_domestic_news():
    news = []
    try:
        resp = S.get("https://top.baidu.com/api/board?tab=realtime", timeout=TIMEOUT)
        data = resp.json()
        for card in data.get("data", {}).get("cards", []):
            for item in card.get("content", []):
                title = item.get("word", "") or item.get("query", "")
                if title:
                    q = urllib.parse.quote(title)
                    news.append({"title": title, "url": "https://www.baidu.com/s?wd=" + q, "source": "百度热搜", "trans": ""})
        log("百度热搜: %d条" % len(news))
    except Exception as e:
        log("百度热搜失败: %s" % e)
    try:
        resp = S.get("https://weibo.com/ajax/side/hotSearch", timeout=TIMEOUT)
        data = resp.json()
        existing = set(n["title"] for n in news)
        for item in data.get("data", {}).get("realtime", [])[:8]:
            title = item.get("word", "")
            if title and title not in existing:
                q = urllib.parse.quote(title)
                news.append({"title": title, "url": "https://s.weibo.com/weibo?q=" + q, "source": "微博热搜", "trans": ""})
                existing.add(title)
        log("微博热搜已补充")
    except:
        pass
    return news


# === International news with translation ===
def translate_text(text):
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text)
        resp = S.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()[0][0][0]
    except:
        pass
    return ""


def fetch_international_news():
    news = []
    try:
        resp = S.get("https://feeds.bbci.co.uk/news/world/rss.xml", timeout=TIMEOUT)
        root = ET.fromstring(resp.content)
        for item in root.iter("item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            if title and len(title) > 5:
                trans = translate_text(title)
                news.append({"title": title.strip(), "url": link, "trans": trans, "source": "BBC"})
                if len(news) >= 10:
                    break
        log("BBC国际新闻: %d条" % len(news))
    except Exception as e:
        log("BBC RSS失败: %s" % e)
    return news


# === Build HTML ===
def build_html(gold, gold_hist, dom_news, intl_news):
    tmpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_template.html")
    with open(tmpl_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Gold direction
    up = False
    down = False
    try:
        chg = float(gold["intl_chg"])
        if chg > 0:
            up = True
        elif chg < 0:
            down = True
    except:
        pass
    icon = "&#x1f4c8;" if up else ("&#x1f4c9;" if down else "&#x27a1;")
    color = "#e74c3c" if up else ("#27ae60" if down else "#7f8c8d")
    sign = "+" if up else ("-" if down else "")

    # Build news HTML
    def make_rows(items):
        rows = ""
        emojis = ["&#x1f4cc;","&#x1f525;","&#x1f4a1;","&#x1f4e2;","&#x2b50;","&#x1f514;","&#x1f4ac;","&#x1f4f0;","&#x1f5de;","&#x26a1;","&#x1f4ce;","&#x1f4aa;"]
        for i, item in enumerate(items):
            emoji = emojis[i % len(emojis)]
            title = html_mod.escape(item["title"])
            tag = '<span class="tag">' + html_mod.escape(item["source"]) + "</span>"
            url = item.get("url", "")
            trans = item.get("trans", "")
            trans_html = ""
            if trans:
                trans_html = '<span class="trans">&#x1f310; ' + html_mod.escape(trans) + "</span>"
            if url:
                rows += '<a class="news-item" href="' + html_mod.escape(url) + '" target="_blank">' + emoji + " " + title + tag + trans_html + "</a>"
            else:
                rows += '<div class="news-item">' + emoji + " " + title + tag + trans_html + "</div>"
        return rows

    html = html.replace("__TITLE__", "每日新闻早报")
    html = html.replace("__DATE__", DATE_LABEL)
    html = html.replace("__WEEKDAY__", WEEKDAY)
    html = html.replace("__GOLD_TITLE__", "现货黄金行情")
    html = html.replace("__GOLD_INTL_PRICE__", "$" + gold["intl_price"])
    html = html.replace("__GOLD_INTL_CHG__", gold["intl_chg"])
    html = html.replace("__GOLD_DOM_PRICE__", gold["dom_price"] + " 元/克")
    html = html.replace("__GOLD_COLOR__", color)
    html = html.replace("__GOLD_ICON__", icon)
    html = html.replace("__GOLD_CHANGE_SIGN__", sign)
    html = html.replace("__GOLD_UPDATE__", "更新时间: " + gold["update"])
    html = html.replace("__GOLD_CHART_1W__", gold_hist["charts"]["1w"])
    html = html.replace("__GOLD_CHART_1M__", gold_hist["charts"]["1m"])
    html = html.replace("__GOLD_CHART_1Y__", gold_hist["charts"]["1y"])
    html = html.replace("__DOM_TITLE__", "国内热点")
    html = html.replace("__INTL_TITLE__", "国际新闻")
    html = html.replace("__DOM_NEWS__", make_rows(dom_news[:15]))
    html = html.replace("__INTL_NEWS__", make_rows(intl_news[:12]))
    html = html.replace("__FOOTER_DATE__", DATE_LABEL)
    return html


# === Send email ===
def send_email(html):
    if not SMTP_USER or not SMTP_PASS:
        log("SMTP未配置")
        return False
    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    subject = "每日新闻早报 | %s %s" % (DATE_LABEL, WEEKDAY)
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText("请在支持HTML的邮件客户端中查看。", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        log("连接QQ邮箱SMTP...")
        s = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30)
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [SMTP_TO], msg.as_string())
        s.quit()
        log("邮件已发送 -> %s" % SMTP_TO)
        return True
    except Exception as e:
        log("邮件失败: %s" % e)
        return False


# === Main ===
def main():
    log("===== 新闻早报 %s %s =====" % (DATE_LABEL, WEEKDAY))
    gold = fetch_gold_price()
    gold_hist = fetch_gold_history()
    dom = fetch_domestic_news()
    intl = fetch_international_news()
    gs = "OK" if gold["success"] else "FAIL"
    log("汇总: 黄金[%s] 国内[%d] 国际[%d]" % (gs, len(dom), len(intl)))
    html = build_html(gold, gold_hist, dom, intl)
    ok = send_email(html)
    print()
    print("=" * 50)
    print("  每日新闻早报 - %s" % DATE_LABEL)
    print("  国际金价: $%s (%s%%)" % (gold["intl_price"], gold["intl_chg"]))
    print("  国内热点: %d条" % len(dom))
    print("  国际新闻: %d条" % len(intl))
    print("  邮件: %s" % ("OK" if ok else "FAIL"))
    print("=" * 50)


if __name__ == "__main__":
    main()
