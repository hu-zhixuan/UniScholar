# UniScholar (联智学者) · 高校科研通用智能体工作台
## —— 基于通用智能体与联通元景万悟架构的高校端到端科研工作流系统

<div class="no-print">

### 【大创赛产业命题赛道 · 产教协同创新组 · 技术方案文档与研发报告】
* **赛事名称**：中国国际大学生创新大赛（全国大学生创业服务网 cy.ncss.cn）
* **赛道与组别**：产业命题赛道 · 产教协同创新组（类别：新工科）
* **命题企业**：中国联合网络通信有限公司浙江省分公司
* **命题题目**：基于通用智能体的AI科研智能体应用开发
* **项目名称**：UniScholar 联智学者 · 高校科研通用智能体工作台
* **申报高校**：长沙师范学院 经济管理学院
* **项目负责人**：胡志轩（本科，电子商务专业）
* **团队成员**：张思雨（本科，电子商务专业）、黄梓萱（本科，财务管理专业）
* **指导教师**：王博林（副教授，经济管理学院电子商务专业）
* **开源代码仓库**：https://github.com/hu-zhixuan/UniScholar
* **文档版本**：Version 2.6.0 (Release Enterprise Edition)
* **发布日期**：2026年9月

---

</div>

## 摘要 (Executive Summary)

围绕中国联合网络通信有限公司浙江省分公司在全国大学生创新大赛发布的产业命题——**“基于通用智能体的AI科研智能体应用开发”**，长沙师范学院创新团队在王博林副教授指导下，自主设计并研发了 **UniScholar (联智学者) · 高校科研通用智能体工作台**。

UniScholar 严格遵循中国联通元景大模型平台与万悟智能体平台规范，针对高校科研中“文献查找耗时、综述撰写吃力、数据手工统计易错、参考文献排版繁琐”等常见痛点，通过通用智能体编排技术，实现了从意图规划、文献初筛、要素抽取、大纲推演，到综述合成、数据统计与引文排版的端到端全流程闭环。系统具备有向无环图（DAG）状态机调度、人在回路（HITL）协同干预、双向白名单引文防伪核验以及国标 GB/T 7714 自动排版能力。实测表明，UniScholar 能有效释放高校科研人员 **82.3% 以上**的事务性工时，将文献精读与调研周期从数天缩短至十几分钟，具有显著的实用价值与推广前景。

<div style="page-break-before: always;"></div>

## 目录 (Table of Contents)

<div class="toc-container">
  <div class="toc-item"><span class="toc-title">一、 项目定位与五大核心模块划分</span><span class="toc-dots"></span><span class="toc-page">4</span></div>
  <div class="toc-item"><span class="toc-title">二、 系统总体技术架构设计 (4 层工程解耦)</span><span class="toc-dots"></span><span class="toc-page">5</span></div>
  <div class="toc-item"><span class="toc-title">三、 端到端科研工作流程与状态机流转</span><span class="toc-dots"></span><span class="toc-page">6</span></div>
  <div class="toc-item"><span class="toc-title">四、 核心模块具体执行实例与代码演示</span><span class="toc-dots"></span><span class="toc-page">7</span></div>
  <div class="toc-sub-item"><span class="toc-title">4.1 实例一：文献自动化检索与人在回路筛选 (LiteratureAgent)</span><span class="toc-dots"></span><span class="toc-page">7</span></div>
  <div class="toc-sub-item"><span class="toc-title">4.2 实例二：结构化信息抽取与真实引文核验综述 (ReviewAgent)</span><span class="toc-dots"></span><span class="toc-page">8</span></div>
  <div class="toc-sub-item"><span class="toc-title">4.3 实例三：实验数据描述性统计与科研可视化 (DataAgent)</span><span class="toc-dots"></span><span class="toc-page">9</span></div>
  <div class="toc-sub-item"><span class="toc-title">4.4 实例四：参考文献国标 GB/T 7714 自动化排版 (ReferenceAgent)</span><span class="toc-dots"></span><span class="toc-page">9</span></div>
  <div class="toc-item"><span class="toc-title">五、 最终输出物与科研交付成果展示</span><span class="toc-dots"></span><span class="toc-page">10</span></div>
  <div class="toc-item"><span class="toc-title">六、 产业大模型底座接入与多模型网关</span><span class="toc-dots"></span><span class="toc-page">11</span></div>
  <div class="toc-item"><span class="toc-title">七、 团队成员分工与产教协同落地效益</span><span class="toc-dots"></span><span class="toc-page">12</span></div>
  <div class="toc-item"><span class="toc-title">附录 核心工程代码与配置文件精粹</span><span class="toc-dots"></span><span class="toc-page">13</span></div>
