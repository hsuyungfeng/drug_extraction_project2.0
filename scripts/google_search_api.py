import pandas as pd
import logging
import os
import re
import json
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入项目配置
from config.project_config import INPUT_CSV, GOOGLE_SEARCH_RESULTS_CSV

# --- Configuration ---
LOG_FILE = "logs/google_search.log"

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

    # 嘗試解析模擬數據的文本格式
    if "適應症：" in summary_text and "用法用量：" in summary_text and "注意事項：" in summary_text:
        # 模擬數據格式：這是 {query} 的搜尋結果摘要。適應症：...用法用量：...注意事項：...
        try:
            # 使用正則表達式提取信息
            indication_match = re.search(r'適應症[：:]\s*(.*?)(?=用法用量|注意事項|$)', summary_text)
            dosage_match = re.search(r'用法用量[：:]\s*(.*?)(?=注意事項|$)', summary_text)
            precaution_match = re.search(r'注意事項[：:]\s*(.*?)$', summary_text)
            
            if indication_match:
                info["適應症"] = indication_match.group(1).strip()[:150]
            if dosage_match:
                info["用法用量"] = dosage_match.group(1).strip()[:150]
            if precaution_match:
                info["注意事項"] = precaution_match.group(1).strip()[:150]
                
            return info
        except Exception:
            pass

    # 如果沒有 JSON 或模擬數據格式，嘗試解析 Markdown 格式
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

def google_web_search_api(query):
    """
    使用 Google Custom Search JSON API 進行搜尋
    需要設置 GOOGLE_API_KEY 和 GOOGLE_CX 環境變數
    """
    import requests
    import os
    
    api_key = os.getenv('GOOGLE_API_KEY')
    cx = os.getenv('GOOGLE_CX')
    
    if not api_key or not cx:
        logger.warning("Google API credentials not found. Using mock data for demonstration.")
        return {
            "success": True,
            "content": f"這是 {query} 的搜尋結果摘要。適應症：用於治療相關症狀。用法用量：請遵照醫師指示。注意事項：請詳閱說明書。"
        }
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': cx,
            'q': query,
            'num': 3  # 獲取前3個結果
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        items = data.get('items', [])
        
        # 從搜尋結果中提取資訊
        content = ""
        for i, item in enumerate(items[:3], 1):
            content += f"結果 {i}: {item.get('title', '無標題')}\n"
            content += f"摘要: {item.get('snippet', '無摘要')}\n\n"
        
        return {
            "success": True,
            "content": content[:1000]  # 限制內容長度
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Google API request failed: {e}")
        return {"success": False, "content": ""}
    except Exception as e:
        logger.error(f"Unexpected error in Google search: {e}")
        return {"success": False, "content": ""}

def main():
    """主函數：使用 Google 搜尋 API 進行藥物資訊提取"""
    logger.info("Starting Google search integration")
    
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

    results = []

    # 迭代處理每一種藥物（示範模式：只處理前5種）
    for index, row in input_df.head(5).iterrows():
        drug_name = row['藥品中文名稱']
        drug_code = row.get('藥品代號', 'N/A')
        logger.info(f"Searching for: {drug_code} - {drug_name}")

        # 構建搜尋查詢
        search_query = f"{drug_name} 適應症 用法用量 注意事項"

        try:
            # 使用 Google 搜尋 API 進行搜尋
            logger.info(f"Executing Google search for: {search_query}")
            
            # 調用 Google 搜尋 API
            search_result = google_web_search_api(search_query)
            
            if search_result["success"]:
                # 解析搜尋結果
                extracted_info = parse_google_summary(search_result["content"])
                
                # 保存結果
                results.append({
                    "藥品代號": drug_code,
                    "藥品中文名稱": drug_name,
                    "適應症": extracted_info["適應症"],
                    "用法用量": extracted_info["用法用量"],
                    "注意事項": extracted_info["注意事項"],
                })
                logger.info(f"Successfully processed {drug_name}")
            else:
                logger.error(f"Google search failed for {drug_name}")
                results.append({
                    "藥品代號": drug_code,
                    "藥品中文名稱": drug_name,
                    "適應症": "搜尋失敗",
                    "用法用量": "搜尋失敗",
                    "注意事項": "搜尋失敗",
                })

        except Exception as e:
            logger.error(f"Failed to process {drug_name} with error: {e}")
            results.append({
                "藥品代號": drug_code,
                "藥品中文名稱": drug_name,
                "適應症": "處理錯誤",
                "用法用量": "處理錯誤",
                "注意事項": "處理錯誤",
            })

    # 將所有結果保存到 CSV 文件
    if results:
        df_output = pd.DataFrame(results)
        
        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(GOOGLE_SEARCH_RESULTS_CSV), exist_ok=True)
        
        df_output.to_csv(GOOGLE_SEARCH_RESULTS_CSV, index=False, encoding='utf-8')
        logger.info(f"Saved {len(results)} search results to {GOOGLE_SEARCH_RESULTS_CSV}")
        
        # 顯示前幾行結果
        logger.info("Sample results:")
        for i, result in enumerate(results[:3]):
            logger.info(f"Result {i+1}: {result}")
    else:
        logger.warning("No results were processed and saved.")

    logger.info("Google search process completed")

if __name__ == "__main__":
    # 確保日誌目錄存在
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    main()
