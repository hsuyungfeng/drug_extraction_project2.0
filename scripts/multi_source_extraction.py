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
                
        except Exception as e:
            logging.error(f"TFDA抓取失败 {drug_name}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 等待1秒后重试
                continue
            else:
                return ""
    
    return ""

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

def extract_info_with_llm(text_content: str, drug_name: str) -> dict:
    """使用本地LLM提取信息"""
    if not text_content:
        return {"適應症": "", "用法用量": "", "注意事項": ""}

    logging.info(f"使用 {MODEL} 提取信息: {drug_name}")
    prompt = f'''你是藥品資訊提取助手。從以下內容提取：
- 適應症（主治）
- 用法及用量（劑量）
- 注意事項（含禁忌）

這些內容只需要參考用，不須太精準。

嚴格遵守以下規則：
1. 以台灣繁體中文簡潔地回答。
2. 每個欄位的回答都必須少於100個字元。
3. 如果資訊不存在，在該欄位回答「資訊不足」。
4. 輸出格式為 JSON。

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

        # 步骤1: 检查Google搜索结果
        web_info = {}
        if not google_results_df.empty and drug_code in google_results_df.index:
            logging.info(f"使用Google搜索结果: {drug_name}")
            google_info = google_results_df.loc[drug_code]
            web_info = {
                "適應症": google_info.get("適應症", ""),
                "用法用量": google_info.get("用法用量", ""),
                "注意事項": google_info.get("注意事項", ""),
            }

        # 检查信息是否完整
        all_fields_complete = all(web_info.get(col, "") not in ["", "資訊不足"] for col in ['適應症', '用法用量', '注意事項'])

        # 步骤2: 如果Google搜索不完整，回退到TFDA (暂时禁用NHI)
        if not all_fields_complete:
            logging.info(f"Google搜索信息不完整，回退到TFDA: {drug_name}")
            combined_text = ""
            tfda_content = scrape_tfda(drug_name, manufacturer, ingredient)
            if tfda_content:
                combined_text += f"--- 來源: TFDA ---\n{tfda_content}\n\n"

            # 暂时禁用NHI数据源，避免DNS错误影响流程
            # nhi_content = scrape_nhi(drug_name, manufacturer, ingredient)
            # if nhi_content:
            #     combined_text += f"--- 來源: NHI ---\n{nhi_content}\n\n"
            
            if combined_text:
                web_info = extract_info_with_llm(combined_text, drug_name)
                all_fields_complete = all(web_info.get(col, "") not in ["", "資訊不足", "模型提取失敗", "模型回傳格式錯誤"] for col in ['適應症', '用法用量', '注意事項'])
            else:
                logging.warning(f"TFDA未找到数据: {drug_name}")
                # 如果TFDA没有数据，直接使用Google搜索结果，避免重复LLM调用
                web_info = {key: value for key, value in web_info.items()}

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
