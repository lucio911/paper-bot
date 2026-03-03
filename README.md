# ArXiv 论文日报机器人

全自动获取ArXiv最新AI论文并使用Gemini生成中文解读的机器人。

## 功能特性

- 自动从ArXiv获取最新论文（支持自定义主题）
- 使用Gemini API生成专业的中文论文解读
- 支持定时自动运行（GitHub Actions）
- 支持微信推送（PushPlus）

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/你的用户名/paper-bot.git
cd paper-bot

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置API Key

#### Gemini API Key
1. 访问 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 创建新的API Key
3. 在GitHub仓库设置中添加Secret:
   - Repository Settings -> Secrets and variables -> Actions
   - 新建Secret: `GOOGLE_API_KEY`

#### (可选) PushPlus微信推送
1. 访问 [PushPlus](http://www.pushplus.plus/)
2. 获取Token
3. 在GitHub Secrets中添加: `PUSHPLUS_TOKEN`

### 3. 本地测试

```bash
# 设置环境变量
export GOOGLE_API_KEY=你的API密钥  # Linux/Mac
set GOOGLE_API_KEY=你的API密钥    # Windows

# 运行脚本
python main.py
```

### 4. 部署到GitHub

1. 将代码推送到GitHub仓库
2. GitHub Actions会自动识别工作流
3. 每日UTC 0点自动运行（北京时区8点）

## 自定义配置

修改 `main.py` 中的参数：

```python
SEARCH_TOPICS = ["LLM", "large language model", "transformer", "GPT"]  # 搜索主题
MAX_RESULTS = 5  # 每个主题返回的论文数量
```

## 文件说明

```
paper_bot/
├── main.py                      # 主程序
├── requirements.txt             # Python依赖
├── .gitignore                   # Git忽略文件
├── .github/
│   └── workflows/
│       └── daily_paper_bot.yml  # GitHub Actions工作流
└── README.md                    # 说明文档
```

## 许可证

MIT License