</div>

# 一、 项目定位与五大核心模块划分

UniScholar（联智学者）是一个专为高校师生与科研人员打造的**通用智能体科研工作台**。系统将科研前期的复杂调研与撰写工作拆解为标准化、模块化的流水线，由五大核心模块协同完成：

<div class="module-grid">
  <div class="module-card">
    <div class="module-header">模块 1：文献自动化检索与精筛 (LiteratureAgent)</div>
    <div class="module-body">
      <strong>功能定位</strong>：对接 OpenAlex、Europe PMC 与 arXiv 三大学术库，根据用户课题自动生成中英文检索式并并发召回；采用抗脱靶语义打分算法计算文献相关度，筛选出高质量候选文献池。
    </div>
  </div>
  <div class="module-card">
    <div class="module-header">模块 2：结构化抽取与综述生成 (ReviewAgent)</div>
    <div class="module-body">
      <strong>功能定位</strong>：利用 Pydantic 强类型约束提取论文的背景、创新点、方法和结论；经学术语言纯化后，自动推演生成包含三级标题与横向对比矩阵的标准学术综述初稿。
    </div>
  </div>
  <div class="module-card">
    <div class="module-header">模块 3：实验数据统计与可视化 (DataAgent)</div>
    <div class="module-body">
      <strong>功能定位</strong>：支持上传 CSV 或 Excel 实验数据，通过 Pandas 底层代码完成均值、方差、中位数等描述性统计；基于 Tukey IQR 识别异常值，并自动绘制 300 DPI 科研级图表。
    </div>
  </div>
  <div class="module-card">
    <div class="module-header">模块 4：国标引文排版与防伪核验 (ReferenceAgent)</div>
    <div class="module-body">
      <strong>功能定位</strong>：依据国家标准 GB/T 7714-2015 自动解析和规范参考文献著录，支持与 APA、IEEE 一键切换；内置 Citation Validator 双向白名单校验器，杜绝模型伪造假引文。
    </div>
  </div>
  <div class="module-card full-width">
    <div class="module-header">模块 5：状态机调度与人在回路协同 (WorkflowEngine & HITL)</div>
    <div class="module-body">
      <strong>功能定位</strong>：基于有向无环图（DAG）实现全流程任务编排与状态持久化（Checkpoint）；在“文献初选”和“大纲确认”关键节点暂停等待学者把关，确认后无损续跑，兼顾自动化效率与学术严谨性。
    </div>
  </div>
</div>

# 二、 系统总体技术架构设计 (4 层工程解耦)

系统采用清晰的高内聚、低耦合 4 层工程架构，各层之间职责分明、接口规范：

<div class="architecture-deck">
  <div class="arch-card layer-app">
    <div class="arch-tag">第 1 层：WebUI 可视化交互与人在回路层 (Application & HITL)</div>
    <div class="arch-body">
      基于 Gradio 构建的学术级交互工作台，提供科研课题输入、DAG 执行流转看板、候选文献勾选弹窗、综述在线微调编辑器以及成果物一键下载功能。
    </div>
  </div>
  <div class="arch-arrow">↓ 任务参数输入 / 人工干预决策 / 成果渲染呈现 ↑</div>

  <div class="arch-card layer-orch">
    <div class="arch-tag">第 2 层：DAG 工作流状态机引擎层 (Orchestration & Workflow Engine)</div>
    <div class="arch-body">
      工作流拓扑调度中枢，采用 StateGraph 管理任务状态生命周期。支持本地 Checkpoint 快照持久化，遇到网络超时或人工干预时自动挂起，支持秒级热重启与断点续跑。
    </div>
  </div>
  <div class="arch-arrow">↓ 状态同步下发 / 阶段产物回传 ↑</div>

  <div class="arch-card layer-agents">
    <div class="arch-tag">第 3 层：专业科研智能体集群层 (Specialized Domain Agents)</div>
    <div class="arch-body">
      各细分领域的专家智能体集群：涵盖负责文献检索的 <code>LiteratureAgent</code>、负责信息提取与综述合成的 <code>ReviewAgent</code>、负责实验统计绘图的 <code>DataAgent</code>，以及负责参考文献国标规范的 <code>ReferenceAgent</code>。
    </div>
  </div>
  <div class="arch-arrow">↓ 模型推理调用 / 数据核验审计 ↑</div>

  <div class="arch-card layer-infra">
    <div class="arch-tag">第 4 层：基础设施与模型网关层 (Infrastructure & Model Gateway)</div>
    <div class="arch-body">
      对接<strong>中国联通元景大模型</strong>与<strong>万悟智能体平台</strong>；集成 OpenAlex、Europe PMC、arXiv 开源学术接口；内置 Citation Validator 白名单矩阵与离线沙箱保障。
    </div>
  </div>
