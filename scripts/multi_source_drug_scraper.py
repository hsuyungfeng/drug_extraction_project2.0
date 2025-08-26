import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import logging
import random
import os
import ollama
import json
import re
import fitz  # PyMuPDF
import io

# --- Configuration ---
INPUT_CSV = "1140816健保用藥品項查詢項目檔_健保用藥品項.csv"
OUTPUT_CSV = "drug_info_extracted_final.csv"
INCOMPLETE_OUTPUT_CSV = "uncomplete-research.csv"
GOOGLE_SEARCH_RESULTS_CSV = "google_search_results.csv" # New input file
LOG_FILE = "drug_scraping.log"
MODEL = "gpt-oss:20b"

# --- Demo Mode ---
IS_DEMO = True
DEMO_LIMIT = 10

# --- Search & Scraping Settings ---
REQUEST_TIMEOUT = 15

# Define specific source URLs
SOURCE_URLS = {
    "TFDA": "https://data.fda.gov.tw/opendata/exportDataList.do",
    "NHI_DATA_DOWNLOAD": "https://scidm.nchc.org.tw/dataset/best_wish23715/resource/2b92cade-ca29-4924-b2d6-5820a239536a/nchcproxy",
}

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def scrape_tfda(drug_name: str, manufacturer: str, ingredient: str) -> str:
    logging.info(f"Attempting to scrape TFDA for {drug_name}")
    tfda_api_url = SOURCE_URLS["TFDA"]
    params = {
        'method': 'openData',
        'InfoId': '36'
    }
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
                        logging.info(f"Found relevant TFDA data for {drug_name}.")
                        return "\n\n".join(found_info)

        if not found_info:
            logging.info(f"No relevant TFDA data found for {drug_name} after filtering.")
        return "\n\n".join(found_info)

    except Exception as e:
        logging.error(f"Unexpected error during TFDA scraping for {drug_name}: {e}")
        return ""


def scrape_nhi(drug_name: str, manufacturer: str, ingredient: str) -> str:
    logging.info(f"Attempting to scrape NHI for {drug_name}")
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
                logging.info(f"Found relevant NHI data for {drug_name}.")
                return "\n\n".join(found_info)
        
        logging.info(f"No relevant NHI data found for {drug_name} after local filtering.")
        return ""

    except Exception as e:
        logging.error(f"Unexpected error during NHI scraping: {e}")
        return ""

def extract_info_with_llm(text_content: str, drug_name: str) -> dict:
    if not text_content:
        return {"適應症": "", "用法用量": "", "注意事項": ""}

    logging.info(f"Extracting from content for '{drug_name}' using {MODEL}.")
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
                logging.error(f"LLM did not return a JSON object for {drug_name}. Response: {resp_text}")
                return {"適應症": "模型回傳格式錯誤", "用法用量": "模型回傳格式錯誤", "注意事項": "模型回傳格式錯誤"}

            json_str = json_match.group(1).strip()
            data = json.loads(json_str)
        
        for key in ["適應症", "用法用量", "注意事項"]:
            data[key] = data.get(key, "資訊不足")[:100]
        return data
    except Exception as e:
        logging.error(f"LLM extraction failed for {drug_name}: {e}")
        return {"適應症": "模型提取失敗", "用法用量": "模型提取失敗", "注意事項": "模型提取失敗"}

