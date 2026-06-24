from __future__ import annotations

import sys
import os
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Patch starlette before importing streamlit
import aquabio._patch_starlette  # noqa: F401

import streamlit as st

from aquabio.agent import AquaBioAgent
from aquabio.config import delete_env_var, load_env, save_env_var
from aquabio.pdf_ingest import ingest_directory
from aquabio.vector_store import LocalVectorStore
from aquabio_mrag.conversation import ConversationStore

# ── Paths ────────────────────────────────────────────────────────────
SESSIONS_DIR = ROOT / "data" / "sessions"
UPLOADS_DIR = ROOT / "data" / "outputs" / "uploads"

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="AquaScope — 水下生物智能识别",
    page_icon="🔬",
    layout="wide",
)

# Populate os.environ from .env so proactive API-key checks work
load_env(ROOT / ".env")

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── species cards (kept from previous) ── */
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
/* ── session list items ── */
.session-list-item {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 0.5rem 0.7rem;
    margin: 4px 0;
    cursor: pointer;
    transition: background 0.15s;
}
.session-list-item:hover {
    background: #e3f2fd;
}
.session-list-item.active {
    background: #bbdefb;
    border-color: #1976d2;
}
.session-list-item .title {
    font-weight: 600;
    font-size: 0.9rem;
}
.session-list-item .meta {
    font-size: 0.75rem;
    color: #888;
}
</style>
""",
    unsafe_allow_html=True,
)


# ── Species card renderer (kept exactly as-is) ────────────────────
def render_species_card(card: dict):
    """Render a Pokemon-style species information card using Streamlit."""
    with st.container():
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
            st.image(card["image_path"], width='stretch')
        elif card.get("image_path"):
            st.image(card["image_path"], width='stretch')

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

        if card.get("color_pattern"):
            st.markdown(
                f"""<div class="section-title">🎨 体色特征</div>
<div class="section-text">{card['color_pattern']}</div>""",
                unsafe_allow_html=True,
            )

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

        if card.get("content"):
            st.markdown(
                f"""<div class="section-title">📖 简介</div>
