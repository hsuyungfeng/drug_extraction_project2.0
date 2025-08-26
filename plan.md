## 重新设计的项目进程（基于您的文档）

### 阶段一：环境准备和基础安装（1-2天）

__目标__：建立完整的工作环境

```bash
# 1. 创建虚拟环境  使用 uv 
uv venv .venv
source .venv/bin/activate

# 2. 安装核心依赖（与您现有项目兼容）
pip install pandas requests beautifulsoup4 ollama PyMuPDF

# 3. 安装 Qwen-Agent（只需要库，不需要拉取源码）
pip install qwen-agent

# 4. 安装 Crawl4AI（只需要库）
pip install crawl4ai

# 5. 验证安装
python -c "import qwen_agent; import crawl4ai; print('所有库安装成功')"
```

### 阶段二：Qwen-Agent 集成（2-3天）

__目标__：将 Qwen-Agent 集成到现有的两步流程中

创建 `qwen_agent_integration.py`：

```python
import pandas as pd
import logging
from qwen_agent.agents import Assistant
import json
import re

class DrugResearchAgent:
    def __init__(self):
        # 使用本地 Ollama 模型，避免需要 API 密钥
        self.agent = Assistant(
            llm='ollama/gpt-oss:20b',  # 使用您现有的本地模型
            function_list=['google_web_search'],
            instructions='您是专业的药品信息研究助手，负责从网络抓取药品信息'
        )
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("qwen_agent.log"),
                logging.StreamHandler()
            ]
        )
    
    def parse_google_summary(self, summary_text: str) -> dict:
        """解析 Google 搜索结果的 AI 摘要"""
        info = {"適應症": "", "用法用量": "", "注意事項": ""}
        if not summary_text:
            return info
        
        # 使用正则表达式提取信息
        patterns = {
            "適應症": r"(適應症|主治|用途)[:：]?\s*(.*?)(?=\n|$)",
            "用法用量": r"(用法用量|劑量|服用方法)[:：]?\s*(.*?)(?=\n|$)", 
            "注意事項": r"(注意事項|禁忌|警告)[:：]?\s*(.*?)(?=\n|$)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, summary_text, re.IGNORECASE)
            if match:
                info[key] = match.group(2).strip()[:150]
        
        return info
    
    async def process_drugs(self, input_csv, output_csv, limit=10):
        """处理药品列表"""
        try:
            df = pd.read_csv(input_csv, encoding='utf-8-sig')
            results = []
            
            for index, row in df.head(limit).iterrows():
                drug_name = row['藥品中文名稱']
                drug_code = row.get('藥品代號', '')
                
                logging.info(f"处理药品: {drug_code} - {drug_name}")
                
                # 使用 Qwen-Agent 进行搜索
                prompt = f"请搜索药品 '{drug_name}' 的适应症、用法用量和注意事项"
                
                try:
                    response = self.agent.run(prompt)
                    extracted_info = self.parse_google_summary(str(response))
                    
                    results.append({
                        "藥品代號": drug_code,
                        "藥品中文名稱": drug_name,
                        **extracted_info
                    })
                    
                except Exception as e:
                    logging.error(f"处理药品 {drug_name} 时出错: {e}")
                    results.append({
                        "藥品代號": drug_code,
                        "藥品中文名稱": drug_name,
                        "適應症": "搜索失败",
                        "用法用量": "搜索失败", 
                        "注意事項": "搜索失败"
                    })
            
            # 保存结果
            result_df = pd.DataFrame(results)
            result_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
            logging.info(f"保存 {len(results)} 条结果到 {output_csv}")
            
        except Exception as e:
            logging.error(f"处理CSV文件时出错: {e}")

# 使用示例
async def main():
    agent = DrugResearchAgent()
    await agent.process_drugs("uncomplete-research.csv", "google_search_results.csv", limit=5)
```

### 阶段三：Crawl4AI 增强抓取（2-3天）

__目标__：使用 Crawl4AI 增强现有的 TFDA/NHI 抓取功能

修改 `multi_source_drug_scraper.py`：

```python
# 在现有代码基础上添加 Crawl4AI 集成
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

async def enhanced_tfda_scrape(drug_name, manufacturer):
    """使用 Crawl4AI 增强 TFDA 数据抓取"""
    async with AsyncWebCrawler() as crawler:
        config = CrawlerRunConfig(
            cache_mode="BYPASS",
            verbose=False
        )
        
        # 构建 TFDA API 查询
        tfda_url = f"https://data.fda.gov.tw/opendata/exportDataList.do?method=openData&InfoId=36&q={drug_name}"
        
        result = await crawler.arun(url=tfda_url, config=config)
        return result.html if result.success else ""
```

### 阶段四：完整流程测试（1-2天）

__目标__：测试完整的自动化流程

```bash
# 1. 运行 Qwen-Agent 步骤
python qwen_agent_integration.py

# 2. 运行主处理脚本（会自动读取 google_search_results.csv）
python multi_source_drug_scraper.py
```

## 回答您的两个问题

### 1. 需要额外拉取 Qwen-Agent 和 Crawl4AI 档案吗？

__不需要拉取源码档案，只需要安装库就可以！__

- __Qwen-Agent__: 只需要 `pip install qwen-agent`，不需要克隆 GitHub 仓库
- __Crawl4AI__: 只需要 `pip install crawl4ai`，不需要拉取源码

### 2. 为什么只需要安装库？

__原因如下：__

1. __标准化安装__: 两个项目都提供了完善的 PyPI 包，包含所有必要功能
2. __依赖管理__: 通过 pip 安装会自动处理所有依赖关系
3. __版本控制__: 可以轻松升级和管理版本
4. __简化部署__: 不需要维护源码，减少复杂性
5. __文档完整__: 官方库包含完整的API文档和示例

### 安装后的文件结构

```javascript
drug_project/
├── .venv/                    # 虚拟环境
├── 1140816健保用藥品項查詢項目檔_健保用藥品項.csv
├── uncomplete-research.csv
├── google_search_results.csv
├── drug_info_extracted_final.csv
├── multi_source_drug_scraper.py    # 修改后的主脚本
├── qwen_agent_integration.py       # 新的Qwen-Agent集成
├── requirements.txt
└── 各种日志文件
```

## 关键优势

1. __保持现有架构__: 完全兼容您现有的两步流程
2. __最小化改动__: 只需要添加新的集成文件，不需要重写现有代码
3. __无额外配置__: 使用本地 Ollama，避免 API 密钥配置
4. __渐进式集成__: 可以逐步测试和部署新功能
