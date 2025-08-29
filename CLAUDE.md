# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Drug information extraction project using Qwen-Agent framework to extract key information from Taiwan NHI drug database. Extracts indications, dosage, and precautions from 14,621 drug records using hybrid AI architecture with local Ollama models.

## Key Commands

### Setup and Installation
```bash
# Create virtual environment with uv
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install qwen-agent pandas requests beautifulsoup4 python-dotenv ollama

# Start Ollama service
ollama serve &
ollama pull gpt-oss:20b
```

### Main Execution Commands
```bash
# Full automated pipeline (recommended)
uv run python run_extraction_pipeline.py

# Stage 1: Qwen-Agent Google search only
uv run python scripts/qwen_agent_integration.py

# Stage 2: Main extraction process
uv run python scripts/multi_source_extraction.py

# Test project setup
uv run python test_project.py
```

### Configuration and Parameters
```bash
# Demo mode (process first 10 drugs)
IS_DEMO=true uv run python scripts/multi_source_extraction.py

# Custom batch size
IS_DEMO=false BATCH_SIZE=20 uv run python scripts/multi_source_extraction.py

# Limit processing to specific number
uv run python scripts/qwen_agent_integration.py --limit 50

# Custom timeout
uv run python scripts/qwen_agent_integration.py --timeout 120
```

## Architecture

### Two-Phase Processing
1. **Google Search Phase**: Qwen-Agent performs web searches for incomplete drug data
2. **Multi-Source Extraction**: Local scripts integrate TFDA/NHI APIs + local LLM processing

### Key Components
- **Qwen-Agent Integration**: `scripts/qwen_agent_integration.py` - Google search with local Ollama
- **Main Extractor**: `scripts/multi_source_extraction.py` - Batch processing with configurable size
- **Pipeline Runner**: `run_extraction_pipeline.py` - Complete automated workflow
- **Configuration**: `config/project_config.py` - Paths, batch sizes, and model settings

### Data Flow
1. Input: `data/1140816健保用藥品項查詢項目檔_健保用藥品項.csv` (14,621 records)
2. Intermediate: `output/google_search_results.csv` (Google search results)
3. Output: `output/drug_info_extracted_final.csv` (complete data)
4. Incomplete: `output/uncomplete-research.csv` (remaining drugs)

### Model Configuration
- Uses local Ollama with OpenAI-compatible endpoint: `http://localhost:11434/v1`
- Default model: `gpt-oss:20b`
- Configurable via `config/project_config.py` and environment variables

## Development Notes

- Batch processing controlled by `BATCH_SIZE` (default: 10) and `IS_DEMO` mode
- Uses uv for dependency management and virtual environments
- Logs stored in `logs/` directory with detailed processing information
- Cache mechanism in `output/qwen_agent_cache.json` to avoid duplicate searches
- ### 2025年8月27日：藥物提取流程重構計畫

**目標：** 根據新的“五步法”統一工作流程，重構藥物資訊提取腳本，以提高提取成功率和流程的穩健性。

**會議記錄 (內部審查 - 45分鐘):**

#### 1. 已批准的統一工作流程

我們將按照以下順序，依次嘗試獲取每種藥物的資訊，直到所有必需欄位（適應症、用法用量、注意事項）都被填寫為止：

1.  **第1步 (中文名搜索)**：使用 `中文藥品名稱 + 關鍵字` 進行初步搜索和提取。
2.  **第2步 (英文名搜索)**：如有缺失，使用 `英文藥品名稱 + 關鍵字` 進行補充搜索。
3.  **第3步 (成分搜索)**：如仍有缺失，使用 `成分` 進行跨國權威網站搜索，並由LLM完成“翻譯+提取”。
4.  **第4步 (API 抓取)**：如仍有缺失，調用（修復後的）TFDA API 進行提取。
5.  **第5步 (PDF 仿單提取)**：作為最終手段，搜索、下載並解析藥品的官方PDF仿單。

#### 2. 實施計畫與進程

**第一階段：修復核心備用方案 & 重構基礎 (預計今日完成)**

*   **任務 1：修復 `scrape_tfda` 函數**
    *   **問題分析：** 當前函數因直接假設API返回JSON而頻繁失敗。日誌顯示 `Expecting value` 錯誤，表明返回的是非JSON內容（可能是HTML錯誤頁面）。
    *   **實現方式：**
        1.  在 `requests.get` 後，增加 `try-except` 塊來包裹 `response.json()` 調用。
        2.  在調用 `.json()` 前，檢查 `response.headers.get('Content-Type')` 是否包含 `application/json`。
        3.  如果不是JSON，或解析失敗，則將 `response.text` 的內容完整記錄到 `logs/debug/tfda_error_[drug_name].html` 文件中，以便分析失敗原因。
        4.  函數在失敗時應返回 `None` 或空字典，而不是拋出異常，讓主流程可以繼續。

*   **任務 2：重構 `multi_source_extraction.py` 主邏輯**
    *   **目標：** 改造 `main` 函數，使其能夠支持新的“五步法”工作流程。
    *   **實現方式：**
        1.  為每種藥物創建一個狀態字典，用於追蹤哪些資訊欄位已被成功填充。
        2.  實現一個主循環，按順序調用五步法的各個提取函數。
        3.  只有當藥物的狀態字典仍有缺失欄位時，才調用下一步的提取函數。

