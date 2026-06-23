from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Patch starlette before importing streamlit
import aquabio._patch_starlette  # noqa: F401

import streamlit as st

from aquabio.agent import AquaBioAgent
from aquabio.pdf_ingest import ingest_directory
from aquabio.vector_store import LocalVectorStore

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="AquaScope — 水下生物智能识别",
    page_icon="🔬",
    layout="wide",
)

# ── Custom CSS for species card styling ──────────────────────────────
st.markdown(
    """
<style>
.species-card {
    border: 2px solid #4fc3f7;
    border-radius: 16px;
    padding: 0;
    overflow: hidden;
    background: linear-gradient(135deg, #e0f7fa 0%, #e8f5e9 100%);
    box-shadow: 0 4px 16px rgba(0, 150, 200, 0.15);
}
.species-card-header {
    background: linear-gradient(135deg, #0288d1 0%, #26c6da 100%);
    color: white;
    padding: 1rem 1.2rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.species-card-header .emoji {
    font-size: 2rem;
}
.species-card-header .name-block h2 {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 700;
}
.species-card-header .name-block p {
    margin: 2px 0 0 0;
    font-size: 0.8rem;
    opacity: 0.85;
}
.species-card-body {
    padding: 1rem 1.2rem;
}
.species-card-body .attr-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 0.7rem;
}
.species-card-body .attr-item {
    flex: 1;
    background: white;
    border-radius: 10px;
    padding: 0.5rem 0.7rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.species-card-body .attr-item .label {
    font-size: 0.7rem;
    color: #666;
}
.species-card-body .attr-item .value {
    font-size: 0.9rem;
    font-weight: 600;
    color: #333;
}
.species-card-body .section-title {
    font-size: 0.8rem;
    font-weight: 700;
    color: #0288d1;
    margin: 0.6rem 0 0.3rem 0;
}
.species-card-body .section-text {
    font-size: 0.85rem;
    color: #444;
    line-height: 1.5;
}
.species-card-body .feature-tag {
    display: inline-block;
    background: #b3e5fc;
    color: #01579b;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    margin: 2px 4px 2px 0;
}
.species-card-body .fun-fact-box {
    background: #fff8e1;
    border-left: 3px solid #ffb300;
    padding: 0.5rem 0.8rem;
    border-radius: 0 8px 8px 0;
    margin-top: 0.5rem;
    font-size: 0.82rem;
    color: #5d4037;
}
.no-species-hint {
    background: #f5f5f5;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
    color: #999;
}
</style>
""",
    unsafe_allow_html=True,
)


