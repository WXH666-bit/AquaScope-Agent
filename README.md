# AquaScope — 水下生物智能识别与问答系统

面向水生生物识别、图像增强、目标检测与多模态知识问答的本地 Agent 工作台。

支持图文联合问答、图像质量分析、多候选增强、YOLO 目标检测、VLM 视觉识别、**多轮对话记忆**与**宝可梦风格物种卡片**展示。基于双模式检索（TF-IDF + MiniLM 语义）+ 通义千问 LLM/VLM，覆盖 **10 种**水下生物（海星、海胆、海参、扇贝、水母、小丑鱼、蝴蝶鱼、石斑鱼、狮子鱼、鹦嘴鱼）。

---

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（可选，离线模式也可检索）
cp .env.example .env
# 编辑 .env 填入 QWEN_API_KEY=sk-你的key

# 3. 构建向量库
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli build-vector-db

# 4. 启动 Web 界面
python run_app.py
```

启动后访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| Web 界面 | http://localhost:8501 | Streamlit 前端，聊天对话 + 物种卡片 |

---

## 项目架构

```
AquaScope-Agent/
├── src/
│   ├── aquabio/                   # 核心库
│   │   ├── agent.py               # AquaBioAgent：管道编排 + 物种卡片匹配 + 对话上下文
│   │   ├── detector.py            # YOLODetector：YOLO 水下生物目标检测
│   │   ├── retriever.py           # HybridRetriever：TF-IDF + 词汇混合检索
│   │   ├── semantic_retriever.py   # SemanticRetriever：MiniLM 语义向量检索
│   │   ├── vector_store.py        # LocalVectorStore：持久化稀疏向量库
│   │   ├── image_tools.py         # OpenCV 图像质量分析 + 4种增强方法
│   │   ├── openrouter.py          # OpenRouter LLM/VLM 客户端
│   │   ├── gemini.py              # Gemini Vision 客户端
│   │   ├── config.py              # 配置管理（多 provider 支持 + .env 读写）
│   │   ├── cli.py                 # 命令行入口
│   │   ├── pdf_ingest.py          # PDF 文本提取与分块
│   │   └── _patch_starlette.py    # starlette 兼容补丁
│   ├── aquabio_mrag/              # 多模态 RAG 管线
│   │   ├── conversation.py        # ConversationStore：JSON 文件会话持久化
│   │   ├── workflow.py            # LangGraph Agent 工作流（15+ 节点）
│   │   ├── retrieval.py           # MultiSourceRetriever：Chroma+BGE-M3 多源检索
│   │   └── ...
│   └── aquabio_web/               # FastAPI 后端 + Web 存储
│       ├── store.py               # WebStore：SQLite 会话/消息/反馈存储
│       ├── service.py             # ChatService：聊天服务编排
│       └── ...
├── app.py                         # Streamlit Web UI（聊天界面 + 会话管理）
├── run_app.py                     # Web 启动器（必须先打 starlette 补丁再启动）
├── models/                        # YOLO 模型权重（.pt 文件，不提交）
├── tests/                         # 单元测试（7 个文件）
├── data/
│   ├── knowledge/                 # 知识卡片（species_cards.jsonl，13 字段完整元数据）
│   ├── mrag/                      # 多模态数据（图片、PDF、知识块）
│   ├── samples/                   # 样本测试图片
│   ├── sessions/                  # 对话会话持久化（JSON 文件）
│   ├── vector_db/                 # 持久化向量库
│   └── species_images.json        # 物种图片路径映射
├── configs/                       # 配置文件
└── pyproject.toml                 # 项目依赖与构建配置
```

### 核心流程

```
用户输入（聊天 + 可选图片上传）
        │
        ▼
   固定管道（硬编码决策）
   ├─ 图像质量分析（亮度/对比度/清晰度/偏色）
   ├─ 多候选图像增强（白平衡/CLAHE/Gamma）
   ├─ YOLO 目标检测（定位生物区域 / 画框标注）
   ├─ VLM 视觉识别（候选物种/可见特征/退化问题）
   ├─ 混合检索（TF-IDF 或 MiniLM 语义检索，可选）
   ├─ 物种卡片匹配（加权打分 → 过滤低分 → 排序）
   └─ LLM 生成回答（含对话上下文，支持多轮指代消解）
        │
        ▼
   Streamlit 聊天界面展示
   ├─ 聊天气泡：回答 + 宝可梦物种卡片（始终可见）+ YOLO 检测图
   ├─ 折叠面板：增强候选图 + 检索证据 + 工具调用轨迹
   └─ 侧边栏：会话管理（新建/切换/重命名/删除/导出）+ 知识库管理 + API 设置
