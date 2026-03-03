import os
import requests
import markdown
import time
from google import genai
from datetime import datetime

SEARCH_JOURNALS = [
    "Construction and Building Materials",
    "Transportation Geotechnics",
    "Engineering Failure Analysis",
    "Canadian Geotechnical Journal",
    "Tunnelling and Underground Space Technology",
    "Ocean Engineering",
    "Computers and Geotechnics",
    "Engineering Applications of Artificial Intelligence",
    "Computer-Aided Civil and Infrastructure Engineering",
    "Computers & Industrial Engineering"
]

MAX_RESULTS = 1  # 免费tier每天20次，10个期刊×1篇=10次，安全

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"

SKIP_KEYWORDS = [
    'Corrigendum', 'Expression of concern', 'Cover Image',
    'Erratum', 'Retraction', 'Editorial'
]


def get_latest_papers(journals=None, max_results=1):
    """从Semantic Scholar按期刊获取最新论文"""
    if journals is None:
        journals = SEARCH_JOURNALS

    papers = []

    for journal in journals:
        params = {
            "query": journal,
            "limit": max_results + 3,  # 多取几篇，过滤后保证有足够数量
            "fields": "title,authors,year,venue,abstract,url,publicationDate",
        }

        for retry in range(3):
            try:
                response = requests.get(SEMANTIC_SCHOLAR_API, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    count = 0
                    for item in data.get("data", []):
                        title = item.get('title', '')
                        # 跳过勘误、声明、封面等无意义条目
                        if any(kw in title for kw in SKIP_KEYWORDS):
                            continue
                        # 跳过没有摘要的
                        if not item.get('abstract'):
                            continue
                        papers.append({
                            'title': title,
                            'summary': item.get('abstract', '无摘要'),
                            'authors': [a.get('name', '') for a in item.get('authors', [])],
                            'published': item.get('publicationDate') or str(item.get('year', '')),
                            'pdf_url': item.get('url', ''),
                            'journal': journal,
                            'venue': item.get('venue', journal)
                        })
                        count += 1
                        if count >= max_results:
                            break
                    break
                elif response.status_code == 429:
                    print(f"  速率限制，等待重试 ({retry+1}/3)...")
                    time.sleep(10)
                else:
                    print(f"  获取期刊 {journal} 失败: {response.status_code}")
                    break
            except Exception as e:
                print(f"  获取期刊 {journal} 异常: {e}")
                break

        time.sleep(2)  # 每个期刊请求间隔2秒

    papers.sort(key=lambda x: x['published'] or '', reverse=True)
    return papers


def generate_summary(paper, api_key=None):
    """调用Gemini API生成论文摘要"""
    client = genai.Client(api_key=api_key or os.getenv('GOOGLE_API_KEY'))

    prompt = f"""你是一位专业的土木工程/岩土工程论文分析师。请仔细阅读以下论文信息，并提供详细的中文解读：

论文标题：{paper['title']}
作者：{', '.join(paper['authors'][:5])}{'等' if len(paper['authors']) > 5 else ''}
发表日期：{paper['published']}
期刊：{paper['journal']}

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

    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    time.sleep(4)  # 避免超出免费tier速率限制
    return response.text


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

        html_part = MIMEText(message, 'html', 'utf-8')
        msg.attach(html_part)

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
        report.append(f"<p><strong>期刊:</strong> {paper['journal']}</p>\n")
        authors_str = ', '.join(paper['authors'][:3])
        if len(paper['authors']) > 3:
            authors_str += ' 等'
        report.append(f"<p><strong>作者:</strong> {authors_str}</p>\n")
        report.append(f"<p><strong>发布日期:</strong> {paper['published']}</p>\n")
        report.append(f"<p><strong>链接:</strong> <a href=\"{paper['pdf_url']}\">点击查看原文</a></p>\n")
        report.append("<br>\n")
        report.append(markdown.markdown(summary))
        report.append("<hr>\n")

    return ''.join(report)


def main():
    """主函数"""
    api_key = os.getenv('GOOGLE_API_KEY')

    if not api_key:
        print("警告: 未设置GOOGLE_API_KEY环境变量")
        api_key = input("请输入Gemini API Key: ").strip()

    print("正在获取各期刊最新论文...")
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

    report = generate_daily_report(papers, summaries)

    print("\n" + "=" * 50)
    print(report)
    print("=" * 50)

    send_wechat_notification(report)
    send_email_notification(report)

    return report


if __name__ == "__main__":
    main()
