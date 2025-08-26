#!/usr/bin/env python3
"""
项目测试脚本
验证药物信息提取项目的结构和依赖
"""

import os
import sys
import subprocess
from pathlib import Path

def check_directory_structure():
    """检查项目目录结构"""
    print("=" * 50)
    print("检查项目目录结构")
    print("=" * 50)
    
    required_dirs = [
        "data",
        "output", 
        "logs",
        "config",
        "scripts"
    ]
    
    all_good = True
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists() and dir_path.is_dir():
            print(f"✓ 目录存在: {dir_name}")
        else:
            print(f"✗ 目录缺失: {dir_name}")
            all_good = False
    
    return all_good

def check_required_files():
    """检查必需的文件"""
    print("\n" + "=" * 50)
    print("检查必需的文件")
    print("=" * 50)
    
    required_files = [
        "config/project_config.py",
        "scripts/multi_source_extraction.py",
        "run_extraction_pipeline.py",
        "setup.py"
    ]
    
    all_good = True
    
    for file_path in required_files:
        file_obj = Path(file_path)
        if file_obj.exists() and file_obj.is_file():
            print(f"✓ 文件存在: {file_path}")
        else:
            print(f"✗ 文件缺失: {file_path}")
            all_good = False
    
    return all_good

def check_python_dependencies():
    """检查Python依赖"""
    print("\n" + "=" * 50)
    print("检查Python依赖")
    print("=" * 50)
    
    # 包名和对应的导入名
    dependencies = [
        ("pandas", "pandas"),
        ("requests", "requests"),
        ("beautifulsoup4", "bs4"),
        ("ollama", "ollama"),
        ("PyMuPDF", "fitz")
    ]
    
    all_good = True
    
    for package_name, import_name in dependencies:
        try:
            __import__(import_name)
            print(f"✓ 依赖已安装: {package_name}")
        except ImportError:
            print(f"✗ 依赖缺失: {package_name}")
            all_good = False
    
    return all_good

def check_sample_data():
    """检查示例数据"""
    print("\n" + "=" * 50)
    print("检查示例数据")
    print("=" * 50)
    
    sample_file = Path("data/sample_drugs.csv")
    if sample_file.exists():
        print(f"✓ 示例数据存在: {sample_file}")
        
        # 读取并显示示例数据
        import pandas as pd
        try:
            df = pd.read_csv(sample_file, encoding='utf-8-sig')
            print(f"  示例数据记录数: {len(df)}")
            print("  前2条记录:")
            for i, row in df.head(2).iterrows():
                print(f"    {row['藥品代號']} - {row['藥品中文名稱']}")
            return True
        except Exception as e:
            print(f"✗ 读取示例数据失败: {e}")
            return False
    else:
        print("✗ 示例数据不存在")
        print("  请运行: python setup.py 创建示例数据")
        return False

def check_ollama_connection():
    """检查Ollama连接"""
    print("\n" + "=" * 50)
    print("检查Ollama连接")
    print("=" * 50)
    
    try:
        import ollama
        # 尝试列出可用模型
        models = ollama.list()
        if models and 'models' in models:
            print("✓ Ollama连接正常")
            print(f"  可用模型: {len(models['models'])} 个")
            for model in models['models']:
                # 安全地获取模型名称，Ollama可能使用'model'字段而不是'name'
                model_name = model.get('model', model.get('name', '未知模型'))
                print(f"    - {model_name}")
            return True
        else:
            print("✗ Ollama未返回模型列表")
            return False
    except Exception as e:
        print(f"✗ Ollama连接失败: {e}")
        print("  请确保Ollama服务正在运行")
        return False

def test_config_import():
    """测试配置导入"""
    print("\n" + "=" * 50)
    print("测试配置导入")
    print("=" * 50)
    
    try:
        # 添加项目根目录到Python路径
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        
        from config.project_config import (
            INPUT_CSV, OUTPUT_CSV, INCOMPLETE_OUTPUT_CSV, 
            GOOGLE_SEARCH_RESULTS_CSV, MODEL, IS_DEMO, DEMO_LIMIT
        )
        
        print("✓ 配置导入成功")
        print(f"  输入文件: {INPUT_CSV}")
        print(f"  输出文件: {OUTPUT_CSV}")
        print(f"  不完整文件: {INCOMPLETE_OUTPUT_CSV}")
        print(f"  Google结果: {GOOGLE_SEARCH_RESULTS_CSV}")
        print(f"  模型: {MODEL}")
        print(f"  演示模式: {IS_DEMO}")
        print(f"  演示限制: {DEMO_LIMIT}")
        
        return True
    except Exception as e:
        print(f"✗ 配置导入失败: {e}")
        return False

def main():
    """主测试函数"""
    print("药物信息提取项目测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("目录结构", check_directory_structure()))
    test_results.append(("必需文件", check_required_files()))
    test_results.append(("Python依赖", check_python_dependencies()))
    test_results.append(("示例数据", check_sample_data()))
    test_results.append(("Ollama连接", check_ollama_connection()))
    test_results.append(("配置导入", test_config_import()))
    
    # 总结测试结果
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过！项目设置完成。")
        print("\n下一步:")
        print("1. 将您的药物数据CSV文件放入 data/ 目录")
        print("2. 运行: python run_extraction_pipeline.py 开始提取")
    else:
        print("\n⚠️  部分测试失败，请检查并修复问题。")
        print("\n建议:")
        print("1. 运行: python setup.py 重新设置项目")
        print("2. 检查Ollama服务是否运行")
        print("3. 安装缺失的依赖: pip install pandas requests beautifulsoup4 ollama PyMuPDF")

if __name__ == "__main__":
    main()
