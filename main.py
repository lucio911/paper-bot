import os
import arxiv
import google.generativeai as genai
from datetime import datetime, timedelta
import requests

SEARCH_TOPICS = ["LLM", "large language model", "transformer", "GPT"]
MAX_RESULTS = 5

def get_latest_papers(topics=None, max_results=5):
    """从ArXiv获取最新论文"""
    if topics is None:
        topics = SEARCH_TOPICS
    
    client = arxiv.Client()
    papers = []
    
    for topic in topics:
        search = arxiv.Search(
            query=topic,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        for result in client.results(search):
            papers.append({
                'title': result.title,
                'summary': result.summary,
                'authors': [author.name for author in result.authors],
                'published': result.published.strftime('%Y-%m-%d'),
                'pdf_url': result.entry_id,
                'topic': topic
            })
    
    papers.sort(key=lambda x: x['published'], reverse=True)
    return papers[:max_results * len(topics)]

def generate_summary(paper, api_key=None):
    """调用Gemini API生成论文摘要"""
    if api_key:
        genai.configure(api_key=api_key)
    
    prompt = f"""你是一位专业的AI论文分析师。请仔细阅读以下论文信息，并提供详细的中文解读：

论文标题：{paper['title']}
作者：{', '.join(paper['authors'])}
发表日期：{paper['published']}
主题：{paper['topic']}

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
    
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    
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
        "title": "ArXiv论文日报",
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

def generate_daily_report(papers, summaries):
    """生成格式化日报"""
    report = []
    report.append("# ArXiv AI论文日报\n")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"论文数量: {len(papers)}\n")
    report.append("---\n")
    
    for i, (paper, summary) in enumerate(zip(papers, summaries), 1):
        report.append(f"## {i}. {paper['title']}\n")
        report.append(f"- **主题**: {paper['topic']}\n")
        report.append(f"- **作者**: {', '.join(paper['authors'][:3])}{'等' if len(paper['authors']) > 3 else ''}\n")
        report.append(f"- **发布日期**: {paper['published']}\n")
        report.append(f"- **PDF链接**: [点击查看]({paper['pdf_url']})\n")
        report.append("\n")
        report.append(summary)
        report.append("\n---\n")
    
    return ''.join(report)

def main():
    """主函数"""
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("警告: 未设置GOOGLE_API_KEY环境变量")
        print("请设置: set GOOGLE_API_KEY=你的API密钥")
        api_key = input("请输入Gemini API Key: ").strip()
    
    print("正在获取ArXiv最新论文...")
    papers = get_latest_papers(max_results=MAX_RESULTS)
    print(f"获取到 {len(papers)} 篇论文\n")
    
    print("正在生成论文解读...")
    summaries = []
    for i, paper in enumerate(papers, 1):
        print(f"  处理第 {i}/{len(papers)} 篇: {paper['title'][:50]}...")
        try:
            summary = generate_summary(paper, api_key)
            summaries.append(summary)
        except Exception as e:
            print(f"  生成摘要失败: {e}")
            summaries.append("摘要生成失败")
    
    report = generate_daily_report(papers, summaries)
    
    print("\n" + "="*50)
    print(report)
    print("="*50)
    
    send_wechat_notification(report)
    
    return report

if __name__ == "__main__":
    main()