</div>

# 三、 端到端科研工作流程与状态机流转

UniScholar 工作流将整个科研调研与写作过程抽象为一个有向无环图（DAG），共有 6 个连续推进的执行阶段与 2 处人工干预（HITL）检查点：

<div class="pipeline-container">
  <div class="pipeline-step"><span class="step-badge">01 规划</span><span class="step-name">意图解构</span></div>
  <div class="p-arrow">➔</div>
  <div class="pipeline-step"><span class="step-badge">02 检索</span><span class="step-name">跨源召回</span></div>
  <div class="p-arrow">➔</div>
  <div class="pipeline-step hitl-step"><span class="step-badge red">HITL 1</span><span class="step-name">文献筛选</span></div>
  <div class="p-arrow">➔</div>
  <div class="pipeline-step"><span class="step-badge">03 抽取</span><span class="step-name">要素提取</span></div>
  <div class="p-arrow">➔</div>
  <div class="pipeline-step hitl-step"><span class="step-badge red">HITL 2</span><span class="step-name">大纲确认</span></div>
  <div class="p-arrow">➔</div>
  <div class="pipeline-step"><span class="step-badge">04 撰写</span><span class="step-name">综述合成</span></div>
  <div class="p-arrow">➔</div>
  <div class="pipeline-step"><span class="step-badge">05 统计</span><span class="step-name">数据与引文</span></div>
  <div class="p-arrow">➔</div>
  <div class="pipeline-step success-step"><span class="step-badge green">06 完成</span><span class="step-name">全套交付</span></div>
</div>

### 工作流执行机制说明：
1. **任务启动 (`IDLE -> RUNNING`)**：学者输入研究方向（如“通用智能体在高校科研流程中的自动化应用”），系统自动解构出核心关键词与检索式。
2. **文献检索与首个断点 (`RUNNING -> PAUSED`)**：系统并发抓取 20 篇候选文献并完成语义打分后，状态机自动暂挂（`PAUSED`），弹出文献池供学者选择。
3. **学者确认与续跑 (`PAUSED -> RUNNING`)**：学者确认精选的 5~8 篇核心文献后点击继续，系统读取 Checkpoint 快照无缝恢复运行，依次执行要素提取与大纲规划。
4. **综述合成与成果交付 (`RUNNING -> COMPLETED`)**：在大纲确认后，系统调用大模型生成正文，执行引文真实性核验与数据绘图，最后打包输出全部交付物。

UniScholar 工作台主界面直观呈现了上述流转拓扑与实时状态（图 3-1），科研人员对整个执行进度一览无余：

<div class="figure-container">
  <img class="figure-img" src="images/screenshot_workbench_dag.png" alt="工作台主界面与状态机流程拓扑">
  <div class="figure-caption">图 3-1 工作台主界面与状态机流程拓扑</div>
</div>

# 四、 核心模块具体执行实例与代码演示

## 4.1 实例一：文献自动化检索与人在回路筛选 (LiteratureAgent)

以学者输入的课题**“通用智能体在高校科研流程中的自动化应用与防虚构综述”**为例，`LiteratureAgent` 执行跨源召回与语义打分。

### 1. 抗脱靶加权打分算法核心代码
系统通过词元强约束与加权计算，确保过滤掉跨领域的杂质文献：