```

### 多轮对话记忆

系统通过 `ConversationStore`（JSON 文件）实现跨轮次记忆：

- 每轮问答后自动持久化到 `data/sessions/{session_id}.json`
- LLM 系统提示词自动注入上一轮的物种名称、图片描述和用户提问
- 用户说"它有什么特征？"时，系统知道"它"=上一轮识别的海星
- 支持会话切换、重命名、导出 JSON，重启应用后历史仍在

### 物种卡片展示

识别到水下生物后，聊天气泡中自动渲染宝可梦风格信息卡片，包含：

- 🖼️ 物种图片（本地知识库图片）
- 📛 中文名 / 学名 / 分类 / 🎯匹配度
- 📏 体长/体型
- 🌊 栖息地
- 🎨 体色特征描述
- 🔍 识别特征标签
- 📖 物种简介
- 💡 趣味知识

---

## 环境配置

复制 `.env.example` 为 `.env`，填入 API Key：

```ini
# 主 LLM（阿里通义千问）
AQUABIO_LLM_PROVIDER=qwen
QWEN_API_KEY=sk-your-qwen-key-here

# 备选：OpenRouter
AQUABIO_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here

# 备选：Google Gemini
GEMINI_API_KEY=your_gemini_key
```

> `.env` 已在 `.gitignore` 中排除，不会被提交到版本控制。
> 未配置 API Key 时自动进入离线模式，仅展示检索证据不生成模型结论。
> 也可以在 Web 界面左侧边栏 ⚙️ API 设置 中直接输入和保存 API Key，无需手动编辑 `.env` 文件。

---

## CLI 命令

### 向量库管理

```bash
# 构建/重建向量库
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli build-vector-db

# 查看向量库信息
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli vector-db-info

# PDF 入库
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ingest "data/pdfs"
```

### 文本问答

```bash
# 离线模式（无需 API Key）
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "海星有哪些视觉特征？" --offline

# 在线模式（需要 QWEN_API_KEY）
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "海星有哪些视觉特征？"

# 语义检索模式（MiniLM 稠密向量，适合描述性查询）
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "会喷墨汁的动物" --semantic
```

### 图文联合问答

```bash
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "这是什么生物？" --image "data/samples/starfish_01.jpg"
```

---

## 运行测试

```bash
# 运行核心测试
python -m pytest tests/test_core.py -v

# 运行所有测试
python -m pytest tests/ -v
```

---

## 当前数据规模

| 数据类型 | 数量 |
|----------|------|
| 物种卡片 | 10（5种棘皮/软体/腔肠动物 + 5种珊瑚礁鱼类，每张 13 字段完整元数据） |
| 数据集卡片 | 3 |
| PDF 文本块 | 91 |
| 向量总数 | 104 |
| 目标检测类别 | 4（海参/海胆/扇贝/海星，DUO 模型） |

### 10 种水下生物

| 类别 | 物种 |
|------|------|
| 🦔 棘皮动物 | 海星、海胆、海参 |
| 🐚 软体动物 | 扇贝 |
| 🪼 腔肠动物 | 水母 |
| 🐠 珊瑚礁鱼类 | 小丑鱼、蝴蝶鱼、石斑鱼、狮子鱼、鹦嘴鱼 |

---

## 依赖项

- **Python** ≥ 3.10
- **LLM API**：阿里通义千问（默认）、OpenRouter、Google Gemini
- **图像处理**：OpenCV（质量分析 + 增强）
- **目标检测**：Ultralytics YOLOv8（DUO 预训练，4 类水下生物定位画框）
- **向量检索**：双模式 — TF-IDF 稀疏检索（默认）+ MiniLM 语义检索（`--semantic`）
- **对话记忆**：JSON 文件持久化（`ConversationStore`，纯标准库）
- **Web 界面**：Streamlit

完整依赖见 [requirements.txt](requirements.txt) 和 [pyproject.toml](pyproject.toml)。

> ⚠️ 已知问题：新版 starlette 移除了 streamlit 依赖的 `DEFAULT_EXCLUDED_CONTENT_TYPES` 和 `IdentityResponder`。项目通过 `run_app.py` 启动器在 streamlit 加载前自动打补丁，**不要直接运行 `streamlit run app.py`**。

---

## 详细文档

- [系统架构](docs/architecture.md)
- [数据集说明](docs/datasets.md)
- [开源方案对比](docs/open_source_comparison.md)

---

## 安全

`.env.example` 只包含占位 key。任何已经贴到聊天或公开文件中的 API Key 都应立即吊销并重新创建。
