"""
项目配置文件
定义所有路径和配置常量
"""

import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据文件路径
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output') 
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 输入输出文件
INPUT_CSV = os.path.join(DATA_DIR, '1140816健保用藥品項查詢項目檔_健保用藥品項.csv')
OUTPUT_CSV = os.path.join(OUTPUT_DIR, 'drug_info_extracted_final.csv')
INCOMPLETE_OUTPUT_CSV = os.path.join(OUTPUT_DIR, 'uncomplete-research.csv')
GOOGLE_SEARCH_RESULTS_CSV = os.path.join(OUTPUT_DIR, 'google_search_results.csv')

# MCP 配置
MCP_CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'mcp_config.json')

# 模型配置
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "gpt-oss:20b"
MODEL = OLLAMA_MODEL  # 兼容性别名

# 运行模式配置
IS_DEMO = True  # True: 演示模式(处理前10种药物), False: 生产模式(处理所有药物)
DEMO_LIMIT = 10  # 演示模式处理数量
BATCH_SIZE = 10  # 生产模式每批处理数量

# 搜索配置
SEARCH_TIMEOUT = 15
MAX_RESULTS_PER_DRUG = 3
REQUEST_TIMEOUT = 30

# 数据源URL
SOURCE_URLS = {
    "TFDA": "https://data.fda.gov.tw/opendata/exportDataList.do",
    "NHI_DATA_DOWNLOAD": "https://data.nhi.gov.tw/resource/mask/maskdata.csv"
}

# 确保目录存在
def ensure_directories():
    """确保所有必要的目录都存在"""
    directories = [DATA_DIR, OUTPUT_DIR, LOG_DIR]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"确保目录存在: {directory}")

# 测试配置
if __name__ == "__main__":
    ensure_directories()
    print("项目配置加载完成")
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"INPUT_CSV: {INPUT_CSV}")
    print(f"OUTPUT_CSV: {OUTPUT_CSV}")
