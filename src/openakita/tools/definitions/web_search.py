"""
Web Search 工具定义

包含网络搜索相关的工具：
- web_search: 搜索网页
- news_search: 搜索新闻
"""

WEB_SEARCH_TOOLS = [
    {
        "name": "web_search",
        "category": "Web Search",
        "description": "使用 DuckDuckGo 搜索网页。当你需要：(1) 查找最新信息，(2) 验证事实，(3) 查阅文档，(4) 回答需要最新知识的问题。返回标题、URL 和摘要。",
        "detail": """使用 DuckDuckGo 搜索网页。

**适用场景**：
- 查找最新信息
- 验证事实
- 查阅文档
- 回答需要最新知识的问题

**参数说明**：
- query: 搜索关键词
- max_results: 最大结果数（1-20，默认 5）
- region: 地区代码（默认 wt-wt 全球，cn-zh 中国）
- safesearch: 安全搜索级别（on/moderate/off）

**示例**：
- 搜索信息：web_search(query="Python asyncio 教程", max_results=5)
- 搜索中文内容：web_search(query="天气预报", region="cn-zh")""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数（1-20，默认 5）",
                    "default": 5,
                },
                "region": {
                    "type": "string",
                    "description": "地区代码（默认 wt-wt 全球，cn-zh 中国）",
                    "default": "wt-wt",
                },
                "safesearch": {
                    "type": "string",
                    "description": "安全搜索级别（on/moderate/off）",
                    "default": "moderate",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "news_search",
        "category": "Web Search",
        "description": "使用 DuckDuckGo 搜索新闻。当你需要：(1) 查找最新新闻文章，(2) 了解时事动态，(3) 获取突发新闻。返回标题、来源、日期、URL 和摘要。",
        "detail": """使用 DuckDuckGo 搜索新闻。

**适用场景**：
- 查找最新新闻
- 了解时事动态
- 获取行业资讯

**参数说明**：
- query: 搜索关键词
- max_results: 最大结果数（1-20，默认 5）
- region: 地区代码
- safesearch: 安全搜索级别
- timelimit: 时间范围（d=一天, w=一周, m=一月）

**示例**：
- 搜索新闻：news_search(query="AI 最新进展", max_results=5)
- 搜索今日新闻：news_search(query="科技", timelimit="d")""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数（1-20，默认 5）",
                    "default": 5,
                },
                "region": {
                    "type": "string",
                    "description": "地区代码（默认 wt-wt 全球）",
                    "default": "wt-wt",
                },
                "safesearch": {
                    "type": "string",
                    "description": "安全搜索级别（on/moderate/off）",
                    "default": "moderate",
                },
                "timelimit": {
                    "type": "string",
                    "description": "时间范围（d=一天, w=一周, m=一月，默认不限）",
                },
            },
            "required": ["query"],
        },
    },
]
