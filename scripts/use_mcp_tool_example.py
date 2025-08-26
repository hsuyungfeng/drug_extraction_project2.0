import pandas as pd
import logging
import os
import re
import json

# --- Configuration ---
INPUT_CSV = "data/uncomplete-research.csv"
OUTPUT_CSV = "output/google_search_results.csv"
LOG_FILE = "logs/mcp_tool_usage.log"

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_google_summary(summary_text):
    """從 Google 搜尋的 AI 摘要中解析出我們需要的資訊"""
    info = {"適應症": "", "用法用量": "", "注意事項": ""}
    if not summary_text:
        return info

    # 嘗試解析 JSON 格式的響應
    try:
        if isinstance(summary_text, str) and summary_text.strip().startswith('{'):
            data = json.loads(summary_text)
            info["適應症"] = data.get("適應症", "")[:150]
            info["用法用量"] = data.get("用法用量", "")[:150]
            info["注意事項"] = data.get("注意事項", "")[:150]
            return info
    except json.JSONDecodeError:
        pass

    # 如果沒有 JSON，嘗試解析文本格式
    pattern = re.compile(r'### \*\*(.*?)\*\*\n(.*?)(?=\n###|\Z)', re.DOTALL)
    matches = pattern.findall(summary_text)

    for title, content in matches:
        title = title.strip()
        content = content.strip().replace('\n', ' ')
        if '適應症' in title:
            info['適應症'] = content
        elif '用法用量' in title or '劑量' in title:
            info['用法用量'] = content
        elif '注意事項' in title:
            info['注意事項'] = content
            
    for key, value in info.items():
        info[key] = value.strip()[:150]  # 限制長度

    return info

def main():
    """主函數：展示如何使用 MCP 工具進行 Google 搜尋"""
    logger.info("Starting MCP tool usage demonstration")
    
    # 讀取輸入文件
    try:
        input_df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig', keep_default_na=False)
        logger.info(f"Successfully read input file: {INPUT_CSV}")
    except FileNotFoundError:
        logger.error(f"Input file not found: {INPUT_CSV}")
        return
    except Exception as e:
        logger.error(f"Error reading input file: {e}")
        return

    if '藥品中文名稱' not in input_df.columns:
        logger.error(f"Input file {INPUT_CSV} must contain a '藥品中文名稱' column.")
        return

    # 選擇前5種藥物進行示範
    demo_drugs = input_df.head(5)
    
    logger.info("MCP Tool Usage Instructions:")
    logger.info("=" * 50)
    
    for index, row in demo_drugs.iterrows():
        drug_name = row['藥品中文名稱']
        drug_code = row.get('藥品代號', 'N/A')
        
        # 構建搜尋查詢
        search_query = f"{drug_name} 適應症 用法用量 注意事項"
        
        logger.info(f"\nDrug: {drug_code} - {drug_name}")
        logger.info(f"Search Query: {search_query}")
        
        # 顯示 MCP 工具使用格式
        logger.info("MCP Tool Usage Format:")
        logger.info('''<use_mcp_tool>
<server_name>google-search-server</server_name>
<tool_name>google_web_search</tool_name>
<arguments>
{
  "query": "%s",
  "max_results": 5
}
</arguments>
</use_mcp_tool>''' % search_query)
        
        logger.info("-" * 30)

    logger.info("\nExpected MCP Response Format:")
    logger.info('''{
  "success": true,
  "results": [
    {
      "title": "藥品名稱 - 適應症與用法",
      "snippet": "適應症：用於治療... 用法用量：成人每次... 注意事項：請勿與...",
      "url": "https://example.com/drug-info"
    }
  ],
  "ai_summary": "### **適應症**\\n用於治療相關症狀\\n\\n### **用法用量**\\n請遵照醫師指示\\n\\n### **注意事項**\\n請詳閱說明書"
}''')

    # 解析示例響應
    example_response = {
        "success": True,
        "results": [
            {
                "title": "鹽酸麻黃錠 - 藥品資訊",
                "snippet": "適應症：支氣管氣喘、過敏性鼻炎 用法用量：成人每次1-2錠 注意事項：高血壓患者慎用",
                "url": "https://example.com/drug-info"
            }
        ],
        "ai_summary": "### **適應症**\n支氣管氣喘、血管運動性鼻炎、過敏性鼻炎\n\n### **用法用量**\n成人每次1至2錠（25-50mg），必要時每3至4小時一次。\n\n### **注意事項**\n禁忌症：若患有嚴重高血壓、冠狀動脈疾病、狹角性青光眼，或正在服用MAO抑制劑者，禁止使用本藥。"
    }

    logger.info("\nExample Parsing Result:")
    extracted_info = parse_google_summary(example_response["ai_summary"])
    logger.info(f"適應症: {extracted_info['適應症']}")
    logger.info(f"用法用量: {extracted_info['用法用量']}")
    logger.info(f"注意事項: {extracted_info['注意事項']}")

    logger.info("\nTo use MCP tools in practice:")
    logger.info("1. Ensure MCP servers are running and configured")
    logger.info("2. Use the <use_mcp_tool> XML format as shown above")
    logger.info("3. Parse the response using the parse_google_summary function")
    logger.info("4. Save results to CSV format")

if __name__ == "__main__":
    # 確保日誌目錄存在
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    main()
