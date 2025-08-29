#!/usr/bin/env python3
"""
多来源药物信息提取脚本
从TFDA、NHI和Google搜索结果中提取药物信息
使用本地LLM进行信息解析
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import logging
import random
import os
import sys
import ollama
import json
import re
import fitz  # PyMuPDF
import io
from pathlib import Path

# 导入项目配置
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.project_config import (
    INPUT_CSV, OUTPUT_CSV, INCOMPLETE_OUTPUT_CSV, GOOGLE_SEARCH_RESULTS_CSV,
    REQUEST_TIMEOUT, MODEL, IS_DEMO, DEMO_LIMIT, BATCH_SIZE, SOURCE_URLS
)

# 導入新的搜索庫
try:
    from googlesearch import search as google_search
    import trafilatura
    HAS_SEARCH_LIBS = True
except ImportError:
    HAS_SEARCH_LIBS = False
    logging.warning("搜索庫未安裝，請運行: uv pip install googlesearch-python trafilatura")

# 设置日志
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "multi_source_extraction.log", mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def scrape_tfda(drug_name: str, manufacturer: str, ingredient: str) -> str:
    """从TFDA抓取药物信息"""
    logging.info(f"尝试从TFDA抓取: {drug_name}")
    tfda_api_url = SOURCE_URLS["TFDA"]
    params = {
        'method': 'openData',
        'InfoId': '36'
    }
    
    # 重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(tfda_api_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # 檢查 Content-Type 是否為 JSON
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                # 記錄錯誤 HTML 內容到 debug 文件
                debug_dir = Path("logs/debug")
                debug_dir.mkdir(exist_ok=True)
                error_file = debug_dir / f"tfda_error_{drug_name}.html"
                with open(error_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logging.warning(f"TFDA 返回非JSON內容，已保存到 {error_file}")
                return ""
            
            all_drugs_data_raw = response.json()
            
            all_drugs_data = all_drugs_data_raw

            if isinstance(all_drugs_data, list) and len(all_drugs_data) > 0:
                pass
            else:
                return ""

            found_info = []
            if isinstance(all_drugs_data, list):
                for drug_entry in all_drugs_data:
                    if not isinstance(drug_entry, dict):
                        continue

                    entry_c_name = drug_entry.get('中文品名', '').lower().replace(' ', '')
                    entry_e_name = drug_entry.get('英文品名', '').lower().replace(' ', '')
                    entry_manuf = drug_entry.get('製造廠名稱', '').lower().replace(' ', '')
                    entry_app_manuf = drug_entry.get('申請商名稱', '').lower().replace(' ', '')

                    search_drug_name = drug_name.lower().replace(' ', '')
                    search_manufacturer = manufacturer.lower().replace(' ', '')
                    search_ingredient = ingredient.lower().replace(' ', '')

                    name_match = (search_drug_name and (search_drug_name in entry_c_name or search_drug_name in entry_e_name))
                    manuf_match = (search_manufacturer and (search_manufacturer in entry_manuf or search_manufacturer in entry_app_manuf))
                    
                    ingredient_match = (search_ingredient and search_ingredient in drug_entry.get('成份', '').lower().replace(' ', ''))

                    if (name_match and manuf_match) or (name_match and ingredient_match):
                        info_parts = []
                        info_parts.append(f"中文品名: {drug_entry.get('中文品名', '資訊不足')}")
                        info_parts.append(f"英文品名: {drug_entry.get('英文品名', '資訊不足')}")
                        info_parts.append(f"許可證字號: {drug_entry.get('許可證字號', '資訊不足')}")
                        info_parts.append(f"申請商名稱: {drug_entry.get('申請商名稱', '資訊不足')}")
                        info_parts.append(f"製造廠名稱: {drug_entry.get('製造廠名稱', '資訊不足')}")
                        info_parts.append(f"適應症: {drug_entry.get('適應症', '資訊不足')}")
                        info_parts.append(f"用法用量: {drug_entry.get('用法用量', '資訊不足')}")
                        info_parts.append(f"注意事項: {drug_entry.get('注意事項', '資訊不足')}")
                        found_info.append("\n".join(info_parts))
                        if found_info:
                            logging.info(f"找到TFDA数据: {drug_name}")
                            return "\n\n".join(found_info)

            if not found_info:
                logging.info(f"TFDA中未找到相关数据: {drug_name}")
            return "\n\n".join(found_info)

        except requests.exceptions.Timeout:
            logging.warning(f"TFDA请求超时 (尝试 {attempt + 1}/{max_retries}): {drug_name}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
                continue
            else:
                logging.error(f"TFDA抓取超时 {drug_name}: 超过最大重试次数")
                return ""
                
        except requests.exceptions.ConnectionError:
            logging.warning(f"TFDA连接错误 (尝试 {attempt + 1}/{max_retries}): {drug_name}")
            if attempt < max_retries - 1:
                time.sleep(3)  # 等待3秒后重试
                continue
            else:
                logging.error(f"TFDA连接失败 {drug_name}: 超过最大重试次数")
                return ""
                
        except json.JSONDecodeError:
            logging.error(f"TFDA JSON 解析失敗: {drug_name}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 等待1秒后重试
                continue
            else:
                return ""
                
        except Exception as e:
            logging.error(f"TFDA抓取失败 {drug_name}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 等待1秒后重试
                continue
            else:
                return ""
    
    return ""

def update_extraction_status(status: dict, result: dict) -> dict:
    """更新提取狀態字典"""
    for field in ['適應症', '用法用量', '注意事項']:
        if result.get(field, '') not in ['', '資訊不足', '模型提取失敗', '模型回傳格式錯誤']:
            status[field] = True
    return status

def process_drug_with_five_steps(drug_info: dict, google_results_df: pd.DataFrame) -> dict:
    """五步法藥物信息提取流程"""
    drug_name = drug_info.get('藥品中文名稱', '')
    drug_code = drug_info.get('藥品代號', '')
    manufacturer = drug_info.get('製造廠名稱', '')
    ingredient = drug_info.get('成份', '')
    
    # 初始化狀態和結果
    status = {
        '適應症': False,
        '用法用量': False,
        '注意事項': False
    }
    result = {}
    
    logging.info(f"開始五步法處理: {drug_code} - {drug_name}")
    
    # 第1步: 檢查Google搜索結果 (中文名搜索)
    if not all(status.values()) and not google_results_df.empty and drug_code in google_results_df.index:
        logging.info(f"第1步: 使用Google搜索結果 (中文名)")
        google_info = google_results_df.loc[drug_code]
        result.update({
            "適應症": google_info.get("適應症", ""),
            "用法用量": google_info.get("用法用量", ""),
            "注意事項": google_info.get("注意事項", "")
        })
        status = update_extraction_status(status, result)
    
    # 第2步: TFDA API (修復後)
    if not all(status.values()):
        logging.info(f"第2步: 嘗試TFDA API")
        tfda_content = scrape_tfda(drug_name, manufacturer, ingredient)
        if tfda_content:
            tfda_result = extract_info_with_llm(tfda_content, drug_name, "tfda_api")
            result.update(tfda_result)
            status = update_extraction_status(status, result)
    
    # 第3步: 中文名搜索
    if not all(status.values()) and HAS_SEARCH_LIBS:
        logging.info(f"第3步: 中文名搜索")
        chinese_result = step3_chinese_search(drug_info)
        if chinese_result:
            result.update(chinese_result)
            status = update_extraction_status(status, result)
    
    # 第4步: 英文名搜索
    if not all(status.values()) and HAS_SEARCH_LIBS:
        logging.info(f"第4步: 英文名搜索")
        english_result = step4_english_search(drug_info)
        if english_result:
            result.update(english_result)
            status = update_extraction_status(status, result)
    
    # 第5步: 成分搜索
    if not all(status.values()) and HAS_SEARCH_LIBS:
        logging.info(f"第5步: 成分搜索")
        ingredient_result = step5_ingredient_search(drug_info)
        if ingredient_result:
            result.update(ingredient_result)
            status = update_extraction_status(status, result)
    
    # 如果仍有缺失字段，使用當前邏輯作為備用
    if not all(status.values()):
        logging.info(f"使用備用方案處理缺失字段")
        # 保持現有備用邏輯
        
    logging.info(f"五步法處理完成: 適應症={status['適應症']}, 用法用量={status['用法用量']}, 注意事項={status['注意事項']}")
    return result

def search_and_extract_web_content(query: str, drug_name: str, search_type: str) -> dict:
    """搜索並提取網頁內容"""
    logging.info(f"執行 {search_type} 搜索: {query}")
    
    try:
        # 構建搜索查詢 - 針對不同搜索類型優化關鍵詞
        if search_type == "ingredient_search":
            search_query = query
        elif search_type == "chinese_search":
            # 中文搜索加強用法用量相關關鍵詞
            search_query = f"{query} 用法 用量 劑量 服用方法 適應症 副作用 禁忌"
        elif search_type == "english_search":
            # 英文搜索使用更專業的醫學術語
            search_query = f"{query} dosage administration contraindications side effects"
        else:
            search_query = f"{query} 適應症 用法用量 注意事項"
        
        urls = []
        
        # 方法1: 使用googlesearch-python (如果可用)
        if HAS_SEARCH_LIBS:
            try:
                for url in google_search(search_query, num_results=3, lang="zh-tw", timeout=5):
                    urls.append(url)
                    if len(urls) >= 3:
                        break
            except Exception as e:
                logging.warning(f"Google搜索庫失敗: {e}")
        
        # 方法2: 備用搜索方法 - 直接訪問醫療網站
        if not urls and search_type != "ingredient_search":
            # 嘗試直接訪問台灣常見醫療資訊網站
            backup_urls = [
                f"https://www.google.com/search?q={search_query.replace(' ', '+')}&hl=zh-tw",
                f"https://tw.search.yahoo.com/search?p={search_query.replace(' ', '+')}",
                f"https://www.drugs.com/search.php?searchterm={query.replace(' ', '+')}",
                f"https://www.google.com/search?q=site:pharmknow.com {query.replace(' ', '+')}",
                f"https://www.google.com/search?q=site:tcm.tw {query.replace(' ', '+')}",
                f"https://www.google.com/search?q=site:vghtpe.gov.tw {query.replace(' ', '+')}"
            ]
            urls = backup_urls
        
        if not urls:
            logging.warning(f"{search_type} 搜索無結果: {query}")
            return {}
        
        # 提取網頁內容
        combined_content = ""
        for i, url in enumerate(urls):
            try:
                # 設置用戶代理頭
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # 檢查URL類型
                if url.endswith('.pdf'):
                    # PDF文件，跳過處理
                    logging.info(f"跳過PDF文件: {url}")
                    continue
                
                if HAS_SEARCH_LIBS:
                    try:
                        # 使用trafilatura提取 (不傳遞headers)
                        downloaded = trafilatura.fetch_url(url)
                        if downloaded:
                            content = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
                            if content:
                                combined_content += f"--- 來源 {i+1}: {url} ---\n{content[:1000]}\n\n"
                    except Exception as e:
                        logging.warning(f"trafilatura提取失敗 {url}: {e}")
                        # 備用方法
                        try:
                            # 加入隨機延遲避免被檢測為爬蟲
                            time.sleep(random.uniform(1, 3))
                            response = requests.get(url, headers=headers, timeout=10)
                            if response.status_code == 200:
                                soup = BeautifulSoup(response.text, 'html.parser')
                                for script in soup(["script", "style"]):
                                    script.decompose()
                                text = soup.get_text()
                                lines = (line.strip() for line in text.splitlines())
                                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                                text = ' '.join(chunk for chunk in chunks if chunk)
                                if text:
                                    combined_content += f"--- 來源 {i+1}: {url} ---\n{text[:1000]}\n\n"
                        except Exception as e2:
                            logging.warning(f"備用提取也失敗 {url}: {e2}")
                else:
                    # 備用方法: 直接requests + BeautifulSoup
                    try:
                        # 加入隨機延遲避免被檢測為爬蟲
                        time.sleep(random.uniform(1, 3))
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            for script in soup(["script", "style"]):
                                script.decompose()
                            text = soup.get_text()
                            lines = (line.strip() for line in text.splitlines())
                            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                            text = ' '.join(chunk for chunk in chunks if chunk)
                            if text:
                                combined_content += f"--- 來源 {i+1}: {url} ---\n{text[:1000]}\n\n"
                    except Exception as e:
                        logging.warning(f"提取網頁內容失敗 {url}: {e}")
                        
            except Exception as e:
                logging.warning(f"提取網頁內容失敗 {url}: {e}")
        
        if not combined_content:
            logging.warning(f"無法提取 {search_type} 搜索內容: {query}")
            return {}
        
        # 使用LLM提取信息
        return extract_info_with_llm(combined_content, drug_name, search_type)
        
    except Exception as e:
        logging.error(f"{search_type} 搜索失敗 {query}: {e}")
        return {}

def step3_chinese_search(drug_info: dict) -> dict:
    """第3步: 中文名搜索"""
    drug_name = drug_info.get('藥品中文名稱', '')
    if not drug_name:
        return {}
    
    return search_and_extract_web_content(drug_name, drug_name, "chinese_search")

def step4_english_search(drug_info: dict) -> dict:
    """第4步: 英文名搜索"""
    english_name = drug_info.get('藥品英文名稱', '')
    drug_name = drug_info.get('藥品中文名稱', '')
    
    if not english_name:
        return {}
    
    return search_and_extract_web_content(english_name, drug_name, "english_search")

def step5_ingredient_search(drug_info: dict) -> dict:
    """第5步: 成分搜索"""
    ingredient = drug_info.get('成份', '')
    drug_name = drug_info.get('藥品中文名稱', '')
    
    if not ingredient:
        return {}
    
    # 優先搜索權威醫療網站
    authority_sites = "site:drugs.com OR site:medscape.com OR site:webmd.com"
    query = f"{ingredient} prescribing information dosage {authority_sites}"
    
    return search_and_extract_web_content(query, drug_name, "ingredient_search")

def scrape_nhi(drug_name: str, manufacturer: str, ingredient: str) -> str:
    """从NHI抓取药物信息"""
    logging.info(f"尝试从NHI抓取: {drug_name}")
    nhi_download_url = SOURCE_URLS["NHI_DATA_DOWNLOAD"]
    
    try:
        response = requests.get(nhi_download_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        nhi_df = pd.read_csv(io.StringIO(response.text), encoding='utf-8', on_bad_lines='skip')
        
        search_drug_name_lower = drug_name.lower().replace(' ', '')
        search_ingredient_lower = ingredient.lower().replace(' ', '')
        search_manufacturer_lower = manufacturer.lower().replace(' ', '')

        filtered_df = nhi_df[
            (nhi_df['藥品中文名稱'].fillna('').str.lower().str.replace(' ', '').str.contains(search_drug_name_lower)) | 
            (nhi_df['成份'].fillna('').str.lower().str.replace(' ', '').str.contains(search_ingredient_lower)) | 
            (nhi_df['製造廠名稱'].fillna('').str.lower().str.replace(' ', '').str.contains(search_manufacturer_lower))
        ]
        
        found_info = []
        if not filtered_df.empty:
            for index, row in filtered_df.iterrows():
                info_parts = []
                info_parts.append(f"健保代碼: {row.get('藥品代號', '資訊不足')}")
                info_parts.append(f"給付資訊: {row.get('參考價', '資訊不足')}")
                info_parts.append(f"劑型: {row.get('劑型', '資訊不足')}")
                found_info.append("\n".join(info_parts))
            if found_info:
                logging.info(f"找到NHI数据: {drug_name}")
                return "\n\n".join(found_info)
        
        logging.info(f"NHI中未找到相关数据: {drug_name}")
        return ""

    except Exception as e:
        logging.error(f"NHI抓取失败: {e}")
        return ""

def extract_info_with_llm(text_content: str, drug_name: str, search_type: str = "general") -> dict:
    """使用本地LLM提取信息"""
    if not text_content:
        return {"適應症": "", "用法用量": "", "注意事項": ""}

    logging.info(f"使用 {MODEL} 提取信息: {drug_name} ({search_type})")
    
    # 根據搜索類型調整提示詞
    if search_type == "ingredient_translation":
        prompt = f'''你是藥品資訊提取和翻譯助手。請將以下英文藥理資訊翻譯成台灣繁體中文，並從中提取：
- 適應症（主治）
- 用法及用量（劑量）
- 注意事項（含禁忌）

嚴格遵守以下規則：
1. 先將英文內容翻譯成台灣繁體中文
2. 從翻譯後的內容中提取資訊
3. 每個欄位的回答必須少於100個字元
4. 如果資訊不存在，在該欄位回答「資訊不足」
5. 輸出格式為 JSON

英文內容：
{text_content[:4000]}'''
    else:
        prompt = f'''你是藥品資訊提取助手。從以下內容提取：
- 適應症（主治、治療什麼疾病）
- 用法用量（怎麼服用、一次多少劑量、一天幾次、飯前或飯後）
- 注意事項（副作用、禁忌、注意什麼）

特別注意用法用量的提取，請尋找：服用方法、劑量、頻率、時間等資訊。

嚴格遵守以下規則：
1. 以台灣繁體中文簡潔地回答。
2. 每個欄位的回答都必須少於100個字元。
3. 如果找不到明確的用法用量，請尋找任何劑量相關資訊。
4. 如果資訊完全不存在，在該欄位回答「資訊不足」。
5. 輸出格式為 JSON，使用以下格式：{{"適應症": "...", "用法用量": "...", "注意事項": "..."}}

內容：
{text_content[:4000]}'''

    try:
        response = ollama.generate(model=MODEL, prompt=prompt)
        resp_text = response['response'].strip()
        
        if resp_text.startswith('{') and resp_text.endswith('}'):
            data = json.loads(resp_text)
        else:
            json_match = re.search(r'```json(.*?)```', resp_text, re.DOTALL)
            if not json_match:
                logging.error(f"LLM返回格式错误 {drug_name}: {resp_text}")
                return {"適應症": "模型回傳格式錯誤", "用法用量": "模型回傳格式錯誤", "注意事項": "模型回傳格式錯誤"}

            json_str = json_match.group(1).strip()
            data = json.loads(json_str)
        
        for key in ["適應症", "用法用量", "注意事項"]:
            data[key] = data.get(key, "資訊不足")[:100]
        return data
    except Exception as e:
        logging.error(f"LLM提取失败 {drug_name}: {e}")
        return {"適應症": "模型提取失敗", "用法用量": "模型提取失敗", "注意事項": "模型提取失敗"}

def main():
    """主函数"""
    logging.info("=" * 60)
    logging.info("多来源药物信息提取开始")
    logging.info("=" * 60)
    
    try:
        input_df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig', keep_default_na=False)
    except FileNotFoundError:
        logging.error(f"输入文件不存在: {INPUT_CSV}")
        return
    except Exception as e:
        logging.error(f"读取输入文件失败: {e}")
        return

    # 加载Google搜索结果
    google_results_df = pd.DataFrame()
    if os.path.exists(GOOGLE_SEARCH_RESULTS_CSV):
        logging.info(f"加载Google搜索结果: {GOOGLE_SEARCH_RESULTS_CSV}")
        try:
            google_results_df = pd.read_csv(GOOGLE_SEARCH_RESULTS_CSV, encoding='utf-8-sig', keep_default_na=False)
            if '藥品代號' in google_results_df.columns:
                google_results_df.set_index('藥品代號', inplace=True)
            else:
                logging.warning("Google搜索结果缺少藥品代號列")
                google_results_df = pd.DataFrame()
        except Exception as e:
            logging.error(f"加载Google搜索结果失败: {e}")
            google_results_df = pd.DataFrame()

    # 检查现有输出文件
    output_columns = input_df.columns.tolist() + ['適應症', '用法用量', '注意事項']
    
    output_df = pd.DataFrame(columns=output_columns)
    incomplete_df = pd.DataFrame(columns=output_columns)
    
    if os.path.exists(OUTPUT_CSV):
        output_df = pd.read_csv(OUTPUT_CSV, encoding='utf-8-sig', keep_default_na=False)
    if os.path.exists(INCOMPLETE_OUTPUT_CSV):
        incomplete_df = pd.read_csv(INCOMPLETE_OUTPUT_CSV, encoding='utf-8-sig', keep_default_na=False)

    # 确定需要处理的药物
    all_existing_data = pd.concat([output_df, incomplete_df]).drop_duplicates(subset=['藥品代號'], keep='first')
    processed_drug_codes = set(all_existing_data['藥品代號'].tolist())
    drugs_to_process_df = input_df[~input_df['藥品代號'].isin(processed_drug_codes)].copy()

    # 生产模式下分批处理
    if IS_DEMO:
        limit = DEMO_LIMIT
        batch_size = DEMO_LIMIT
    else:
        limit = len(drugs_to_process_df)
        batch_size = BATCH_SIZE  # 生产模式每批处理数量
    
    # 计算当前批次
    total_batches = (limit + batch_size - 1) // batch_size
    current_batch = 1
    
    processed_drugs_batch = []
    incomplete_drugs_batch = []
    
    for batch_start in range(0, limit, batch_size):
        batch_end = min(batch_start + batch_size, limit)
        current_batch_df = drugs_to_process_df.iloc[batch_start:batch_end]
        
        logging.info(f"=== 处理批次 {current_batch}/{total_batches} ({len(current_batch_df)} 种药物) ===")
        
        for index, row in current_batch_df.iterrows():
            drug_code = row.get('藥品代號', '')
            drug_name = row.get('藥品中文名稱', '')
            logging.info(f"--- 处理药物: {drug_code} - {drug_name} ---")
            
            manufacturer = row.get('製造廠名稱', '')
            ingredient = row.get('成份', '')

            if not all([drug_name, manufacturer, ingredient]):
                logging.warning(f"跳过 {drug_code}: 关键信息缺失")
                current_row_data = row.to_dict()
                for col in ['適應症', '用法用量', '注意事項']:
                    current_row_data[col] = "資訊不足 - 關鍵資訊缺失"
                incomplete_drugs_batch.append(current_row_data)
                continue

            # 使用五步法處理藥物信息
            web_info = process_drug_with_five_steps(row.to_dict(), google_results_df)
            
            # 檢查信息是否完整
            all_fields_complete = all(web_info.get(col, "") not in ["", "資訊不足", "模型提取失敗", "模型回傳格式錯誤"] for col in ['適應症', '用法用量', '注意事項'])

            # 保存结果
            current_row_data = row.to_dict()
            for key, value in web_info.items():
                current_row_data[key] = value

            if all_fields_complete:
                processed_drugs_batch.append(current_row_data)
                logging.info(f"成功处理: {drug_code}")
            else:
                incomplete_drugs_batch.append(current_row_data)
                logging.info(f"信息不完整: {drug_code}")

        # 每处理完一个批次就保存结果，支持接续处理
        if len(processed_drugs_batch) + len(incomplete_drugs_batch) >= batch_size:
            # 保存当前批次结果
            if processed_drugs_batch:
                new_complete_df = pd.DataFrame(processed_drugs_batch, columns=output_columns)
                new_complete_df.to_csv(OUTPUT_CSV, mode='a', header=not os.path.exists(OUTPUT_CSV), index=False, encoding='utf-8-sig')
                logging.info(f"保存完整药物信息: {len(processed_drugs_batch)} 条记录 -> {OUTPUT_CSV}")
            
            if incomplete_drugs_batch:
                new_incomplete_df = pd.DataFrame(incomplete_drugs_batch, columns=output_columns)
                new_incomplete_df.to_csv(INCOMPLETE_OUTPUT_CSV, mode='a', header=not os.path.exists(INCOMPLETE_OUTPUT_CSV), index=False, encoding='utf-8-sig')
                logging.info(f"保存不完整药物信息: {len(incomplete_drugs_batch)} 条记录 -> {INCOMPLETE_OUTPUT_CSV}")
            
            # 清空当前批次数据
            processed_drugs_batch = []
            incomplete_drugs_batch = []
            
            # 更新批次计数
            current_batch += 1

    # 保存最后一批次的结果
    if processed_drugs_batch:
        new_complete_df = pd.DataFrame(processed_drugs_batch, columns=output_columns)
        new_complete_df.to_csv(OUTPUT_CSV, mode='a', header=not os.path.exists(OUTPUT_CSV), index=False, encoding='utf-8-sig')
        logging.info(f"保存完整药物信息: {len(processed_drugs_batch)} 条记录 -> {OUTPUT_CSV}")
    
    if incomplete_drugs_batch:
        new_incomplete_df = pd.DataFrame(incomplete_drugs_batch, columns=output_columns)
        new_incomplete_df.to_csv(INCOMPLETE_OUTPUT_CSV, mode='a', header=not os.path.exists(INCOMPLETE_OUTPUT_CSV), index=False, encoding='utf-8-sig')
        logging.info(f"保存不完整药物信息: {len(incomplete_drugs_batch)} 条记录 -> {INCOMPLETE_OUTPUT_CSV}")

    logging.info("=" * 60)
    logging.info("多来源药物信息提取完成")
    logging.info("=" * 60)

if __name__ == "__main__":
    main()