def main():
    logging.info("Starting enhanced drug information scraping pipeline.")
    try:
        input_df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig', keep_default_na=False)
    except FileNotFoundError:
        logging.error(f"Input file not found: {INPUT_CSV}")
        return

    # Load Google Search results if available
    google_results_df = pd.DataFrame()
    if os.path.exists(GOOGLE_SEARCH_RESULTS_CSV):
        logging.info(f"Loading Google Search results from {GOOGLE_SEARCH_RESULTS_CSV}")
        google_results_df = pd.read_csv(GOOGLE_SEARCH_RESULTS_CSV, encoding='utf-8-sig', keep_default_na=False)
        # Index by '藥品代號' for quick lookup
        if '藥品代號' in google_results_df.columns:
            google_results_df.set_index('藥品代號', inplace=True)
        else:
            logging.warning(f"{GOOGLE_SEARCH_RESULTS_CSV} does not have '藥品代號' column, cannot use it for lookup.")
            google_results_df = pd.DataFrame()


    output_columns = input_df.columns.tolist() + ['適應症', '用法用量', '注意事項']

    if IS_DEMO:
        if os.path.exists(OUTPUT_CSV):
            os.remove(OUTPUT_CSV)
        if os.path.exists(INCOMPLETE_OUTPUT_CSV):
            os.remove(INCOMPLETE_OUTPUT_CSV)

    output_df = pd.DataFrame(columns=output_columns)
    if os.path.exists(OUTPUT_CSV):
        output_df = pd.read_csv(OUTPUT_CSV, encoding='utf-8-sig', keep_default_na=False)
    
    incomplete_df = pd.DataFrame(columns=output_columns)
    if os.path.exists(INCOMPLETE_OUTPUT_CSV):
        incomplete_df = pd.read_csv(INCOMPLETE_OUTPUT_CSV, encoding='utf-8-sig', keep_default_na=False)

    all_existing_data = pd.concat([output_df, incomplete_df]).drop_duplicates(subset=['藥品代號'], keep='first')
    
    processed_drug_codes = set(all_existing_data['藥品代號'].tolist())
    drugs_to_process_df = input_df[~input_df['藥品代號'].isin(processed_drug_codes)].copy()

    limit = DEMO_LIMIT if IS_DEMO else len(drugs_to_process_df)
    
    processed_drugs_batch = []
    incomplete_drugs_batch = []
    
    for index, row in drugs_to_process_df.head(limit).iterrows():
        drug_code = row.get('藥品代號', '')
        drug_name = row.get('藥品中文名稱', '')
        logging.info(f"--- Processing drug: {drug_code} - {drug_name} ---")
        
        manufacturer = row.get('製造廠名稱', '')
        ingredient = row.get('成份', '')

        if not all([drug_name, manufacturer, ingredient]):
            logging.warning(f"Skipping row {drug_code} due to missing critical information.")
            current_row_data = row.to_dict()
            for col in ['適應症', '用法用量', '注意事項']:
                current_row_data[col] = "資訊不足 - 關鍵資訊缺失"
            incomplete_drugs_batch.append(current_row_data)
            continue

        # Step 1: Check for info from Google Search results
        web_info = {}
        if not google_results_df.empty and drug_code in google_results_df.index:
            logging.info(f"Found pre-compiled Google Search info for {drug_name}.")
            google_info = google_results_df.loc[drug_code]
            web_info = {
                "適應症": google_info.get("適應症", ""),
                "用法用量": google_info.get("用法用量", ""),
                "注意事項": google_info.get("注意事項", ""),
            }

        all_fields_complete = all(web_info.get(col, "") not in ["", "資訊不足"] for col in ['適應症', '用法用量', '注意事項'])

        # Step 2: If web search is incomplete, fallback to TFDA/NHI
        if not all_fields_complete:
            logging.info(f"Web search info incomplete for {drug_name}. Falling back to TFDA/NHI.")
            combined_text = ""
            tfda_content = scrape_tfda(drug_name, manufacturer, ingredient)
            if tfda_content:
                combined_text += f"--- 來源: TFDA ---\n{tfda_content}\n\n"

            nhi_content = scrape_nhi(drug_name, manufacturer, ingredient)
            if nhi_content:
                combined_text += f"--- 來源: NHI ---\n{nhi_content}\n\n"
            
            web_info = extract_info_with_llm(combined_text, drug_name)
            all_fields_complete = all(web_info.get(col, "") not in ["", "資訊不足", "模型提取失敗", "模型回傳格式錯誤"] for col in ['適應症', '用法用量', '注意事項'])

        current_row_data = row.to_dict()
        for key, value in web_info.items():
            current_row_data[key] = value

        if all_fields_complete:
            processed_drugs_batch.append(current_row_data)
            logging.info(f"Successfully processed and added to complete batch: {drug_code}")
        else:
            incomplete_drugs_batch.append(current_row_data)
            logging.info(f"Drug {drug_code} not fully processed. Added to incomplete batch.")

    if processed_drugs_batch:
        new_complete_df = pd.DataFrame(processed_drugs_batch, columns=output_columns)
        new_complete_df.to_csv(OUTPUT_CSV, mode='a', header=not os.path.exists(OUTPUT_CSV), index=False, encoding='utf-8-sig')
        logging.info(f"Saved final {len(processed_drugs_batch)} complete drugs to {OUTPUT_CSV}")
    
    if incomplete_drugs_batch:
        new_incomplete_df = pd.DataFrame(incomplete_drugs_batch, columns=output_columns)
        new_incomplete_df.to_csv(INCOMPLETE_OUTPUT_CSV, mode='a', header=not os.path.exists(INCOMPLETE_OUTPUT_CSV), index=False, encoding='utf-8-sig')
        logging.info(f"Saved final {len(incomplete_drugs_batch)} incomplete drugs to {INCOMPLETE_OUTPUT_CSV}")

    logging.info(f"Pipeline finished. Complete results saved to {OUTPUT_CSV}, incomplete to {INCOMPLETE_OUTPUT_CSV}")

if __name__ == "__main__":
    main()