<div class="section-text">{card['content'][:300]}</div>""",
                unsafe_allow_html=True,
            )

        if card.get("fun_fact"):
            st.markdown(
                f"""<div class="fun-fact-box">💡 <b>趣味知识：</b>{card['fun_fact']}</div>""",
                unsafe_allow_html=True,
            )

        st.markdown("</div></div>", unsafe_allow_html=True)


# ── Session helpers ───────────────────────────────────────────────

def init_session_state():
    """Initialise all session_state keys on first load."""
    defaults: dict = {
        "messages": [],
        "session_id": "",
        "store": ConversationStore(SESSIONS_DIR),
        "image_upload_key": 0,
        "chat_input_key": 0,
        "api_key_input": "",
        "_last_provider": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # API key input init
    if not st.session_state.api_key_input:
        current_provider = os.getenv("AQUABIO_LLM_PROVIDER", "qwen").lower()
        key_env_var = "QWEN_API_KEY" if current_provider == "qwen" else "OPENROUTER_API_KEY"
        st.session_state.api_key_input = os.getenv(key_env_var, "")

    # Auto-create or load a session
    if not st.session_state.session_id:
        sessions = st.session_state.store.list_sessions()
        if sessions:
            sid = sessions[0]["session_id"]
            session = st.session_state.store.load(sid)
            st.session_state.session_id = sid
            st.session_state.messages = session.get("messages", [])
        else:
            _create_new_session()


def _create_new_session():
    """Create a fresh session and set it as active."""
    new_id = str(uuid.uuid4())[:12]
    session = st.session_state.store.load(new_id)
    session["title"] = "新对话"
    session["messages"] = []
    st.session_state.store.save(session)
    st.session_state.session_id = new_id
    st.session_state.messages = []


def _build_summary(messages: list[dict]) -> dict:
    """Extract conversation summary from message history for agent context."""
    summary: dict[str, list | str] = {
        "last_species_ids": [],
        "last_species_names": [],
        "last_image_caption": "",
        "last_query": "",
        "last_image_path": "",
    }
    # Walk backwards to find the last assistant message with species data
    for msg in reversed(messages):
        if msg["role"] == "assistant" and msg.get("species_cards"):
            for card in msg["species_cards"]:
                summary["last_species_ids"].append(card.get("class_name", ""))
                summary["last_species_names"].append(card.get("chinese_name", ""))
            summary["last_query"] = msg.get("content", "")
            break
    # Find the last user message with an image
    for msg in reversed(messages):
        if msg["role"] == "user" and msg.get("image_path"):
            summary["last_image_path"] = msg["image_path"]
            break
    return summary


def _save_current_session():
    """Persist current chat to JSON file."""
    session = st.session_state.store.load(st.session_state.session_id)
    # Auto-title from first user message
    if session.get("title") in ("新对话", ""):
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                session["title"] = msg["content"][:36]
                break
    session["messages"] = st.session_state.messages[-200:]  # keep last 200
    # Update summary
    summary = _build_summary(st.session_state.messages)
    session["summary"] = {
        "last_species_ids": summary["last_species_ids"],
        "last_species_names": summary["last_species_names"],
        "last_image_caption": summary["last_image_caption"],
        "last_image_path": summary["last_image_path"],
        "last_query": summary["last_query"],
        "last_evidence_ids": [],
        "last_answer_summary": "",
    }
    st.session_state.store.save(session)


# ── Chat renderer ─────────────────────────────────────────────────

def render_chat():
    """Render all messages using st.chat_message()."""
    prev_species_ids: set[str] = set()  # track previous turn to avoid duplicate cards
    for msg in st.session_state.messages:
        role = msg["role"]
        with st.chat_message(role):
            if role == "user":
                st.markdown(msg["content"])
                if msg.get("image_path") and Path(msg["image_path"]).exists():
                    st.image(msg["image_path"], width=300)

            else:  # assistant
                st.markdown(msg.get("answer", "*无回答*"))

                if msg.get("warnings"):
                    for w in msg["warnings"]:
                        st.warning(w)

                # ── Species cards (skip if same species as previous turn) ──
                cards = msg.get("species_cards", [])
                current_ids = {c.get("class_name", "") for c in cards}
                if cards and current_ids != prev_species_ids:
                    if len(cards) == 1:
                        render_species_card(cards[0])
                    elif len(cards) > 1:
                        render_species_card(cards[0])
                        rest_names = "、".join(c.get("chinese_name", "?") for c in cards[1:])
                        with st.expander(f"🃏 还有 {len(cards)-1} 个匹配物种（{rest_names}）", expanded=False):
                            for card in cards[1:]:
                                render_species_card(card)
                                st.write("")
                if cards:
                    prev_species_ids = current_ids

                # ── YOLO detection (always visible) ──
                dets = msg.get("detections")
                if dets and dets.get("annotated_path") and Path(dets["annotated_path"]).exists():
                    st.caption("🎯 目标检测")
                    st.image(dets["annotated_path"], width='stretch')
                    for d in dets.get("detections", []):
                        st.caption(
                            f"🔍 {d['label']} — 置信度 {d['confidence']:.2f}"
                        )
                elif dets is not None and not dets.get("detections"):
                    st.caption("🎯 未检测到已知水下生物")

                # ── Expandable details (retrieval + enhancements + trace) ──
                has_details = any([
                    msg.get("enhancements"),
                    msg.get("retrieval"),
                    msg.get("tool_trace"),
                ])
                if has_details:
                    with st.expander("🔍 查看检索与分析详情", expanded=False):
                        # Enhancements
                        if msg.get("enhancements"):
                            st.caption("🖼️ 增强候选图")
                            tabs = st.tabs(
                                [e["method"].replace("_", " ").title()
                                 for e in msg["enhancements"]]
                            )
                            for tab, item in zip(tabs, msg["enhancements"]):
                                with tab:
                                    st.image(item["path"])
                                    st.caption(
                                        f"亮度: {item['quality'].get('brightness', '?')} | "
                                        f"对比度: {item['quality'].get('contrast', '?')}"
                                    )

                        # Retrieval evidence
                        retrieval = msg.get("retrieval", [])
                        if retrieval:
                            st.caption(f"📋 检索证据 ({len(retrieval)} 条)")
                            for item in retrieval:
                                label = (
                                    item.get("source")
                                    or item.get("dataset_name")
                                    or item.get("class_name")
                                    or "证据"
                                )
                                if item.get("page"):
                                    label = f"{label} — p.{item['page']}"
                                with st.expander(
                                    f"{label}  |  匹配度: {item.get('score', 0):.3f}"
                                ):
                                    st.write(item.get("content", "*无内容*"))

                        # Tool trace
                        if msg.get("tool_trace"):
                            st.caption("🔧 工具调用轨迹")
                            for step, tool in enumerate(msg["tool_trace"], 1):
                                st.caption(f"{step}. {tool}")


# ═══════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════

init_session_state()

with st.sidebar:
    st.title("🔬 AquaScope")
    st.caption("水下生物智能识别与问答系统")
    st.divider()

    # ── Section 1: Session Management ──
    st.subheader("💬 会话")

    if st.button("＋ 新建会话", width='stretch'):
        _create_new_session()
        st.rerun()

    sessions = st.session_state.store.list_sessions()
    st.caption(f"共 {len(sessions)} 个会话")

    # Render session list as clickable items
    with st.container(height=280, border=True):
        for s in sessions:
            sid = s["session_id"]
            is_active = sid == st.session_state.session_id
            # Load the session file to get the title
            sess_data = st.session_state.store.load(sid)
            title = sess_data.get("title", sid)
            turns = s.get("turns", 0)
            # Count actual messages if turns not tracked in summary
            msg_count = len(sess_data.get("messages", []))
            display_turns = msg_count // 2 if msg_count else turns
            species_names = s.get("last_species_names", [])

            cols = st.columns([0.78, 0.22], gap="small")
            with cols[0]:
                label = title if title else sid[:8]
                extra = f" — {'、'.join(species_names)}" if species_names else ""
                btn_label = f"{'📌 ' if is_active else ''}{label} ({display_turns}轮){extra}"
                if st.button(
                    btn_label,
                    key=f"load_{sid}",
                    width='stretch',
                    type="primary" if is_active else "secondary",
                ):
                    if sid != st.session_state.session_id:
                        session = st.session_state.store.load(sid)
                        st.session_state.session_id = sid
                        st.session_state.messages = session.get("messages", [])
                        st.session_state.image_upload_key += 1
                        st.rerun()
            with cols[1]:
                if st.button("🗑", key=f"del_{sid}", help="删除此会话"):
                    st.session_state.store.clear(sid)
                    if sid == st.session_state.session_id:
                        remaining = st.session_state.store.list_sessions()
                        if remaining:
                            new_sid = remaining[0]["session_id"]
                            new_session = st.session_state.store.load(new_sid)
                            st.session_state.session_id = new_sid
                            st.session_state.messages = new_session.get("messages", [])
                        else:
                            _create_new_session()
                    st.rerun()

    # Rename current session
    current_session = st.session_state.store.load(st.session_state.session_id)
    current_title = current_session.get("title", "新对话")
    new_title = st.text_input("会话标题", value=current_title, key="rename_input")
    col_rename, col_export = st.columns(2)
    with col_rename:
        if st.button("💾 保存标题", width='stretch'):
            session = st.session_state.store.load(st.session_state.session_id)
            session["title"] = new_title
            st.session_state.store.save(session)
            st.rerun()
    with col_export:
        if st.button("📋 导出", width='stretch', help="导出当前会话为 JSON"):
            session = st.session_state.store.load(st.session_state.session_id)
            st.download_button(
                "下载 JSON",
                data=__import__("json").dumps(session, ensure_ascii=False, indent=2),
                file_name=f"{current_title}.json",
                mime="application/json",
            )

    st.divider()

    # ── Section 2: Knowledge Base Management ──
    st.subheader("📚 知识库管理")
    pdfs = st.file_uploader(
        "上传 PDF 扩充知识库",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if st.button("📥 写入 PDF 知识库", disabled=not pdfs, width='stretch'):
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
- 支持多轮对话，系统会记住上一轮识别的物种
"""
        )

    st.divider()

    # ── Section 3: API Key Settings ──
    st.subheader("⚙️ API 设置")

    current_provider = os.getenv("AQUABIO_LLM_PROVIDER", "qwen").lower()
    provider = st.selectbox(
        "激活提供商",
        options=["qwen", "openrouter"],
        index=0 if current_provider != "openrouter" else 1,
        key="provider_select",
    )
    key_env_var = "QWEN_API_KEY" if provider == "qwen" else "OPENROUTER_API_KEY"

    if st.session_state.get("_last_provider", "") != provider:
        st.session_state._last_provider = provider
        st.session_state.api_key_input = os.getenv(key_env_var, "")

    api_key = st.text_input(
        key_env_var,
        value=st.session_state.api_key_input,
        type="password",
        placeholder="输入 API Key…",
        key="api_key_widget",
    )
    st.session_state.api_key_input = api_key

    col_save, col_clear = st.columns(2)
    with col_save:
        if st.button("💾 保存", width='stretch'):
            if api_key.strip():
                save_env_var(ROOT / ".env", key_env_var, api_key.strip())
                save_env_var(ROOT / ".env", "AQUABIO_LLM_PROVIDER", provider)
                st.session_state.api_key_input = api_key.strip()
                st.success(f"✅ {key_env_var} 已保存")
                st.rerun()
            else:
                st.warning("API Key 不能为空")

    with col_clear:
        if st.button("🗑️ 清除", width='stretch'):
            delete_env_var(ROOT / ".env", key_env_var)
            st.session_state.api_key_input = ""
            os.environ.pop(key_env_var, None)
            st.success(f"✅ {key_env_var} 已清除")
            st.rerun()

    # Proactive status indicator
    current_key = os.getenv(key_env_var, "")
    if not current_key or "replace_with" in current_key:
        st.warning(
            f"⚠️ 未配置 {key_env_var}。VLM 图像理解将被跳过，"
            "仅返回本地知识库检索结果。请在上方设置 API Key。"
        )
    else:
        masked = (
            current_key[:6] + "…" + current_key[-4:]
            if len(current_key) > 10
            else "****"
        )
        st.caption(f"✅ {key_env_var} 已配置（{masked}）")

    st.divider()
    st.caption("📁 知识库物种数：10 种")
    st.caption("🖼️ 样本图片：5 张")


