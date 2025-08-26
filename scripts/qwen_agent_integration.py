import pandas as pd
import logging
import os
import re
import time
import json
from typing import Dict, List, Optional
from qwen_agent.agents import Assistant
from qwen_agent.llm.schema import Message

# --- Configuration ---
INPUT_CSV = "data/sample_drugs.csv"
OUTPUT_CSV = "output/google_search_results.csv"
LOG_FILE = "logs/qwen_agent.log"
ERROR_LOG_FILE = "logs/qwen_agent_errors.log"
CACHE_FILE = "output/qwen_agent_cache.json"

# --- Setup Logging ---
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(os.path.dirname(ERROR_LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
        logging.FileHandler(ERROR_LOG_FILE, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_cache() -> Dict[str, Dict]:
    """載入處理緩存"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
    return {}

def save_cache(cache: Dict[str, Dict]):
    """保存處理緩存"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")

def parse_google_summary(summary_text: str) -> Dict[str, str]:
    """從 Google 搜尋的 AI 摘要中解析出我們需要的資訊"""
    info = {"適應症": "", "用法用量": "", "注意事項": ""}
    
    if not summary_text or summary_text.strip() == "":
        return info

    # 多種解析策略
    patterns = [
        # 策略1: Markdown格式 (## 1. 適應症（Indications）)
        (r'##\s*\d+\.\s*(適應症|用法用量|注意事項)[^\n]*\n(.*?)(?=\n##|\Z)', re.DOTALL),
        # 策略2: Markdown格式 (### **標題**)
        (r'### \*\*(.*?)\*\*\n(.*?)(?=\n###|\Z)', re.DOTALL),
        # 策略3: 簡單標題格式
        (r'(適應症|用法用量|注意事項)[:：]?\s*(.*?)(?=\n|$)', re.IGNORECASE),
        # 策略4: 中文標題
        (r'(【(適應症|用法用量|注意事項)】)\s*(.*?)(?=\n【|$)', re.DOTALL),
        # 策略5: 數字標題格式 (1. 適應症)
        (r'(\d+\.\s*(適應症|用法用量|注意事項))\s*(.*?)(?=\n\d+\.|$)', re.IGNORECASE | re.DOTALL),
        # 策略6: 冒號分隔格式
        (r'(適應症|用法用量|注意事項)\s*[:：]\s*(.*?)(?=\n|$)', re.IGNORECASE)
    ]
    
    for pattern, flags in patterns:
        try:
            matches = re.findall(pattern, summary_text, flags)
            for match in matches:
                if len(match) == 2:
                    title, content = match
                elif len(match) == 3:
                    _, title, content = match
                elif len(match) == 4:
                    _, _, title, content = match
                else:
                    continue
                
                title = title.strip().lower()
                content = content.strip().replace('\n', ' ')
                
                if '適應症' in title or 'indication' in title or 'indications' in title:
                    info['適應症'] = content[:200] if content else "資訊不足"
                elif '用法用量' in title or 'dosage' in title or '劑量' in title or 'administration' in title:
                    info['用法用量'] = content[:200] if content else "資訊不足"
                elif '注意事項' in title or 'precaution' in title or 'warning' in title or 'precautions' in title:
                    info['注意事項'] = content[:200] if content else "資訊不足"
                    
        except Exception as e:
            logger.debug(f"Pattern {pattern} failed: {e}")
            continue
    
    # 如果所有欄位都為空，嘗試直接提取關鍵信息
    if all(not value for value in info.values()):
        direct_patterns = {
            "適應症": r'(用於|治療|適用於)[^。]*?[。\n]',
            "用法用量": r'(每次|每日|劑量)[^。]*?[。\n]',
            "注意事項": r'(禁忌|注意|警告)[^。]*?[。\n]'
        }
        
        for key, pattern in direct_patterns.items():
            matches = re.findall(pattern, summary_text, re.IGNORECASE)
            if matches:
                info[key] = matches[0][:200]

    return info

def initialize_qwen_agent() -> Optional[object]:
    """初始化 Qwen LLM（直接使用LLM避免Assistant的bug）"""
    try:
        from qwen_agent.llm import get_chat_model
        
        # 使用本地Ollama模型 - 使用Ollama原生API端點
        llm_config = {
            'model': 'gpt-oss:20b',  # 直接使用模型名稱
            'model_server': 'http://localhost:11434',  # Ollama默认端口
            'api_base': 'http://localhost:11434/v1',  # 使用Ollama的OpenAI兼容端點
            'api_type': 'open_ai',  # 使用open_ai API類型
            'generate_cfg': {'temperature': 0.1}
        }
        
        llm = get_chat_model(llm_config)
        logger.info("Qwen LLM initialized successfully")
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize Qwen LLM: {e}")
        return None

def search_with_retry(llm: object, search_query: str, max_retries: int = 3) -> Optional[str]:
    """帶重試機制的搜尋函數（直接使用LLM）"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Search attempt {attempt + 1} for: {search_query}")
            
            # 直接使用LLM進行搜索查詢
            prompt = f'''請搜索以下藥品資訊並返回包含以下內容的詳細摘要：

藥品名稱：{search_query}

請搜索並提供：
1. 適應症（Indications）- 主要治療用途
2. 用法用量（Dosage and Administration）- 具體使用方法和劑量
3. 注意事項（Precautions）- 使用禁忌和注意事項

請以繁體中文返回結構化的詳細資訊。'''
            
            # 使用非流式響應以避免超時問題
            response = llm.chat([{'role': 'user', 'content': prompt}], stream=False)
            
            # 提取搜尋結果 - 處理生成器響應
            result_text = ""
            if hasattr(response, '__iter__') and not isinstance(response, str):
                # 如果是生成器，迭代獲取所有內容
                try:
                    for chunk in response:
                        logger.debug(f"Chunk type: {type(chunk)}, value: {chunk}")
                        # 處理不同類型的響應塊 - 特別處理列表格式的chunk
                        if isinstance(chunk, list):
                            # 列表中的每個元素可能是字典
                            for item in chunk:
                                if isinstance(item, dict):
                                    if 'content' in item:
                                        result_text += str(item['content'])
                                    elif 'text' in item:
                                        result_text += str(item['text'])
                                    elif 'output' in item:
                                        result_text += str(item['output'])
                                elif hasattr(item, 'content'):
                                    result_text += str(item.content)
                                elif hasattr(item, 'output'):
                                    result_text += str(item.output)
                                elif isinstance(item, str):
                                    result_text += item
                                else:
                                    result_text += str(item)
                        elif isinstance(chunk, dict):
                            if 'content' in chunk:
                                result_text += str(chunk['content'])
                            elif 'text' in chunk:
                                result_text += str(chunk['text'])
                            elif 'output' in chunk:
                                result_text += str(chunk['output'])
                        elif hasattr(chunk, 'content'):
                            result_text += str(chunk.content)
                        elif hasattr(chunk, 'output'):
                            result_text += str(chunk.output)
                        elif isinstance(chunk, str):
                            result_text += chunk
                        else:
                            result_text += str(chunk)
                except Exception as e:
                    logger.error(f"Error iterating generator response: {e}")
                    # 嘗試直接調用LLM的chat方法
                    try:
                        direct_response = llm.chat([{'role': 'user', 'content': prompt}], stream=False)
                        if hasattr(direct_response, 'output'):
                            result_text = direct_response.output
                        elif isinstance(direct_response, dict) and 'content' in direct_response:
                            result_text = direct_response['content']
                        else:
                            result_text = str(direct_response)
                    except Exception as inner_e:
                        logger.error(f"Direct chat also failed: {inner_e}")
                        result_text = ""
            elif hasattr(response, 'output'):
                result_text = response.output
            elif isinstance(response, dict) and 'content' in response:
                result_text = response['content']
            elif isinstance(response, str):
                result_text = response
            else:
                # 嘗試轉換為字符串
                result_text = str(response)
                logger.debug(f"Response converted to string: {result_text[:200]}...")
            
            # 如果結果是列表格式，轉換為字符串
            if isinstance(result_text, list):
                result_text = ' '.join([str(item) for item in result_text])
            
            # 保存原始搜索結果用於調試
            debug_dir = "logs/debug"
            os.makedirs(debug_dir, exist_ok=True)
            # 清理文件名中的非法字符
            safe_query = re.sub(r'[<>:"/\\|?*]', '_', search_query[:20])
            debug_file = os.path.join(debug_dir, f"search_debug_{safe_query}.txt")
            
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(f"Search Query: {search_query}\n")
                    f.write(f"Result: {result_text}\n")
                logger.info(f"Debug info saved to: {debug_file}")
            except Exception as e:
                logger.error(f"Failed to save debug file: {e}")
            
            logger.debug(f"Raw search result: {result_text[:200]}...")
            return result_text
                
        except Exception as e:
            import traceback
            logger.warning(f"Search attempt {attempt + 1} failed: {e}")
            logger.debug(f"Exception details: {traceback.format_exc()}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指數退避
            else:
                logger.error(f"All search attempts failed for: {search_query}")
                return None
    
    return None

def main():
    """主函數：使用 Qwen-Agent 進行 Google 搜尋和資訊提取"""
    logger.info("Starting Qwen-Agent Google search integration")
    
    # 載入緩存
    cache = load_cache()
    
    # 初始化 Qwen-Agent
    agent = initialize_qwen_agent()
    if not agent:
        return

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
    processed_count = 0

    # 迭代處理每一種藥物
    for index, row in input_df.iterrows():
        drug_name = row['藥品中文名稱']
        drug_code = row.get('藥品代號', 'N/A')
        
        # 檢查緩存
        cache_key = f"{drug_code}_{drug_name}"
        if cache_key in cache:
            logger.info(f"Using cached results for: {drug_code} - {drug_name}")
            results.append(cache[cache_key])
            continue

        logger.info(f"Processing: {drug_code} - {drug_name}")

        # 構建搜尋查詢
        search_query = f"{drug_name} 適應症 用法用量 注意事項 台灣"

        try:
            # 使用 Qwen LLM 進行搜尋
            search_result_text = search_with_retry(agent, search_query)
            
            if not search_result_text:
                raise Exception("Search returned no results")

            logger.info(f"Received search results for {drug_name}")

            # 解析搜尋結果
            extracted_info = parse_google_summary(search_result_text)

            # 構建結果
            result = {
                "藥品代號": drug_code,
                "藥品中文名稱": drug_name,
                "適應症": extracted_info["適應症"] or "資訊不足",
                "用法用量": extracted_info["用法用量"] or "資訊不足",
                "注意事項": extracted_info["注意事項"] or "資訊不足",
            }

            # 保存到緩存
            cache[cache_key] = result
            results.append(result)
            
            processed_count += 1
            logger.info(f"Successfully processed {drug_name}")
            
            # 每處理10個藥物保存一次緩存
            if processed_count % 10 == 0:
                save_cache(cache)
                logger.info(f"Checkpoint: Processed {processed_count} drugs")

        except Exception as e:
            logger.error(f"Failed to process {drug_name} with error: {e}")
            
            # 錯誤結果
            error_result = {
                "藥品代號": drug_code,
                "藥品中文名稱": drug_name,
                "適應症": "搜尋失敗",
                "用法用量": "搜尋失敗",
                "注意事項": "搜尋失敗",
            }
            
            cache[cache_key] = error_result
            results.append(error_result)

    # 將所有結果保存到 CSV 文件
    if results:
        df_output = pd.DataFrame(results)
        
        # 讀取原始數據來合併完整資訊
        try:
            original_df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig', keep_default_na=False)
            
            # 合併結果：以藥品代號為鍵，將Qwen-Agent結果合併到原始數據
            merged_df = original_df.merge(
                df_output, 
                on=['藥品代號', '藥品中文名稱'], 
                how='left',
                suffixes=('', '_qwen')
            )
            
            # 優先使用Qwen-Agent提取的資訊，如果沒有則保持原樣
            for col in ['適應症', '用法用量', '注意事項']:
                # 處理輸入文件可能沒有這些欄位的情況
                if col in merged_df.columns:
                    merged_df[col] = merged_df.get(f'{col}_qwen', merged_df[col])
                else:
                    merged_df[col] = merged_df.get(f'{col}_qwen', '')
                if f'{col}_qwen' in merged_df.columns:
                    merged_df.drop(columns=[f'{col}_qwen'], inplace=True)
            
            # 確保輸出目錄存在
            os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
            
            # 保存最終結果（與drug_info_extracted_final.csv格式一致）
            merged_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
            
        except Exception as e:
            logger.error(f"Failed to merge with original data: {e}")
            # 如果合併失敗，只保存Qwen-Agent結果
            os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
            df_output.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        
        # 保存緩存
        save_cache(cache)
        
        # 統計信息
        success_count = sum(1 for r in results if r["適應症"] not in ["搜尋失敗", "資訊不足"])
        failure_count = sum(1 for r in results if r["適應症"] == "搜尋失敗")
        incomplete_count = sum(1 for r in results if r["適應症"] == "資訊不足")
        
        logger.info(f"Processing completed:")
        logger.info(f"- Total drugs processed: {len(results)}")
        logger.info(f"- Successfully extracted: {success_count}")
        logger.info(f"- Search failures: {failure_count}")
        logger.info(f"- Incomplete information: {incomplete_count}")
        logger.info(f"- Results saved to: {OUTPUT_CSV}")
        
        # 顯示統計摘要
        if success_count > 0:
            logger.info("Sample successful results:")
            successful_results = [r for r in results if r["適應症"] not in ["搜尋失敗", "資訊不足"]][:3]
            for i, result in enumerate(successful_results):
                logger.info(f"Success {i+1}: {result['藥品中文名稱']} - {result['適應症'][:50]}...")
    else:
        logger.warning("No results were processed and saved.")

    logger.info("Qwen-Agent integration process completed")

if __name__ == "__main__":
    # 確保日誌目錄存在
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    main()
