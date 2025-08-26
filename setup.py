#!/usr/bin/env python3
"""
项目安装脚本
设置药物信息提取项目的环境
"""

import os
import sys
import subprocess
import venv
from pathlib import Path

def create_virtual_environment():
    """创建Python虚拟环境"""
    venv_path = Path(".venv")
    
    if venv_path.exists():
        print(f"虚拟环境已存在: {venv_path}")
        return True
    
    print("创建Python虚拟环境...")
    try:
        venv.create(venv_path, with_pip=True)
        print(f"虚拟环境创建成功: {venv_path}")
        return True
    except Exception as e:
        print(f"创建虚拟环境失败: {e}")
        return False

def install_requirements():
    """安装项目依赖"""
    requirements = [
        "pandas",
        "requests",
        "beautifulsoup4",
        "ollama",
        "PyMuPDF"
    ]
    
    # 检查是否在虚拟环境中
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    # 使用 uv 安装依赖
    uv_cmd = ["uv", "pip", "install"]
    
    if in_venv:
        # 如果在虚拟环境中，直接使用 uv
        print("安装项目依赖...")
        for package in requirements:
            try:
                result = subprocess.run(uv_cmd + [package], 
                                      capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    print(f"✓ 安装成功: {package}")
                else:
                    print(f"✗ 安装失败: {package}")
                    print(f"  错误: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"✗ 安装超时: {package}")
            except Exception as e:
                print(f"✗ 安装异常: {package} - {e}")
    else:
        # 如果不在虚拟环境中，使用系统 uv
        print("安装项目依赖...")
        for package in requirements:
            try:
                result = subprocess.run(uv_cmd + [package], 
                                      capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    print(f"✓ 安装成功: {package}")
                else:
                    print(f"✗ 安装失败: {package}")
                    print(f"  错误: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"✗ 安装超时: {package}")
            except Exception as e:
                print(f"✗ 安装异常: {package} - {e}")

def setup_project_structure():
    """设置项目目录结构"""
    directories = [
        "data",
        "output", 
        "logs",
        "config",
        "scripts"
    ]
    
    print("创建项目目录结构...")
    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(exist_ok=True)
        print(f"✓ 创建目录: {directory}")

def create_sample_data():
    """创建示例数据文件"""
    data_dir = Path("data")
    sample_file = data_dir / "sample_drugs.csv"
    
    if sample_file.exists():
        print("示例数据文件已存在")
        return
    
    print("创建示例数据文件...")
    
    # 使用虚拟环境中的Python来运行数据创建
    venv_python = Path(".venv/bin/python")
    if venv_python.exists():
        try:
            # 在虚拟环境中运行数据创建脚本
            script_content = '''
import pandas as pd
import os

sample_data = [
    {
        "藥品代號": "A000072100",
        "藥品英文名稱": "EPHEDRINE HCL TABELTS 25MG",
        "藥品中文名稱": "鹽酸麻黃錠２５公絲",
        "規格量": "0.0",
        "規格單位": "",
        "單複方": "單方",
        "參考價": "0.56",
        "有效起日": "1030701",
        "有效迄日": "9991231",
        "製造廠名稱": "黃氏製藥股份有限公司",
        "劑型": "錠劑",
        "成份": "EPHEDRINE HCL",
        "ATC_CODE": "R03CA02"
    },
    {
        "藥品代號": "A000076100",
        "藥品英文名稱": "ACETAMINOPHEN TABLETS 0.3 GM",
        "藥品中文名稱": "安世多阿米諾思錠０．３公克",
        "規格量": "0.0",
        "規格單位": "",
        "單複方": "單方",
        "參考價": "0.25",
        "有效起日": "1030701",
        "有效迄日": "9991231",
        "製造廠名稱": "福元化學製藥股份有限公司",
        "劑型": "錠劑",
        "成份": "ACETAMINOPHEN (=PARACETAMOL)",
        "ATC_CODE": "N02BE01"
    }
]

df = pd.DataFrame(sample_data)
df.to_csv("data/sample_drugs.csv", index=False, encoding='utf-8-sig')
print("✓ 示例数据文件创建成功: data/sample_drugs.csv")
'''
            
            # 创建临时脚本文件
            temp_script = Path("create_sample_data_temp.py")
            with open(temp_script, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # 在虚拟环境中运行脚本
            result = subprocess.run([str(venv_python), str(temp_script)], 
                                  capture_output=True, text=True)
            
            # 删除临时脚本
            temp_script.unlink()
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"创建示例数据失败: {result.stderr}")
                
        except Exception as e:
            print(f"创建示例数据异常: {e}")
    else:
        print("虚拟环境不存在，跳过示例数据创建")

def main():
    """主安装函数"""
    print("=" * 50)
    print("药物信息提取项目安装程序")
    print("=" * 50)
    
    # 设置项目目录结构
    setup_project_structure()
    
    # 创建虚拟环境
    if not create_virtual_environment():
        print("虚拟环境创建失败，继续使用系统环境")
    
    # 安装依赖
    install_requirements()
    
    # 创建示例数据
    create_sample_data()
    
    print("\n" + "=" * 50)
    print("安装完成！")
    print("下一步:")
    print("1. 将您的药物数据CSV文件放入 data/ 目录")
    print("2. 运行: python test_project.py 测试项目结构")
    print("3. 运行: python run_extraction_pipeline.py 开始提取")
    print("=" * 50)

if __name__ == "__main__":
    main()
