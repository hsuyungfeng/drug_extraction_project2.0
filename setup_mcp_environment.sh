#!/bin/bash

# MCP 环境设置脚本
echo "正在设置 MCP 环境..."

# 检查 Node.js 是否安装
if ! command -v node &> /dev/null; then
    echo "错误: 请先安装 Node.js (https://nodejs.org/)"
    exit 1
fi

# 检查 npm 是否安装
if ! command -v npm &> /dev/null; then
    echo "错误: npm 未安装，请检查 Node.js 安装"
    exit 1
fi

# 安装必要的 MCP 服务器
echo "安装 MCP 服务器..."
npm install -g @modelcontextprotocol/server-google-search
npm install -g @modelcontextprotocol/server-playwright
npm install -g @modelcontextprotocol/server-memory
npm install -g @modelcontextprotocol/server-filesystem

# 安装 Playwright 浏览器
echo "安装 Playwright 浏览器..."
npx playwright install chromium

# 创建环境变量配置文件
echo "创建环境变量配置文件..."
cat > .env << 'EOL'
# Google Search API 配置
# 请从 Google Cloud Console 获取这些值
# https://console.cloud.google.com/
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CX=your_search_engine_id_here

# Ollama 配置 (用于本地 LLM)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b

# 项目路径配置
DATA_DIR=./data
OUTPUT_DIR=./output
LOG_DIR=./logs
EOL

echo "环境设置完成！"
echo ""
echo "下一步："
echo "1. 编辑 .env 文件，填入您的 Google API 密钥和搜索引擎 ID"
echo "2. 确保 Ollama 服务正在运行: ollama serve"
echo "3. 运行测试脚本: python scripts/use_mcp_tool_example.py"
echo ""
echo "要启动 MCP 服务器，可以使用以下命令："
echo "npx -y @modelcontextprotocol/server-google-search"
echo "npx -y @modelcontextprotocol/server-playwright"
echo "npx -y @modelcontextprotocol/server-memory"
echo "npx -y @modelcontextprotocol/server-filesystem"