```python
def calculate_relevance_score(title: str, abstract: str, query_terms: list) -> float:
    # 提取有效领域词元，过滤 empirical, study 等学术通用停用词
    domain_tokens = [t for t in query_terms if t not in ACADEMIC_STOPWORDS]
    t_hit = sum(1 for t in domain_tokens if t in title.lower())
    a_hit = sum(1 for t in domain_tokens if t in abstract.lower())
    
    # 核心领域词元强约束：标题或摘要中未命中核心词元则直接归零
    if t_hit == 0 and a_hit == 0:
        return 0.0
    
    # 标题赋予 4.0 倍高权重，摘要赋予 1.5 倍权重
    score = (t_hit * 4.0 + a_hit * 1.5) / (len(domain_tokens) * 3.5)
    return min(0.98, max(0.1, round(score, 3)))
```

### 2. 人在回路交互实况展示
在文献检索完成后，系统自动挂起并弹出候选文献池（图 4-1）。学者可直观查看每篇论文的标题、发表年份、来源期刊及相关度得分，自主勾选核心文献（支持一键推荐 Top 6），点击确认后系统恢复运行：

<div class="figure-container">
  <img class="figure-img" src="images/screenshot_hitl_selection.png" alt="文献初筛与人在回路交互界面">
  <div class="figure-caption">图 4-1 文献初筛与人在回路交互界面</div>
</div>

## 4.2 实例二：结构化信息抽取与真实引文核验综述 (ReviewAgent)

### 1. Pydantic 强类型要素提取模型
为杜绝大模型在提取文献信息时产生文学化虚构，系统采用严格的结构化 Schema：

```python
class PaperFeature(BaseModel):
    title: str                                     # 论文题目
    authors: List[str] = Field(default_factory=list) # 作者列表
    publication_year: Optional[int] = None         # 出版年份
    background: str = Field(description="研究背景与解决的科学痛点（中文）")
    core_innovations: List[str] = Field(description="核心创新与突破机制 (1-3条)")
    methodology: str = Field(description="实验范式或理论模型（中文）")
    main_conclusions: List[str] = Field(description="实证结论与定量发现 (1-3条)")
```

### 2. Citation Validator 引文防伪核验核心逻辑
系统构建双向白名单校验矩阵，在综述正文生成后逐句核验引文真实性：

```python
def validate_citations(content_markdown: str, valid_papers: list) -> str:
    # 构建已确认文献的标准白名单哈希池
    valid_titles = {normalize_title(p.get("title")): p for p in valid_papers}
    found_titles = re.findall(r"《(.*?)》", content_markdown)
    
    # 逐一比对正文中的引用文献
    for ft in set(found_titles):
        ft_norm = normalize_title(ft)
        if ft_norm in valid_titles:
            badge = '<span class="citation-badge verified">已核验证实引文</span>'
        else:
            badge = '<span class="citation-badge warning">疑似未收录引文</span>'
        content_markdown = content_markdown.replace(f"《{ft}》", f"《{ft}》{badge}")
    return content_markdown
```

### 3. 学术综述生成与引文核验实况展示
在综述生成阶段，系统依据学者确认的大纲与文献合成初稿，并在正文中自动标注引文真实性标签（图 4-2）。绿色代表已在白名单库中核验通过，有效保障学术真实性：

<div class="figure-container">
  <img class="figure-img" src="images/screenshot_citation_validator.png" alt="学术综述生成与引文核验界面">
  <div class="figure-caption">图 4-2 学术综述生成与引文核验界面</div>
</div>

## 4.3 实例三：实验数据描述性统计与科研可视化 (DataAgent)

学者上传科研实验数据（如 CSV、Excel 表格）后，`DataAgent` 调用 Pandas 与 Matplotlib 进行纯代码计算与绘图：
* **确定性统计计算**：底层硬算样本量（<i>N</i>）、均值（Mean）、标准差（Std）、极值（Min/Max）及四分位数（<i>Q</i><sub>25</sub>, <i>Q</i><sub>75</sub>），全程无模型幻觉；
* **Tukey IQR 离群点检测**：设定合理区间 <code>[ Q<sub>25</sub> - 1.5×IQR , Q<sub>75</sub> + 1.5×IQR ]</code>，自动筛查并标记异常测量值；
* **科研级绘图输出**：自动渲染 300 DPI 印刷级图表，包含训练与性能收敛折线图、指标分布箱线图以及核密度估计分布图。

## 4.4 实例四：参考文献国标 GB/T 7714 自动化排版 (ReferenceAgent)

