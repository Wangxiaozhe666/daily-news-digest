# 📰 小管的MSG - AI前沿 + 抖音热榜 + 财经资讯

每天早上7:00（北京时间），自动采集 **国内热点新闻、国际新闻、现货黄金行情**，生成精美HTML邮件发送到你的QQ邮箱。

所有代码在 GitHub 云端运行，**你的电脑无需开机**，24小时在线。

---

## 目录结构

```
daily-news-digest/
├── .github/workflows/daily.yml   # GitHub Actions 定时任务
├── send_daily.py                  # 主脚本（采集+生成+发送）
├── email_template.html            # 邮件HTML模板
├── requirements.txt               # Python 依赖
└── README.md                      # 本说明文件
```

---

## 数据来源

| 数据 | 来源 |
|------|------|
| 国内热点 | 百度热搜 |
| 国际新闻 | BBC RSS |
| 现货黄金(国际) | 新浪财经 (XAU/USD) |
| 现货黄金(国内) | 黄金ETF (sh518880) |
| 美元/人民币 | 新浪财经 |
| 天气 | wttr.in (苏州) |
| 🤖 AI前沿 | HackerNews + arXiv cs.AI |
| 🔥 抖音热榜 | 抖音官方热搜API |

---

## 部署步骤（只需3步）

### 第1步：创建 GitHub 仓库

1. 打开 https://github.com/new
2. **Repository name** 输入：`daily-news-digest`
3. 选择 **Public**（公开）或 **Private**（私有）都可以
4. 点击 **Create repository**
5. 创建后不用动，保持空白页面即可

### 第2步：上传代码到仓库

**方法A - 网页上传（最简单）**

1. 在新仓库页面，点击 **uploading an existing file**
2. 把所有文件拖进去上传
3. 底部点击 **Commit changes**

**方法B - 命令行上传**
```bash
# 如果电脑上装了Git
cd D:\daily-news-digest
git init
git add .
git commit -m "Initial commit: daily news digest"
git remote add origin https://github.com/你的用户名/daily-news-digest.git
git push -u origin main
```

### 第3步：配置仓库 Secrets（关键！）

1. 在仓库页面点击 **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**，添加以下3个：

| Name | Value |
|------|-------|
| `SMTP_USER` | `1065155319@qq.com` |
| `SMTP_PASS` | `你的QQ邮箱SMTP授权码` |
| `SMTP_TO` | `1065155319@qq.com` |

> 💡 SMTP授权码获取方式：
> QQ邮箱 → 设置 → 账户 → POP3/IMAP/SMTP服务 → 开启 → 生成授权码

3. 添加完毕后，页面应该显示3个 Secrets

### 第4步：验证运行

1. 点击仓库顶部的 **Actions** 标签
2. 左侧看到 **Daily News Digest**
3. 点击 **Daily News Digest** → **Run workflow** → 绿色按钮
4. 等待1-2分钟，任务完成
5. 检查你的QQ邮箱是否收到邮件！

> 每天早上7:00（北京时间），任务会自动运行，无需任何操作。

---

## 手动触发测试

任何时候想测试，都可以：
1. 打开你的仓库 https://github.com/你的用户名/daily-news-digest
2. Actions → Daily News Digest → **Run workflow** → 绿色按钮
3. 等待执行完毕，查收邮件

---

## 如何关闭

如果以后不需要了：
1. 进入仓库 Settings → Actions → General
2. 在 **Actions permissions** 选择 **Disable actions**
3. 或者直接删除仓库

---

## 邮件效果预览

邮件采用淡蓝色主题，包含：
- 📌 顶部：日期 + 星期
- 🥇 现货黄金行情卡片（国际/国内价格、涨跌、更新时间）
- 🇨🇳 国内热点新闻列表
- 🌏 国际新闻列表
- 📱 适配手机和电脑查看

