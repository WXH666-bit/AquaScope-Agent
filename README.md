# AquaScope — 水下生物智能识别与问答系统

面向水生生物识别、图像增强与多模态知识问答的本地 Agent 工作台。

支持图文联合问答、图像质量分析、多候选增强、VLM 视觉识别与**宝可梦风格物种卡片**展示。基于双模式检索（TF-IDF + MiniLM 语义）+ 通义千问 LLM/VLM，覆盖 **20 种**水下生物（棘皮动物、鱼类、软体动物、甲壳类、腔肠动物）。

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
| Web 界面 | http://localhost:8501 | Streamlit 前端，物种卡片 + 问答 |

---

## 项目架构

```
AquaScope-Agent/
├── src/
│   ├── aquabio/                   # 核心库
│   │   ├── agent.py               # AquaBioAgent：管道编排 + 物种卡片匹配
│   │   ├── retriever.py           # HybridRetriever：TF-IDF + 词汇混合检索
│   │   ├── semantic_retriever.py   # SemanticRetriever：MiniLM 语义向量检索
│   │   ├── vector_store.py        # LocalVectorStore：持久化稀疏向量库
│   │   ├── image_tools.py         # OpenCV 图像质量分析 + 4种增强方法
│   │   ├── openrouter.py          # OpenRouter LLM/VLM 客户端
│   │   ├── config.py              # 配置管理（多 provider 支持）
│   │   ├── cli.py                 # 命令行入口
│   │   ├── pdf_ingest.py          # PDF 文本提取与分块
│   │   └── _patch_starlette.py    # starlette 兼容补丁
│   └── aquabio_mrag/              # 多模态 RAG 管线
│       ├── pdf_pipeline.py        # PDF 下载、解析、分块、图谱绑定
│       ├── config.py              # MRAG 路径与设置
│       └── io_utils.py            # JSONL 读写工具
├── app.py                         # Streamlit Web UI（主界面）
├── run_app.py                     # Web 启动器（必须先打 starlette 补丁再启动）
├── scripts/                       # 数据采集与索引构建脚本
│   ├── 01_crawl_wikipedia_worms.py
│   ├── 02_crawl_commons_images.py
│   ├── 03_build_multimodal_documents.py
│   ├── 04_download_parse_pdfs.py
│   └── 05_build_chroma_bge.py
├── tests/                         # 单元测试
│   └── test_core.py
├── data/
│   ├── knowledge/                 # 知识卡片（species_cards.jsonl 等）
│   ├── mrag/                      # 多模态数据（图片、PDF、知识块）
│   ├── samples/                   # 样本测试图片
│   ├── vector_db/                 # 持久化向量库
│   └── species_images.json        # 物种图片路径映射
├── configs/                       # 配置文件
├── docs/                          # 详细技术文档
├── pyproject.toml                 # 项目依赖与构建配置
├── requirements.txt               # pip 依赖清单
└── README.md
```

### 核心流程

```
用户上传图片 + 文字提问
        ↓
   固定管道（硬编码决策）
   ├─ 图像质量分析（亮度/对比度/清晰度/偏色）
   ├─ 多候选图像增强（白平衡/CLAHE/Gamma）
   ├─ VLM 视觉识别（候选物种/可见特征/退化问题）
   ├─ 混合检索（TF-IDF 或 MiniLM 语义检索，可选）
   └─ 物种卡片匹配（加权打分 → 过滤低分 → 排序）
        ↓
   Streamlit 卡片式 UI 展示
   ├─ [左栏] Agent 回答 + 检索证据
   ├─ [右栏] 物种卡片（📏体长 · 🌊栖息地 · 🎨体色 · 🔍特征 · 💡趣味知识）
   └─ [底部] 增强图候选 / 工具调用轨迹
```

### 物种卡片展示

识别到水下生物后，右栏自动渲染宝可梦风格信息卡片，包含：

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
python -m pytest tests/test_core.py -v
```

---

## 当前数据规模

| 数据类型 | 数量 |
|----------|------|
| 物种卡片 | 20 |
| 数据集卡片 | 3 |
| PDF 文本块 | 91 |
| 向量总数 | 114 |
| 物种覆盖 | 棘皮动物(5) · 鱼类(6) · 软体动物(3) · 甲壳类(2) · 腔肠动物(2) · 其他(2) |

### 20 种水下生物

| 类别 | 物种 |
|------|------|
| 🦔 棘皮动物 | 海星、海胆、海参、扇贝、海百合 |
| 🐟 鱼类 | 蝴蝶鱼、小丑鱼、石斑鱼、狮子鱼、天使鱼、鹦嘴鱼、蝠鲼 |
| 🐙 软体动物 | 章鱼、乌贼、海兔 |
| 🦞 甲壳类 | 龙虾、清洁虾 |
| 🌸 腔肠动物 | 海葵、珊瑚、水母 |

---

## 依赖项

- **Python** ≥ 3.10
- **LLM API**：阿里通义千问（默认）、OpenRouter、Google Gemini
- **图像处理**：OpenCV（质量分析 + 增强）
- **向量检索**：双模式 — TF-IDF 稀疏检索（默认）+ MiniLM 语义检索（`--semantic`）
- **Web 界面**：Streamlit

完整依赖见 [requirements.txt](requirements.txt) 和 [pyproject.toml](pyproject.toml)。

> ⚠️ 已知问题：新版 starlette 移除了 streamlit 依赖的 `DEFAULT_EXCLUDED_CONTENT_TYPES` 和 `IdentityResponder`。项目通过 `run_app.py` 启动器在 streamlit 加载前自动打补丁，**不要直接运行 `streamlit run app.py`**。

---

## 详细文档

- [系统架构](docs/architecture.md)
- [数据集说明](docs/datasets.md)
- [开源方案对比](docs/open_source_comparison.md)
- [数据库设计](aquabio_mrag_long_text_database/docs/database_design.md)
- [嵌入向量设计](aquabio_mrag_long_text_database/docs/embedding_vector_design.md)

---

## 安全

`.env.example` 只包含占位 key。任何已经贴到聊天或公开文件中的 API Key 都应立即吊销并重新创建。
