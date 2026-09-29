# UniScholar（联智学者）：科研辅助智能体

> **中国国际大学生创新大赛（大创赛）产业赛道 · 产教协同创新组**  
> **命题企业**：中国联合网络通信有限公司浙江省分公司  
> **命题题目**：基于通用智能体的AI科研智能体应用开发  

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 项目简介

帮高校学生和老师处理科研中重复性的工作：检索文献、整理摘要、做数据的初步统计、排参考文献格式。各个步骤串成一个可以暂停、人工修改、再继续的工作流。

## 功能

| 模块 | 做什么 | 怎么做的 |
| :--- | :--- | :--- |
| 文献检索与筛选 | 按研究方向、关键词、年份范围检索文献 | 调用 OpenAlex 和 arXiv 接口，用关键词加权打分（标题命中权重高于摘要）过滤不相关的论文 |
| 信息抽取与综述初稿 | 抽取每篇文献的背景、创新点、方法、结论，生成综述大纲和初稿 | LLM 按 Pydantic Schema 输出结构化结果；初稿中的引用会与检索到的文献池比对 |
| 数据统计与作图 | 上传 CSV / Excel，计算均值、方差、分位数 | 按 IQR 规则标记离群值，用 Matplotlib 画折线图、箱线图、直方图 |
| 参考文献格式化 | 把格式混乱的引文整理成 GB/T 7714-2015 | 检查作者、年份、页码等字段是否缺失；支持 GB/T 7714 / APA / IEEE 之间切换 |
| 暂停与续跑 | 工作流可以在关键节点暂停，让用户修改文献池或大纲后继续 | 每一步的状态保存为本地 JSON 检查点 |

## 系统结构

```
1. 交互层 (Gradio WebUI)
   - 显示工作流各节点状态（就绪 / 运行中 / 暂停 / 完成）
   - 暂停时可人工挑选文献、修改大纲；支持上传 CSV/Excel/Word/PDF
2. 工作流引擎 (core/workflow_engine.py)
   - 自己实现的轻量状态机，按有向无环图编排各个步骤
   - 每步结束写 JSON 检查点，可从断点继续
   - 导出联通元景平台格式的 workflow_config.json 和执行日志
3. 各功能模块 (agents/)
   - LiteratureAgent：OpenAlex + arXiv 检索与关键词打分过滤
   - ReviewAgent：结构化抽取 + 综述大纲与初稿
   - DataAgent：Pandas 描述统计 + IQR 离群值 + Matplotlib 作图
   - ReferenceAgent：GB/T 7714 格式化与多格式切换
4. 基础设施 (utils/)
   - llm_client.py：兼容 OpenAI / DeepSeek 接口
   - citation_validator.py：核对引用是否来自检索到的文献
   - offline_demo/：无网络、无密钥时使用的演示数据
```

---

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/hu-zhixuan/UniScholar.git
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

#### 方式一：WebUI

```bash
python app.py
# 或 Windows 双击运行 run.bat
```
打开浏览器访问 `http://127.0.0.1:7860`。

#### 方式二：命令行

```bash
# 完整运行一遍
python main.py -q "通用智能体科研自动化" -k "AI Agent,Workflow" -y 3 -m 15

# 在大纲生成后暂停，等待用户确认
python main.py --pause

# 从断点继续已暂停的任务
python main.py --resume <task_id>
```

---

## 离线演示

不联网、不需要 API 密钥也能跑完整个流程（使用 `offline_demo/` 中预先准备的文献数据）：

```bash
# Windows PowerShell
$env:OFFLINE_DEMO="1"; python app.py
```
或直接在 CLI 执行：
```bash
python main.py --offline
```
结果输出到 `output/<task_id>_final_report.md` 和 `output/charts/`。

---

## 目录结构

```
UniScholar/
├── core/
│   └── workflow_engine.py      # 工作流引擎：状态机、检查点、暂停/续跑
├── agents/
│   ├── literature_agent.py     # 文献检索与过滤
│   ├── review_agent.py         # 信息抽取与综述生成
│   ├── data_agent.py           # 数据统计与作图
│   └── reference_agent.py      # 参考文献格式化
├── utils/
│   ├── llm_client.py           # LLM 客户端
│   ├── network_config.py       # 国内镜像源配置
│   └── citation_validator.py   # 引用校验
├── config/
│   └── workflow_config.json    # 联通元景平台工作流配置
├── offline_demo/               # 离线演示数据
│   └── demo_data.py
├── web/
│   └── app.py                  # Gradio WebUI 前端应用
├── scripts/                    # 生成比赛提交材料的脚本
├── docs/                       # 技术方案、路演稿
├── tests/                      # 单元测试
├── main.py                     # CLI命令行入口与全流程串联
├── app.py                      # 根目录 WebUI 快速启动入口
├── run.bat                     # Windows 一键启动脚本
├── requirements.txt            # 项目依赖
└── README.md                   # 项目说明文档
```

---

## 局限性

- **文献筛选靠关键词匹配**，不是语义检索。同义词、换一种说法的论文会被漏掉，关键词碰巧重合的无关论文也可能混进来。
- **综述初稿质量取决于 LLM 和摘要。** 抽取只基于标题和摘要，不读全文，"方法""结论"等字段可能不准确，需要人工核对。
- **引用校验只能保证引用的文献真实存在于检索结果中**，不能保证引用内容和原文观点一致。
- **参考文献格式化是规则解析**，遇到格式特别混乱或信息缺失的引文会解析失败或需要手动补全。
- **与联通元景平台的对接目前只到配置文件导出**：代码中没有调用平台接口，LLM 走的是 OpenAI 兼容接口。
- 测试覆盖有限（`tests/test_agents.py` 共 12 个用例）。

## 说明

- 所有数据来自公开的文献平台（OpenAlex / arXiv）和用户自己上传的文件。
- 可以导出联通元景万悟平台格式的 `workflow_config.json` 和执行日志，满足赛题的交付要求。

## 许可证

MIT License