# ═══════════════════════════════════════════════════════════════════
# Main Area — Chat Interface
# ═══════════════════════════════════════════════════════════════════

st.title("🔬 AquaScope — 水下生物智能识别")
st.caption("上传图片 + 提问 → 图像分析 → 物种识别 → 多轮对话记忆")

# Proactive hint when no valid API key is configured
_active_provider = os.getenv("AQUABIO_LLM_PROVIDER", "qwen").lower()
_active_key_var = "QWEN_API_KEY" if _active_provider == "qwen" else "OPENROUTER_API_KEY"
_active_key = os.getenv(_active_key_var, "")
if not _active_key or "replace_with" in _active_key:
    st.info(
        "💡 **提示：** 未检测到有效的 API Key。"
        "系统将以离线模式运行，仅使用本地知识库检索结果。"
        "在左侧边栏 ⚙️ API 设置 中配置 API Key 即可启用完整的 VLM 图像理解和模型回答功能。"
    )

# Render chat history
render_chat()

# Welcome message for empty sessions
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(
            "👋 你好！我是 **AquaScope**，水下生物智能识别助手。\n\n"
            "你可以：\n"
            "- 📸 上传一张水下生物图片，我会分析图像质量、检测目标、识别物种\n"
            "- 💬 直接输入问题，我会从知识库中检索答案\n"
            "- 🔄 多轮对话：我会记住上一轮识别的物种，你可以追问\"它有什么特征？\"\n\n"
            "在左侧边栏配置 API Key 后可使用完整的 VLM 图像理解功能。"
        )