**第二階段：實現新的搜索策略 (預計後續執行)**

*   **任務 3：實現中文名、英文名、成分搜索**
    *   **實現方式：**
        1.  創建一個更通用的搜索函數 `search_and_extract(query)`。
        2.  該函數將集成 `googlesearch-python`（或類似庫）來獲取URL。
        3.  使用 `trafilatura` 提取網頁正文。
        4.  調用LLM從乾淨文本中提取JSON。
        5.  在主流程中按順序調用此函數，傳入不同的查詢（中文名、英文名、成分）。

**第三階段：開發PDF提取功能 (長期目標)**

*   **任務 4：實現PDF仿單提取**
    *   **實現方式：**
        1.  研究如何穩定地搜索到藥品仿單的PDF連結。
        2.  使用 `PyMuPDF` 庫讀取和提取PDF文本。
        3.  開發文本清洗算法，處理PDF中的分欄和格式問題。
        4.  將清洗後的文本交給LLM進行提取。

**今日進程：**
我將立即開始執行 **第一階段** 的 **任務 1**，即修復 `scrape_tfda` 函數。


> 1. 嘗試藥品中名稱 配合關鍵字 - 適應症（主治）或- 用法及用量（劑量）或- 注意事項（含禁忌）做第一次藥物資訊llm 提取  2. 如果有缺失欄位 第2 次提取     以藥品英文名稱 配合關鍵字 - 適應症（主治）或- 用法及用量（劑量）或- 注意事項（含禁忌）做第一次藥物資訊llm 提取  3.如果有缺失欄位 仍有缺失欄位 第3  提取 以成份 提取不限台灣網站 但須翻譯中文提取  4. 如果還未補足 才以才以目前方式提取藥品代號的pdf ,仿單資訊   

  对您方案的分析与技术实现思路

  您的想法 1 & 2：使用中文和英文名称进行搜索

   * 我的看法：完全同意。这是最直接有效的方式。
   * 技术实现：
       1. 我们可以精确地执行这个两步过程。首先使用“中文名 + 关键词”搜索。
       2. 检查返回的 JSON 中是否有空字段。
       3. 如果有，再启动第二步，使用“英文名 + 关键词”进行补充搜索。
       4. 这个过程可以结合我之前提到的“分离搜索与提取”的技巧：先用搜索引擎获取URL列表，再提取网页正文，最后让 LLM
          专注地从干净的文本中提取信息。这样结果会更稳定。

  您的想法 3：使用“成分”进行跨国搜索和翻译

   * 我的看法：这是整个方案中的一个亮点。通过成分搜索可以突破特定品牌和地区的限制，找到最核心的药品信息，极大提升覆盖率。
   * 技术实现：
       1. 精确搜索：搜索时，可以使用更专业的查询，例如 "[成分英文名] prescribing information" 或 "[成分英文名] 
          dosage"。我们甚至可以优先搜索国外权威药品网站，如 site:drugs.com 或 site:medscape.com。
       2. 翻译与提取合并：我们可以设计一个更高效的 Prompt，让 LLM
          一步完成两个任务：“请将以下英文药理信息翻译成台湾繁体中文，并从中提取‘适应症’、‘用法用量’和‘注意事项’，以JSON格式输出。”
          这样可以减少一次模型调用。

  您的想法 4：提取 PDF 仿单信息

   * 我的看法：这是最可靠的“最后防线”。仿单（PDF）是官方资料，准确性最高。
   * 技术实现与现状：
       1. 需要澄清：目前脚本中的 multi_source_extraction.py 虽然导入了 fitz (PyMuPDF) 库，但实际上并没有编写从 PDF
          中提取信息的代码。当前的备用方案是调用 TFDA API，而这个 API 已经失效。
       2. 实现步骤：我们可以将“解析PDF”作为真正的最后一步来实现。这需要：
           * 找到PDF：这本身就是一个挑战，需要先搜索到药品的官方仿单 PDF 的链接。
           * 文本提取：使用 PyMuPDF 从 PDF 中抽取出所有文字。
           * 文本清洗：PDF 的文本布局可能很复杂（多栏、页眉页脚），需要进行预处理，整合成连贯的文本块。
           * LLM 提取：将清洗后的文本交给 LLM 进行最终的信息提取。

  ---

  总结与建议的“统一工作流程”

  结合您的策略和我的技术建议，我构想出一个新的、更强大的自动化流程：

  对于每一款药品：

   1. 第1步 (中文名搜索)：使用 中文藥品名稱 + 關鍵字 进行搜索和LLM提取。
   2. 第2步 (英文名搜索)：如果仍有字段缺失，使用 英文藥品名稱 + 關鍵字 进行补充搜索和提取。
   3. 第3步 (成分搜索)：如果仍有字段缺失，使用 成分 + "prescribing information" 进行跨国搜索，然后由 LLM 完成“翻译+提取”任务。
   4. 第4步 (API 抓取 - 修复后)：如果仍有字段缺失，调用（修复后的）TFDA API，并用 LLM 从返回的信息中提取。
   5. 第5步 (PDF 仿单提取 - 新功能)：如果以上步骤全部失败，则启动最终方案：搜索并下载该药品的官方 PDF 仿单，解析其内容进行提取。