# 🎓 UniScholar (联智学者) - 通用AI科研智能体应用系统

> **中国国际大学生创新大赛（大创赛）产业赛道 · 产教协同创新组**  
> **命题企业**：中国联合网络通信有限公司浙江省分公司  
> **命题题目**：基于通用智能体的AI科研智能体应用开发  

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture: StateGraph](https://img.shields.io/badge/Architecture-StateGraph%20DAG-orange.svg)]()
[![Platform: Yuanjing Wanwu](https://img.shields.io/badge/Platform-China%20Unicom%20Yuanjing-red.svg)]()

---

## 📖 项目简介

当前高校师生在开展科研工作时，普遍面临文献检索量大、摘要整理耗时、实验数据统计繁琐、参考文献格式不规范、科研流程重复性劳动多等痛点。

**UniScholar (联智学者)** 深度融合**通用智能体自动化工作流框架**与**联通元景/万悟平台标准**，将流程编排、任务递归、工具链调用与状态机持久化能力深度结合，构建面向高校科研全场景的端到端闭环自动化智能体系统。

---

## ✨ 五大核心功能特性

| 模块 | 核心能力 | 技术亮点 |
| :--- | :--- | :--- |
| 🔍 **文献自动化检索与递归筛选** | 基于研究方向、关键词与期刊范围，通过 OpenAlex 与 arXiv 接口递归抓取 | 自动计算语义相关度并过滤低相关“水文”，形成高精准文献池 |
| 📑 **核心信息抽取与综述生成** | 自动提取文献标题、作者、**背景、创新点、方法、结论** | Pydantic Schema 强类型防幻觉约束；自动生成三级综述大纲与带真实引文的初稿 |
| 📊 **实验数据初步统计与科研可视化** | 支持上传科研数据表格（CSV / Excel），自动计算均值/方差/分位数 | **IQR 规则自动标记离群异常值**；Matplotlib 自动渲染生成科研级折线图、箱线图、直方图 |
| 📐 **参考文献国标自动格式化与校对** | 自动解析杂乱引文，对标 **GB/T 7714-2015** 规范排版纠错 | 检查作者、年份、页码缺失；支持 **GB/T 7714 / APA / IEEE** 一键无损切换 |
| 🛑 **断点续跑与人在回路 (HITL)** | 工作流支持任务随时暂停、持久化保存状态检查点 (Checkpoints) | **允许用户在网页端人工修改文献池或综述大纲，随后无损断点续跑** |

---

## 🏛️ 系统架构 (4 层解耦设计)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 可视化交互层 (WebUI / Gradio)                                            │
│    - DAG 工作流执行拓扑图实时监控 (就绪 / 运行中 / 暂停修改 / 已完成)         │
│    - 人在回路 (HITL) 介入面板 + 文件上传 (CSV/Excel/Word/PDF)                │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. 工作流状态机引擎 (Workflow Engine - 系统大脑)                             │
│    - 基于 StateGraph 拓扑编排任务节点                                        │
│    - 本地 Checkpoint JSON 序列化持久化，支持容灾与断点无损续跑               │
│    - 自动导出符合联通元景标准的 workflow_config.json 与执行日志              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. 专业智能体工具层 (Specialized Domain Agents)                              │
│    - LiteratureAgent (OpenAlex + arXiv 递归检索 + 语义精筛)                  │
│    - ReviewAgent (Pydantic 结构化抽取 + 综述大纲正文生成)                    │
│    - DataAgent (Pandas 描述统计 + IQR 异常值审计 + Matplotlib 科研绘图)      │
│    - ReferenceAgent (GB/T 7714-2015 格式化 + 多格式一键切换)                │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. 基础设施与安全保障 (Infrastructure & Trust Gateway)                      │
│    - 模型网关 (llm_client.py)：适配 OpenAI/DeepSeek 协议，预留元景标准       │
│    - 引文防幻觉校验器 (citation_validator.py)：真实文献双向比对，杜绝伪造    │
│    - 离线免 Key 评审包 (offline_demo/)：无网络/无Key环境下秒级运行演示       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd UniScholar
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的大模型 API 密钥（支持 DeepSeek / 通义千问 / 联通元景）：

```ini
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

### 3. 运行系统

#### 方式一：WebUI 可视化交互（推荐演示）

```bash
python app.py
# 或 Windows 双击运行 run.bat
```
打开浏览器访问 `http://127.0.0.1:7860` 即可体验全流程。

#### 方式二：CLI 命令行全流程

```bash
# 全流程自动化运行
python main.py -q "通用智能体科研自动化" -k "AI Agent,Workflow" -y 3 -m 15

# 开启人在回路断点 (在大纲生成后自动暂停等待用户确认)
python main.py --pause

# 恢复已暂停的任务断点续跑
python main.py --resume <task_id>
```

---

## ⚡ 评委无密钥离线演示模式 (评审友好)

为应对比赛盲审、现场答辩断网或无 API Key 测评的极端情况，系统内置了**学术脱机演示数据包**，无需联网、零 API 消耗、秒级走完全流程：

```bash
# Windows PowerShell
$env:OFFLINE_DEMO="1"; python app.py
```
或直接在 CLI 执行：
```bash
python main.py --offline
```
产物将秒级输出至 `output/<task_id>_final_report.md` 和 `output/charts/`。

---

## 📁 项目目录结构

```
UniScholar/
├── core/
│   └── workflow_engine.py      # DAG工作流引擎：状态机、Checkpoints持久化、断点暂停/续跑
├── agents/
│   ├── literature_agent.py     # 功能1: 文献递归检索与语义过滤 Agent
│   ├── review_agent.py         # 功能2: 核心信息抽取与综述大纲生成 Agent
│   ├── data_agent.py           # 功能3: 实验数据统计与科研绘图 Agent
│   └── reference_agent.py      # 功能4: GB/T 7714 参考文献排版与校对 Agent
├── utils/
│   ├── llm_client.py           # 通用模型客户端（自适应并预留元景标准）
│   ├── network_config.py       # 国内镜像源与网络引导
│   └── citation_validator.py   # Citation Validator 引文防幻觉校验器
├── config/
│   └── workflow_config.json    # 联通元景万悟通用智能体工作流标准配置文件
├── offline_demo/               # 离线真实学术脱机演示包
│   └── demo_data.py
├── logs/                       # 赛题要求的通用智能体执行日志
│   └── workflow_execution.log
├── web/
│   └── app.py                  # Gradio WebUI 前端应用
├── output/                     # 最终成果研报与生成的科研图表
├── main.py                     # CLI命令行入口与全流程串联
├── app.py                      # 根目录 WebUI 快速启动入口
├── run.bat                     # Windows 一键启动脚本
├── requirements.txt            # 项目依赖
└── README.md                   # 项目说明文档
```

---

## 📄 赛题合规说明

1. **数据安全**：本系统 100% 依托公开文献平台（OpenAlex / arXiv）、公开科研数据集与国标文档构建知识库，绝不涉及任何涉密敏感数据。
2. **规范导出**：系统原生支持导出联通元景万悟智能体平台配置文件 `workflow_config.json` 与状态流转日志 `workflow_execution.log`，完全满足产业赛道成果交付规范。

## 📜 许可证

MIT License