# ── Input bar ──
col_img, col_input, col_send = st.columns([0.55, 8.5, 0.85], gap="small")

with col_img:
    # Show indicator if an image is staged for upload
    has_image = st.session_state.get("_has_staged_image", False)
    btn_label = "📎 *" if has_image else "📎"
    with st.popover(btn_label, use_container_width=False):
        uploaded_image = st.file_uploader(
            "上传水下图片",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"img_upload_{st.session_state.image_upload_key}",
        )
        if uploaded_image:
            st.caption(f"已选择: {uploaded_image.name}")
with col_input:
    user_input = st.text_input(
        "输入问题",
        key=f"chat_input_{st.session_state.get('chat_input_key', 0)}",
        label_visibility="collapsed",
        placeholder="输入问题，例如：这是什么生物？它有什么特征？",
    )
with col_send:
    send_clicked = st.button("发送", key="send_btn", width='stretch', type="primary")

# ── Process input (Enter in text_input OR send button) ──
prompt = None
if send_clicked and user_input.strip():
    prompt = user_input.strip()
elif user_input and user_input.strip() != st.session_state.get("_processed_prompt", ""):
    prompt = user_input.strip()

if prompt:
    # Guard: prevent double-submit before anything else
    st.session_state._processed_prompt = prompt
    st.session_state.image_upload_key += 1
    st.session_state.chat_input_key = st.session_state.get("chat_input_key", 0) + 1

    # Save uploaded image to persistent location
    image_path = None
    if uploaded_image:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = Path(uploaded_image.name).suffix or ".jpg"
        dest_name = f"{uuid.uuid4().hex[:10]}{suffix}"
        dest_path = UPLOADS_DIR / dest_name
        dest_path.write_bytes(uploaded_image.getvalue())
        image_path = str(dest_path)

    # Append user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "image_path": image_path,
    })

    # Build conversation summary from previous turns (before this message)
    prev_msgs = st.session_state.messages[:-1]  # exclude current
    conversation_summary = _build_summary(prev_msgs)

    # Run agent
    with st.spinner("🔍 正在分析图像质量、增强图像、识别物种、检索知识库…"):
        state = AquaBioAgent(ROOT).run(
            query=prompt,
            image_path=image_path,
            conversation_summary=(
                conversation_summary
                if conversation_summary.get("last_species_names")
                else None
            ),
        )

    # Build assistant message
    assistant_msg = {
        "role": "assistant",
        "content": prompt,  # store the triggering query
        "answer": state.get("answer", "*无回答*"),
        "species_cards": state.get("matched_species", []),
        "detections": state.get("detections"),
        "enhancements": state.get("enhancements", []),
        "retrieval": state.get("retrieval", []),
        "tool_trace": state.get("tool_trace", []),
        "warnings": state.get("warnings", []),
    }
    st.session_state.messages.append(assistant_msg)

    # Persist to JSON
    _save_current_session()
    st.rerun()
