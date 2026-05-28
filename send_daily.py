#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily news digest: fetch news + gold, send HTML email via QQ SMTP"""

import requests, re, json, os, smtplib, xml.etree.ElementTree as ET
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ===== Config from env vars =====
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_TO = os.environ.get('SMTP_TO', SMTP_USER)

# ===== Beijing time =====
BJ_TZ = timezone(timedelta(hours=8))
now = datetime.now(BJ_TZ)
DATE_LABEL = now.strftime('%Y年%m月%d日')
WEEKDAYS = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
WEEKDAY = WEEKDAYS[now.weekday()]

S = requests.Session()
S.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept-Language': 'zh-CN,zh;q=0.9'})
TIMEOUT = 15

def log(msg):
    ts = datetime.now(BJ_TZ).strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')

# === Gold price ===
def fetch_gold_price():
    r = {'success':False,'intl_price':'--','intl_chg':'--','dom_price':'--','dom_chg':'--','update':'--'}
    try:
        resp = S.get('https://hq.sinajs.cn/list=xauusd', timeout=TIMEOUT)
        resp.encoding='gbk'
        m = re.search(r'"(.*?)"', resp.text)
        if m and len(m.group(1).split(','))>=5:
            p = m.group(1).split(',')
            r['intl_price'], r['intl_chg'] = p[1], p[4]
            r['success'] = True
            log(f'国际金价: ${p[1]} ({p[4]}%)')
    except Exception as e:
        log(f'国际金价失败: {e}')
    try:
        resp = S.get('https://hq.sinajs.cn/list=au9999', timeout=TIMEOUT)
        resp.encoding='gbk'
        m = re.search(r'"(.*?)"', resp.text)
        if m and len(m.group(1).split(','))>=5:
            p = m.group(1).split(',')
            r['dom_price'], r['dom_chg'] = p[1], p[4]
            log(f'国内金价: {p[1]}元/克 ({p[4]}%)')
    except Exception as e:
        log(f'国内金价失败: {e}')
    r['update'] = now.strftime('%H:%M')
    return r

# === Domestic news (Baidu + Weibo) ===
def fetch_domestic_news():
    news = []
    try:
        resp = S.get('https://top.baidu.com/api/board?tab=realtime', timeout=TIMEOUT)
        data = resp.json()
        for card in data.get('data',{}).get('cards',[]):
            for item in card.get('content',[]):
                title = item.get('word','') or item.get('query','')
                if title: news.append({'title':title,'source':'百度热搜'})
        log(f'百度热搜: {len(news)}条')
    except Exception as e:
        log(f'百度热搜失败: {e}')
    try:
        resp = S.get('https://weibo.com/ajax/side/hotSearch', timeout=TIMEOUT)
        data = resp.json()
        titles = {n['title'] for n in news}
        for item in data.get('data',{}).get('realtime',[])[:10]:
            title = item.get('word','')
            if title and title not in titles:
                news.append({'title':title,'source':'微博热搜'})
                titles.add(title)
        log('微博热搜已补充')
    except:
        pass
    return news

# === International news (BBC RSS) ===
def fetch_international_news():
    news = []
    for url, label in [
        ('https://www.bbc.com/zhongwen/simp/world/index.xml', 'BBC中文'),
        ('https://feedx.net/rss/bbc-zh.xml', 'BBC中文(备)'),
    ]:
        try:
            resp = S.get(url, timeout=TIMEOUT)
            root = ET.fromstring(resp.content)
            for item in root.iter('item'):
                title = item.findtext('title','')
                if title and len(title)>5:
                    news.append({'title':title.strip(),'source':label})
                    if len(news)>=30: break
            log(f'{label}: {sum(1 for n in news if n["source"]==label)}条')
            break
        except Exception as e:
            log(f'{label}失败: {e}')
    return news[:30]