def render_species_card(card: dict):
    """Render a Pokemon-style species information card using Streamlit."""
    with st.container():
        # ── Header with gradient ──
        species_emoji = {
            "starfish": "⭐", "echinus": "🦔", "holothurian": "🥒",
            "scallop": "🐚", "jellyfish": "🪼", "butterflyfish": "🦋",
            "clownfish": "🤡", "grouper": "🐟", "lionfish": "🦁",
            "angelfish": "👼", "parrotfish": "🦜", "manta_ray": "🦇",
            "octopus": "🐙", "cuttlefish": "🦑", "nudibranch": "🐌",
            "lobster": "🦞", "cleaner_shrimp": "🦐", "feather_star": "🪶",
            "sea_anemone": "🌸", "coral": "🪸",
        }
        emoji = species_emoji.get(card.get("class_name", ""), "🔬")

        st.markdown(
            f"""
<div class="species-card">
<div class="species-card-header">
    <span class="emoji">{emoji}</span>
    <div class="name-block">
        <h2>{card.get('chinese_name', '未知物种')}</h2>
        <p>{card.get('scientific_name', '')} &nbsp;|&nbsp; {card.get('category', '')} &nbsp;|&nbsp; 🎯 匹配度 {card.get('match_score', '?')}</p>
    </div>
</div>
<div class="species-card-body">
""",
            unsafe_allow_html=True,
        )

        # ── Image ──
        if card.get("image_path") and Path(card["image_path"]).exists():
            st.image(card["image_path"], use_container_width=True)
        elif card.get("image_path"):
            st.image(card["image_path"], use_container_width=True)

        # ── Attribute metrics ──
        size_val = card.get("size", "未知")
        habitat_val = card.get("habitat", "未知")
        st.markdown(
            f"""
<div class="attr-row">
    <div class="attr-item">
        <div class="label">📏 体长/体型</div>
        <div class="value">{size_val}</div>
    </div>
    <div class="attr-item">
        <div class="label">🌊 栖息地</div>
        <div class="value">{habitat_val}</div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        # ── Color pattern ──
        if card.get("color_pattern"):
            st.markdown(
                f"""<div class="section-title">🎨 体色特征</div>
<div class="section-text">{card['color_pattern']}</div>""",
                unsafe_allow_html=True,
            )

        # ── Visual features ──
        if card.get("visual_features"):
            tags_html = " ".join(
                f'<span class="feature-tag">{f}</span>'
                for f in card["visual_features"]
            )
            st.markdown(
                f"""<div class="section-title">🔍 识别特征</div>
<div>{tags_html}</div>""",
                unsafe_allow_html=True,
            )

        # ── Body content excerpt ──
        if card.get("content"):
            st.markdown(
                f"""<div class="section-title">📖 简介</div>
<div class="section-text">{card['content'][:300]}</div>""",
                unsafe_allow_html=True,
            )

        # ── Fun fact ──
        if card.get("fun_fact"):
            st.markdown(
                f"""<div class="fun-fact-box">💡 <b>趣味知识：</b>{card['fun_fact']}</div>""",
                unsafe_allow_html=True,
            )

        st.markdown("</div></div>", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔬 AquaScope")
    st.caption("水下生物智能识别与问答系统")
    st.divider()

    st.subheader("📚 知识库管理")
    pdfs = st.file_uploader(
        "上传 PDF 扩充知识库",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if st.button("📥 写入 PDF 知识库", disabled=not pdfs, use_container_width=True):
        pdf_dir = ROOT / "data" / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        for uploaded in pdfs:
            (pdf_dir / uploaded.name).write_bytes(uploaded.getvalue())
        count = ingest_directory(pdf_dir, ROOT / "data/index/pdf_chunks.jsonl")
        manifest = LocalVectorStore(ROOT / "data/vector_db").build(
            ROOT / "data/knowledge", ROOT / "data/index"
        )
        st.success(
            f"✅ 已生成 {count} 个 PDF chunk，写入 {manifest['vector_count']} 条向量。"
        )

    with st.expander("💡 使用提示"):
        st.markdown(
            """
- 上传水下生物图片，系统自动分析图像质量并识别物种
- 也可以在问题框中直接文字提问
- 识别结果会以卡片形式展示物种详细信息
- 所有回答基于本地知识库和视觉分析结果
"""
        )

    st.divider()
    st.caption(f"📁 知识库物种数：20 种")
    st.caption(f"🖼️ 样本图片：5 张")

# ── Main area ────────────────────────────────────────────────────────
st.title("🔬 AquaScope — 水下生物智能识别")
st.caption("上传图片 + 提问 → 图像分析 → 物种识别 → 卡片式结果展示")

# ── Input row ──
col_q, col_img = st.columns([2, 1])
with col_q:
    query = st.text_area(
        "💬 你的问题",
        value="这是什么水下生物？它有什么特征？",
        height=80,
        placeholder="例如：这是什么生物？有什么视觉特征？",
    )
with col_img:
    image = st.file_uploader(
        "🖼️ 上传水下图片（可选）",
        type=["jpg", "jpeg", "png", "webp"],
    )

run_clicked = st.button("🚀 开始识别", type="primary", use_container_width=True)

if run_clicked:
    image_path = None
    if image:
        suffix = Path(image.name).suffix or ".jpg"
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp.write(image.getvalue())
        temp.close()
        image_path = temp.name

    with st.spinner("🔍 正在分析图像质量、增强图像、识别物种、检索知识库…"):
        state = AquaBioAgent(ROOT).run(query, image_path)

    # ── Warnings ──
    if state.get("warnings"):
        for warning in state["warnings"]:
            st.warning(warning)

    # ── Answer ──
    st.subheader("💬 回答")
    st.markdown(state.get("answer", "*（暂无回答）*"))

    st.divider()

    # ── Main columns: evidence + species card ──
    left, right = st.columns([3, 2])

    with left:
        # ── Retrieval evidence ──
        st.subheader("📋 检索证据")
        if state.get("retrieval"):
            for idx, item in enumerate(state["retrieval"]):
                label = (
                    item.get("source")
                    or item.get("dataset_name")
                    or item.get("class_name")
                    or f"证据 #{idx + 1}"
                )
                if item.get("page"):
                    label = f"{label} — p.{item['page']}"
                score = item.get("score", 0)
                with st.expander(f"{label}  |  匹配度: {score:.3f}"):
                    st.write(item.get("content", "*无内容*"))
        else:
            st.info("未检索到相关证据。")

        # ── Tool trace ──
        with st.expander("🔧 工具调用轨迹"):
            if state.get("tool_trace"):
                for step, tool in enumerate(state["tool_trace"], 1):
                    st.caption(f"{step}. {tool}")
            if state.get("image_quality"):
                st.json(state["image_quality"])

    with right:
        # ── Species card(s) ──
        st.subheader("🃏 物种识别卡片")
        matched = state.get("matched_species", [])
        if matched:
            for card in matched:
                render_species_card(card)
                st.write("")  # spacing
        else:
            st.markdown(
                '<div class="no-species-hint">'
                "📭 未匹配到物种卡片<br>"
                "<small>试试上传水下生物图片，或调整提问方式</small>"
                "</div>",
                unsafe_allow_html=True,
            )

        # ── Enhanced image candidates ──
        if state.get("enhancements"):
            st.subheader("🖼️ 增强候选图")
            tabs = st.tabs(
                [item["method"].replace("_", " ").title() for item in state["enhancements"]]
            )
            for tab, item in zip(tabs, state["enhancements"]):
                with tab:
                    st.image(item["path"])
                    st.caption(
                        f"亮度: {item['quality'].get('brightness', '?')} | "
                        f"对比度: {item['quality'].get('contrast', '?')}"
                    )

        # ── VLM analysis detail ──
        if state.get("vision_analysis"):
            with st.expander("🤖 VLM 分析详情"):
                st.json(state["vision_analysis"])
