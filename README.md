# CodeU —— 基于 LangGraph 的本地编码助手 Beta（WIP）

一个使用 LangGraph + LangChain 构建的 ReAct 风格编码代理（Coding Agent）。它通过一组安全受控的工具（文件系统查询、文本替换编辑、终端执行等）来理解你的指令并在本地代码库中自动化操作。

## 功能特性
- ReAct 风格多步骤推理与工具调用
- 内置工具：
  - grep/ls/tree：便捷、安全地查看与搜索文件系统
  - text_editor：对文件内容进行文本替换编辑（带安全限制）
  - bash：受控地执行常用终端命令
- LangGraph CLI 提供 Web UI 与 CLI 双入口，支持多轮对话与状态保存

## 项目结构
- src/codeu/
  - app_graph.py：对外暴露 `graph`，供 LangGraph CLI 加载
  - __init__.py：创建并配置编码代理（工具、提示词、记忆器等）
  - models/chat_model.py：LLM 模型初始化
  - tools/：内置工具实现（editor/fs/terminal）
- langgraph.json：LangGraph CLI 配置，指定加载 `graph`
- pyproject.toml：项目元数据与依赖

## 运行要求
- Python 3.13+
- 建议使用 uv 管理依赖（也可用 pip）

## 快速开始
1) 克隆项目并进入目录
2) 安装依赖
   - 使用 uv：
     - 安装 uv（如已安装可跳过）
     - 在项目根目录执行：
       - `uv sync`（或 `uv pip install -e .`）
   - 使用 pip：
     - `pip install -e .`
3) 配置环境变量
   - 在项目根目录创建 `.env` 文件（示例）：
     ```ini
     ARK_API_KEY=你的密钥
     ```
4) 启动开发服务器（Web UI）
   - `uv run langgraph dev`
   - 打开浏览器访问：`http://127.0.0.1:2024/`
5) 在 Web UI 中直接输入需求，例如：
   - “在 src 目录里查找所有包含 TODO 的行”
   - “把 README 中的某处文本替换为最新描述”
   - “列出项目根目录的树状结构”

## 使用说明
- 代理会优先使用安全的文件系统工具（ls/grep/tree）与文本编辑工具（text_editor）。
- 终端工具（bash）仅用于必要且安全的命令；请避免危险操作（删除系统文件、重启等）。
- 提示词要尽量明确，例如：
  - 指定要查找的目录与关键词
  - 指定编辑的文件、替换的旧文本与新文本

## 常见问题
- Web UI 无法访问：
  - 确认命令已成功运行：`uv run langgraph dev`
  - 检查端口占用或代理设置
- API Key 报错或模型不可用：
  - 确保 `.env` 已设置并在运行环境中生效
  - 检查 `base_url` 与 `model` 是否正确
- 文本编辑未生效：
  - 说明更清晰的替换范围与内容
  - 确认文件路径正确，并具有写入权限
