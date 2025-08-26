#!/usr/bin/env python3
"""
药物信息提取主流程脚本
整合Google搜索、TFDA/NHI抓取和本地LLM处理
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.project_config import ensure_directories, INPUT_CSV, OUTPUT_CSV, INCOMPLETE_OUTPUT_CSV, GOOGLE_SEARCH_RESULTS_CSV

def setup_logging():
    """设置日志配置"""
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "extraction_pipeline.log", mode='w', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def check_input_file():
    """检查输入文件是否存在"""
    if not os.path.exists(INPUT_CSV):
        logging.error(f"输入文件不存在: {INPUT_CSV}")
        logging.info("请将您的药物数据CSV文件放入 data/ 目录")
        logging.info("或者运行 setup.py 创建示例数据")
        return False
    return True

def run_google_search_phase():
    """运行Google搜索阶段"""
    logging.info("=" * 50)
    logging.info("阶段1: Google搜索信息提取 (使用Qwen-Agent)")
    logging.info("=" * 50)
    
    # 检查是否已经有Google搜索结果
    if os.path.exists(GOOGLE_SEARCH_RESULTS_CSV):
        logging.info(f"Google搜索结果已存在: {GOOGLE_SEARCH_RESULTS_CSV}")
        logging.info("跳过Google搜索阶段")
        return True
    
    logging.info("开始执行Qwen-Agent Google搜索...")
    
    try:
        # 导入并执行Qwen-Agent整合脚本
        from scripts.qwen_agent_integration import main as qwen_main
        
        logging.info("启动Qwen-Agent进行药物信息搜索")
        qwen_main()
        
        # 检查是否成功生成结果
        if os.path.exists(GOOGLE_SEARCH_RESULTS_CSV):
            logging.info(f"Qwen-Agent搜索完成，结果保存至: {GOOGLE_SEARCH_RESULTS_CSV}")
            return True
        else:
            logging.warning("Qwen-Agent执行完成但未生成结果文件")
            return False
            
    except ImportError as e:
        logging.error(f"导入Qwen-Agent脚本失败: {e}")
        logging.info("请确保已安装Qwen-Agent依赖: pip install qwen-agent")
        return False
    except Exception as e:
        logging.error(f"Qwen-Agent执行失败: {e}")
        return False

def run_main_extraction():
    """运行主提取流程"""
    logging.info("=" * 50)
    logging.info("阶段2: 主信息提取流程")
    logging.info("=" * 50)
    
    try:
        # 导入主提取脚本
        from scripts.multi_source_extraction import main as extraction_main
        
        logging.info("开始执行主提取流程...")
        extraction_main()
        return True
        
    except ImportError as e:
        logging.error(f"导入提取脚本失败: {e}")
        logging.info("请确保 multi_source_extraction.py 脚本存在")
        return False
    except Exception as e:
        logging.error(f"提取流程执行失败: {e}")
        return False

def summarize_results():
    """总结提取结果"""
    logging.info("=" * 50)
    logging.info("结果总结")
    logging.info("=" * 50)
    
    import pandas as pd
    
    # 检查输出文件
    files_to_check = [
        (OUTPUT_CSV, "完整药物信息"),
        (INCOMPLETE_OUTPUT_CSV, "不完整药物信息"),
        (GOOGLE_SEARCH_RESULTS_CSV, "Google搜索结果")
    ]
    
    for file_path, description in files_to_check:
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                logging.info(f"{description}: {len(df)} 条记录 - {file_path}")
            except Exception as e:
                logging.error(f"读取 {file_path} 失败: {e}")
        else:
            logging.info(f"{description}: 文件不存在 - {file_path}")

def main():
    """主函数"""
    # 确保目录存在
    ensure_directories()
    
    # 设置日志
    setup_logging()
    
    logging.info("=" * 60)
    logging.info("药物信息提取管道启动")
    logging.info("=" * 60)
    
    # 检查输入文件
    if not check_input_file():
        return
    
    # 运行Google搜索阶段
    google_search_complete = run_google_search_phase()
    
    # 运行主提取流程
    if google_search_complete or os.path.exists(GOOGLE_SEARCH_RESULTS_CSV):
        run_main_extraction()
    else:
        logging.info("等待Google搜索阶段完成后，请重新运行此脚本")
    
    # 总结结果
    summarize_results()
    
    logging.info("=" * 60)
    logging.info("药物信息提取管道完成")
    logging.info("=" * 60)

if __name__ == "__main__":
    main()
