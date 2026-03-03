import os
import requests
import markdown
import time
import xml.etree.ElementTree as ET
from datetime import datetime

# ========== 配置区 ==========
ARXIV_KEYWORDS = [
    "geotechnical engineering",
    "soil mechanics",
    "slope stability",
    "tunneling underground",
    "pile foundation",
    "ground improvement",
    "rock mechanics",
    "consolidation settlement",
    "retaining wall",
    "liquefaction"
]
MAX_RESULTS = 1  # 每个关键词取1篇，共10篇

AI_API_URL = "https://apis.iflow.cn/v1/chat/completions"
AI_MODELS = ["deepseek-v3.2", "qwen3-max", "glm-4.6"]  # 依次尝试，互为备用
# ============================

ARXIV_API = "http://export.arxiv.org/api/query"


def get_latest_papers(keywords=None, max_results=1):
    """从arXiv按关键词获取最新岩土工程论文"""
    if keywords is None:
        keywords = ARXIV_KEYWORDS

    papers = []
    seen_titles = set()

    for kw in keywords:
        params = {
            "search_query": f"all:{kw}",
            "start": 0,
            "max_results": max_results + 2,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        try:
            response = requests.get(ARXIV_API, params=params, timeout=30)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                count = 0
                for entry in root.findall('atom:entry', ns):
                    title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                    # 去重
                    if title in seen_titles:
                        continue
                    abstract = entry.find('atom:summary', ns).text.strip()
                    if not abstract:
                        continue
                    published = entry.find('atom:published', ns).text[:10]
                    authors = [a.find('atom:name', ns).text
                               for a in entry.findall('atom:author', ns)]
                    link = entry.find('atom:id', ns).text
                    seen_titles.add(title)
                    papers.append({
                        'title': title,
                        'summary': abstract,
                        'authors': authors,
                        'published': published,
                        'pdf_url': link.replace('abs', 'pdf'),
                        'journal': kw,
                        'venue': 'arXiv'
                    })
                    count += 1
                    if count >= max_results:
                        break
            else:
                print(f"  arXiv 请求失败: {response.status_code}")
        except Exception as e:
            print(f"  获取关键词 '{kw}' 异常: {e}")

        time.sleep(1)

    papers.sort(key=lambda x: x['published'] or '', reverse=True)
    return papers


def call_ai_api(prompt, api_key):
    """调用AI API，依次尝试三个模型，互为备用"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500,
        "temperature": 0.7
    }

    for model in AI_MODELS:
        try:
            body["model"] = model
            response = requests.post(AI_API_URL, headers=headers, json=body, timeout=60)
            if response.status_code == 200:
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                print(f"    ✅ 使用模型: {model}")
                return text
            else:
                print(f"    ⚠️ {model} 失败 ({response.status_code})，尝试下一个...")
                time.sleep(2)
        except Exception as e:
            print(f"    ⚠️ {model} 异常: {e}，尝试下一个...")
            time.sleep(2)

    raise Exception("所有模型均调用失败")


def generate_summary(paper, api_key=None):
    """生成论文中文解读"""
    if not api_key:
        api_key = os.getenv('AI_API_KEY')

    prompt = f"""你是一位专业的土木工程/岩土工程论文分析师。请仔细阅读以下论文信息，并提供详细的中文解读：

论文标题：{paper['title']}
作者：{', '.join(paper['authors'][:5])}{'等' if len(paper['authors']) > 5 else ''}
发表日期：{paper['published']}
关键词分类：{paper['journal']}

原文摘要：
{paper['summary']}

请提供以下格式的中文解读：
1. 【核心贡献】一句话概括论文的主要创新点
2. 【技术方法】论文采用的关键技术或方法
3. 【实验结果】主要实验结论和性能指标
4. 【应用场景】该研究的潜在应用领域
5. 【阅读建议】适合什么层次的读者，是否值得深入阅读

请用Markdown格式输出。
"""
    return call_ai_api(prompt, api_key)


def send_wechat_notification(message, token=None):
    """通过PushPlus发送微信通知"""
    if not token:
        token = os.getenv('PUSHPLUS_TOKEN')
    if not token:
        print("未配置PushPlus Token，跳过微信推送")
        return

    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": "岩土工程论文日报",
        "content": message,
        "template": "html"
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print("微信推送成功")
        else:
            print(f"微信推送失败: {response.text}")
    except Exception as e:
        print(f"微信推送异常: {e}")


def send_email_notification(message):
    """通过Gmail SMTP发送邮件"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_server = os.getenv('SMTP_SERVER') or 'smtp.gmail.com'
    smtp_port = int(os.getenv('SMTP_PORT') or '587')
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    email_from = os.getenv('EMAIL_FROM') or smtp_user
    email_to = os.getenv('EMAIL_TO')

    if not all([smtp_user, smtp_password, email_to]):
        print("未配置邮箱推送，跳过（需设置 SMTP_USER, SMTP_PASSWORD, EMAIL_TO）")
        return

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'岩土工程论文日报 {datetime.now().strftime("%Y-%m-%d")}'
        msg['From'] = email_from
        msg['To'] = email_to
        msg.attach(MIMEText(message, 'html', 'utf-8'))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print("邮箱推送成功")
    except smtplib.SMTPAuthenticationError:
        print("❌ 认证失败：Gmail必须使用App Password，而非账号密码")
        print("   路径：Google账号 → 安全 → 开启两步验证 → 搜索 App passwords → 生成16位密码")
    except Exception as e:
        print(f"邮箱推送失败: {e}")


def generate_daily_report(papers, summaries):
    """生成格式化HTML日报"""
    report = []
    report.append("<h1>岩土工程论文日报</h1>\n")
    report.append(f"<p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
    report.append(f"<p>论文数量: {len(papers)}</p>\n")
    report.append("<hr>\n")

    for i, (paper, summary) in enumerate(zip(papers, summaries), 1):
        report.append(f"<h2>{i}. {paper['title']}</h2>\n")
        report.append(f"<p><strong>关键词:</strong> {paper['journal']}</p>\n")
        authors_str = ', '.join(paper['authors'][:3])
        if len(paper['authors']) > 3:
            authors_str += ' 等'
        report.append(f"<p><strong>作者:</strong> {authors_str}</p>\n")
        report.append(f"<p><strong>发布日期:</strong> {paper['published']}</p>\n")
        report.append(f"<p><strong>链接:</strong> <a href=\"{paper['pdf_url']}\">点击查看原文(PDF)</a></p>\n")
        report.append("<br>\n")
        report.append(markdown.markdown(summary))
        report.append("<hr>\n")

    return ''.join(report)


def main():
    """主函数"""
    api_key = os.getenv('AI_API_KEY')
    if not api_key:
        print("警告: 未设置AI_API_KEY环境变量")
        api_key = input("请输入API Key: ").strip()

    print("正在从arXiv获取最新岩土工程论文...")
    papers = get_latest_papers(max_results=MAX_RESULTS)
    print(f"获取到 {len(papers)} 篇论文\n")

    if not papers:
        print("未获取到任何论文，请检查网络连接")
        return

    print("正在生成论文解读...")
    summaries = []
    for i, paper in enumerate(papers, 1):
        title_short = paper['title'][:50] + "..." if len(paper['title']) > 50 else paper['title']
        print(f"  处理第 {i}/{len(papers)} 篇: {title_short}")
        try:
            summary = generate_summary(paper, api_key)
            summaries.append(summary)
        except Exception as e:
            print(f"  生成摘要失败: {e}")
            summaries.append("**摘要生成失败**")
        time.sleep(2)

    report = generate_daily_report(papers, summaries)

    print("\n" + "=" * 50)
    print(report)
    print("=" * 50)

    send_wechat_notification(report)
    send_email_notification(report)

    return report


if __name__ == "__main__":
    main()