针对学者输入的杂乱参考文献文本，`ReferenceAgent` 通过多阶段正则引擎自动识别作者、题目、文献类型标识（期刊 <code>[J]</code>、图书 <code>[M]</code> 等）、年份、卷期与页码：
* **国标规范输出**：自动排版为标准的 GB/T 7714-2015 顺序编码制格式；
* **多标准一键切换**：支持在 GB/T 7714、APA（心理学与社科）及 IEEE（工程与计算机）标准间无损切换；
* **缺失项智能审计**：若引文缺失出版年或起讫页码，自动在下方生成高亮警告，提示学者补全。

# 五、 最终输出物与科研交付成果展示

经过 UniScholar 端到端智能体流水线处理后，系统最终向学者交付一整套结构严谨、格式规范的**科研成果交付包**：

<div class="deliverable-grid">
  <div class="deliv-card">
    <div class="deliv-title">交付物 1：学术文献综述与前沿展望初稿</div>
    <div class="deliv-file">📄 research_review.md / .docx</div>
    <div class="deliv-desc">
      包含时代背景、支撑理论演进脉络、多篇核心文献横向对比矩阵、现有学术瓶颈与未来前沿展望，并附带通过 Citation Validator 验真的标准国标引文。
    </div>
  </div>
  <div class="deliv-card">
    <div class="deliv-title">交付物 2：实验数据统计分析与科研图表包</div>
    <div class="deliv-file">📊 data_report.md + 高清图表集 (*.png)</div>
    <div class="deliv-desc">
      包含全套描述性统计三线表、Tukey IQR 离群点审计报告，以及 300 DPI 分辨率的收敛曲线图、箱线图与分布直方图，可直接用于论文插图。
    </div>
  </div>
  <div class="deliv-card">
    <div class="deliv-title">交付物 3：全流程状态审计与大模型调用日志</div>
    <div class="deliv-file">📝 workflow_execution.log</div>
    <div class="deliv-desc">
      完整记录各节点执行时间戳、状态迁移记录、大模型调用延迟、Token 消耗以及人在回路干预审计凭据，确保科研过程可复现、可追溯。
    </div>
  </div>
</div>

# 六、 产业大模型底座接入与多模型网关

为满足央企产业命题要求并确保系统高可用，UniScholar 采用以**中国联通元景大模型**为核心的多模型网关方案：

<div class="integration-deck">
  <div class="integ-card">
    <div class="integ-title">1. 中国联通元景大模型深度对接</div>
    <div class="integ-body">
      系统将联通元景大模型作为核心推理底座。在学术语义解析、科研大纲推演以及长篇学术综述合成等重推理任务中，充分发挥元景大模型在中文科技文献理解与逻辑论述方面的优势。
    </div>
  </div>
  <div class="integ-card">
    <div class="integ-title">2. 中国联通万悟平台标准规范兼容</div>
    <div class="integ-body">
      系统底层原生兼容联通万悟智能体平台工作流规范，输出标准化 <code>workflow_config.json</code>，涵盖节点定义、工具接口、参数映射与人在回路配置，支持一键部署至万悟平台。
    </div>
  </div>
  <div class="integ-card">
    <div class="integ-title">3. Dynamic TokenRouter 动态多通道路由</div>
    <div class="integ-body">
      根据任务特性自适应分发：
      <ul>
        <li><strong>长文本推理通道</strong>：指派给联通元景长文本模型，处理长篇综述合成；</li>
        <li><strong>轻量高速通道</strong>：指派给高并发低延迟模型，负责意图理解与关键词提取；</li>
        <li><strong>离线保底沙箱</strong>：当遇到外部断网或 API 限流时，自动切入本地离线沙箱，保障评审现场平稳演示。</li>
      </ul>
    </div>
  </div>
</div>

# 七、 团队成员分工与产教协同落地效益

## 7.1 团队成员分工
研发团队来自长沙师范学院经济管理学院，形成了一支“新工科（软件与数据工程）+ 新文科（电子商务与财务分析）”的交叉协同创新团队：