# === Build HTML from template ===
def build_html(gold, dom_news, intl_news):
    # Read template
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tmpl_path = os.path.join(script_dir, 'email_template.html')
    with open(tmpl_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Gold direction
    up = False; down = False
    try:
        chg = float(gold['intl_chg'])
        if chg>0: up=True
        elif chg<0: down=True
    except: pass
    icon = '&#x1f4c8;' if up else ('&#x1f4c9;' if down else '&#x27a1;')
    color = '#e74c3c' if up else ('#27ae60' if down else '#7f8c8d')
    sign = '+' if up else ('-' if down else '')

    # Build news rows
    def make_rows(items, max_n=12):
        rows = ''
        emojis = ['&#x1f4cc;','&#x1f525;','&#x1f4a1;','&#x1f4e2;','&#x2b50;','&#x1f514;','&#x1f4ac;','&#x1f4f0;','&#x1f5de;','&#x26a1;','&#x1f4ce;','&#x1f4aa;']
        for i, item in enumerate(items[:max_n]):
            badge = '<span style="background:#e8f0fe;color:#1967d2;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px">'+item['source']+'</span>'
            rows += '<tr><td style="padding:10px 16px;border-bottom:1px solid #f0f0f0;font-size:15px;line-height:1.6;color:#333">'+emojis[i%len(emojis)]+' '+item['title']+badge+'</td></tr>'
        return rows

    html = html.replace('__TITLE__', '每日新闻早报')
    html = html.replace('__DATE__', DATE_LABEL)
    html = html.replace('__WEEKDAY__', WEEKDAY)
    html = html.replace('__GOLD_TITLE__', '现货黄金行情')
    html = html.replace('__GOLD_INTL_LABEL__', '国际金价 (美元/盎司)')
    html = html.replace('__GOLD_DOM_LABEL__', '国内金价 (人民币/克)')
    html = html.replace('__GOLD_INTL_PRICE__', '$' + gold['intl_price'])
    html = html.replace('__GOLD_INTL_CHANGE__', gold['intl_chg'])
    html = html.replace('__GOLD_DOM_PRICE__', gold['dom_price'])
    html = html.replace('__GOLD_DOM_UNIT__', '元/克')
    html = html.replace('__GOLD_COLOR__', color)
    html = html.replace('__GOLD_ICON__', icon)
    html = html.replace('__GOLD_CHANGE_SIGN__', sign)
    html = html.replace('__GOLD_UPDATE__', '更新时间: ' + gold['update'])
    html = html.replace('__DOM_TITLE__', '国内热点')
    html = html.replace('__INTL_TITLE__', '国际新闻')
    html = html.replace('__DOM_NEWS__', make_rows(dom_news, 15))
    html = html.replace('__INTL_NEWS__', make_rows(intl_news, 15))
    html = html.replace('__FOOTER_AUTO__', '每日早7:00 自动推送')
    html = html.replace('__FOOTER_GEN__', 'Generated by')
    html = html.replace('__FOOTER_DATE__', DATE_LABEL)
    return html

# === Send email ===
def send_email(html):
    if not SMTP_USER or not SMTP_PASS:
        log('SMTP未配置，跳过邮件发送')
        return False
    msg = MIMEMultipart('alternative')
    msg['From'] = SMTP_USER
    msg['To'] = SMTP_TO
    subject = f'每日新闻早报 | {DATE_LABEL} {WEEKDAY}'
    msg['Subject'] = Header(subject, 'utf-8')
    msg.attach(MIMEText('每日新闻早报 - ' + DATE_LABEL + '\n请在支持HTML的邮件客户端中查看。', 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    try:
        log('连接QQ邮箱SMTP...')
        s = smtplib.SMTP_SSL('smtp.qq.com', 465, timeout=30)
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [SMTP_TO], msg.as_string())
        s.quit()
        log(f'邮件已发送 -> {SMTP_TO}')
        return True
    except Exception as e:
        log(f'邮件发送失败: {e}')
        return False

# === Main ===
def main():
    log(f'===== 新闻早报 {DATE_LABEL} {WEEKDAY} =====')
    gold = fetch_gold_price()
    dom = fetch_domestic_news()
    intl = fetch_international_news()
    status = 'OK' if gold['success'] else 'FAIL'
    log(f'汇总: 黄金[{status}] 国内[{len(dom)}] 国际[{len(intl)}]')
    html = build_html(gold, dom, intl)
    ok = send_email(html)
    print()
    print('='*50)
    print(f'  每日新闻早报 - {DATE_LABEL}')
    print('  国际金价: $' + gold['intl_price'] + ' (' + gold['intl_chg'] + '%)')
    print(f'  国内热点: {len(dom)}条')
    print(f'  国际新闻: {len(intl)}条')
    m_status = 'OK' if ok else 'FAIL'
    print(f'  邮件: {m_status}')
    print('='*50)

if __name__ == '__main__':
    main()