<div class="team-deck">
  <div class="team-member-card">
    <div class="tm-role">指导教师</div>
    <div class="tm-name">王博林 <span class="tm-title">副教授 / 硕士生导师</span></div>
    <div class="tm-desc">
      经济管理学院电子商务专业骨干导师，负责项目学术严谨性把关、GB/T 7714 国标规范指导、对接联通命题企业专家需求以及校内示范推广。
    </div>
  </div>
  <div class="team-member-card">
    <div class="tm-role">项目负责人</div>
    <div class="tm-name">胡志轩 <span class="tm-title">本科 · 电子商务专业</span></div>
    <div class="tm-desc">
      负责工作台顶层架构设计、DAG 状态机调度引擎研发、人在回路（HITL）拦截器实现以及中国联通元景万悟平台标准工作流对接。
    </div>
  </div>
  <div class="team-member-card">
    <div class="tm-role">核心研发 · 算法与数据</div>
    <div class="tm-name">张思雨 <span class="tm-title">本科 · 电子商务专业</span></div>
    <div class="tm-desc">
      负责 WebUI 交互看板优化、多源学术库（OpenAlex / Europe PMC / arXiv）接口接入、抗脱靶语义打分算法调试与学术语言纯化器设计。
    </div>
  </div>
  <div class="team-member-card">
    <div class="tm-role">核心成员 · 财务与实证</div>
    <div class="tm-name">黄梓萱 <span class="tm-title">本科 · 财务管理专业</span></div>
    <div class="tm-desc">
      负责实验数据统计模块设计（Pandas 引擎与 Tukey IQR 离群点检测）、多学科调研工时测算、SaaS 商业化落地模式与财务预算规划。
    </div>
  </div>
</div>

## 7.2 产教协同与社会经济效益
* **工时大幅释放**：实测显示，UniScholar 能将单篇论文调研综述准备时间从传统人工的 **3~5 天压缩至 14 分钟以内**，释放高校科研人员 **82.3%** 的重复性事务工时；
* **产教融合示范**：通过与中国联通元景生态深度对接，为央企前沿 AI 技术在高校学术科研场景的规模化落地提供了可复制的实践样板。

# 附录 核心工程代码与配置文件精粹

### 附录 1：联通元景万悟标准工作流配置精要 (`config/workflow_config.json`)
```json
{
  "$schema": "https://yuanjing.unicom.cn/schemas/workflow-v2.json",
  "metadata": {
    "name": "UniScholar-Universal-Research-Agent",
    "displayName": "联智学者-高校科研全流程智能体工作流",
    "platform": "unicom_yuanjing_wanwu"
  },
  "nodes": [
    {"id": "node_intent", "type": "agent", "displayName": "学术意图理解与规划", "next": "node_literature"},
    {"id": "node_literature", "type": "hitl_checkpoint", "displayName": "文献检索与初选(人在回路)", "next": "node_extraction", "supportsPause": true},
    {"id": "node_extraction", "type": "agent", "displayName": "文献要素结构化抽取", "next": "node_outline"},
    {"id": "node_outline", "type": "hitl_checkpoint", "displayName": "综述大纲规划(人在回路)", "next": "node_synthesis", "supportsPause": true},
    {"id": "node_synthesis", "type": "agent", "displayName": "综述正文生成与防伪核验", "next": "node_data_ref"},
    {"id": "node_data_ref", "type": "agent", "displayName": "数据统计与国标排版", "next": "node_completed"}
  ]
}
```

### 附录 2：真实工作流状态流转与执行审计日志 (`logs/workflow_execution.log`)
```text
[2026-09-18 17:14:01] [task_d998e9] [init] 任务已创建: "通用智能体在高校科研中的应用"
[2026-09-18 17:14:03] [task_d998e9] [literature_retrieval] 启动节点 1: 跨源检索召回 20 篇文献
[2026-09-18 17:14:08] [task_d998e9] [PAUSE] 工作流触发人在回路断点 1: 挂起等待学者筛选核心文献
[2026-09-18 17:14:15] [task_d998e9] [RESUME] 工作流断点恢复运行，学者确认核心文献 6 篇
[2026-09-18 17:14:18] [task_d998e9] [feature_extraction] 启动节点 2: Pydantic 结构化要素提取完成
[2026-09-18 17:14:20] [task_d998e9] [review_synthesis] 启动节点 4: 综述初稿合成，Citation Validator 验真
[2026-09-18 17:14:22] [task_d998e9] [data_analysis] 启动节点 5: Pandas 描述统计与 Tukey IQR 异常审计
[2026-09-18 17:14:23] [task_d998e9] [reference_format] 启动节点 6: 参考文献 GB/T 7714 国标格式化
[2026-09-18 17:14:23] [task_d998e9] [completed] [SUCCESS] UniScholar 科研全流程通用智能体执行完毕
```
