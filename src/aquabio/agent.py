from __future__ import annotations

import json
from pathlib import Path

from .config import Settings
from .image_tools import analyze_quality, create_enhancements
from .openrouter import OpenRouterClient
from .retriever import HybridRetriever
from .semantic_retriever import SemanticRetriever


class AquaBioAgent:
    def __init__(
        self,
        project_root: str | Path = ".",
        offline: bool = False,
        use_semantic: bool = False,
    ):
        self.root = Path(project_root)
        self.settings = Settings.from_env()
        self.client = OpenRouterClient(self.settings, offline=offline)
        if use_semantic:
            self.retriever = SemanticRetriever(
                self.root / "data/knowledge",
                self.root / "data/index",
                self.root / "data/vector_db",
            )
        else:
            self.retriever = HybridRetriever(
                self.root / "data/knowledge",
                self.root / "data/index",
                self.root / "data/vector_db",
            )
        self._species_cards: list[dict] | None = None
        self._species_images: dict[str, list[str]] | None = None

    def _load_species_cards(self) -> list[dict]:
        if self._species_cards is not None:
            return self._species_cards
        cards_path = self.root / "data" / "knowledge" / "species_cards.jsonl"
        cards = []
        if cards_path.exists():
            for line in cards_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    cards.append(json.loads(line))
        self._species_cards = cards
        return cards

    def _load_image_mapping(self) -> dict[str, list[str]]:
        if self._species_images is not None:
            return self._species_images
        mapping_path = self.root / "data" / "species_images.json"
        if mapping_path.exists():
            self._species_images = json.loads(mapping_path.read_text(encoding="utf-8"))
        else:
            self._species_images = {}
        return self._species_images

    def _match_species_cards(self, state: dict) -> list[dict]:
        """Match VLM candidates and retrieval results to species cards.

        Only returns cards with meaningful match confidence: either the
        card's chinese_name appears directly in the candidates, or it
        matches at least 2 keywords. Caps result to top 3 cards.
        """
        matched: list[dict] = []
        cards = self._load_species_cards()
        image_map = self._load_image_mapping()
        if not cards:
            return matched

        candidates: set[str] = set()

        # VLM candidates are high-confidence — give them more weight
        vlm_names: set[str] = set()
        if state.get("vision_analysis"):
            for name in state["vision_analysis"].get("possible_species", []):
                name_lower = name.lower().strip()
                candidates.add(name_lower)
                vlm_names.add(name_lower)

        # Retrieval results — only from top-scoring items, weighted by score
        retrieval_scores: dict[str, float] = {}
        for item in state.get("retrieval", []):
            item_score = float(item.get("score", 0))
            for field in ("class_name", "chinese_name"):
                value = item.get(field, "")
                if not value:
                    continue
                key = str(value).lower().strip()
                candidates.add(key)
                retrieval_scores[key] = max(retrieval_scores.get(key, 0), item_score)

        # Match each card and compute a confidence score
        scored: list[tuple[int, dict]] = []
        seen_ids: set[str] = set()
        for card in cards:
            if card.get("id", "") in seen_ids:
                continue
            card_names = {
                card.get("class_name", "").lower(),
                card.get("chinese_name", "").lower(),
                card.get("scientific_name", "").lower(),
                *[kw.lower() for kw in card.get("keywords", [])],
            }
            card_names.discard("")
            hits = candidates & card_names
            if not hits:
                continue

            # Confidence score: VLM hits weighted heavily,
            # retrieval hits weighted by their search score
            score = 0.0
            for h in hits:
                if h in vlm_names:
                    score += 5.0
                else:
                    score += retrieval_scores.get(h, 0.5)

            # Bonus for chinese_name match (strongest signal)
            if card.get("chinese_name", "").lower() in candidates:
                score += 2.0

            if score < 2.0:
                continue  # too weak

            seen_ids.add(card.get("id", ""))
            card_copy = dict(card)
            class_name = card.get("class_name", "")
            images = image_map.get(class_name, [])
            card_copy["image_path"] = str(
                self.root / images[0]
            ) if images else None
            card_copy["match_score"] = round(score, 1)
            scored.append((score, card_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [card for _, card in scored[:3]]

    def _offline_answer(self, query: str, contexts: list[dict], warning: str) -> str:
        excerpts = []
        for item in contexts[:4]:
            source = item.get("source") or item.get("dataset_name") or item.get("class_name", "knowledge")
            page = f", p.{item['page']}" if item.get("page") else ""
            excerpts.append(f"- [{source}{page}] {item.get('content', '')[:260]}")
        body = "\n".join(excerpts) or "- 本地知识库尚无可用内容。"
        return f"{warning}\n\n与“{query}”最相关的本地证据：\n{body}"

    def run(self, query: str, image_path: str | None = None) -> dict:
        state = {
            "query": query,
            "route": "multimodal_qa" if image_path else "document_qa",
            "image_path": image_path,
            "retrieval": [],
            "image_quality": None,
            "enhancements": [],
            "vision_analysis": None,
            "matched_species": [],
            "tool_trace": [],
            "warnings": [],
            "answer": "",
        }
        retrieval_query = query
        if image_path:
            state["image_quality"] = analyze_quality(image_path)
            state["tool_trace"].append("image_quality")
            state["enhancements"] = create_enhancements(
                image_path, self.root / "data/outputs/enhanced"
            )
            state["tool_trace"].append("image_enhancement")
            if self.client.enabled:
                state["vision_analysis"] = self.client.analyze_image(
                    image_path,
                    "你是水下生物图像分析助手。给出候选类别、可见特征、退化问题和不确定性。"
                    "不要声称输出了可靠边界框，也不要把候选识别说成专用检测器结果。",
                )
                state["tool_trace"].append("openrouter_vision")
                retrieval_query += " " + " ".join(state["vision_analysis"]["possible_species"])
            else:
                state["warnings"].append("未配置 OpenRouter key，已跳过 VLM 图像理解。")

        state["retrieval"] = self.retriever.search(retrieval_query, top_k=7)
        state["tool_trace"].append("hybrid_retrieval")
        state["matched_species"] = self._match_species_cards(state)

        if not self.client.enabled:
            state["answer"] = self._offline_answer(
                query,
                state["retrieval"],
                "当前为离线模式，下面只展示检索证据，不生成模型结论。",
            )
            return state

        evidence = []
        for item in state["retrieval"]:
            source = item.get("source") or item.get("dataset_name") or item.get("class_name")
            evidence.append(
                {
                    "source": source,
                    "page": item.get("page"),
                    "source_type": item.get("source_type"),
                    "content": item.get("content"),
                }
            )
        prompt = {
            "user_query": query,
            "image_quality": state["image_quality"],
            "vision_analysis": state["vision_analysis"],
            "retrieved_evidence": evidence,
            "rules": [
                "只根据工具事实和检索证据回答。",
                "VLM 结果称为候选识别，不称为目标检测结果。",
                "不能因视觉质量提高就断言检测性能提高。",
                "引用 PDF 时写出文件名和页码。",
                "信息不足时明确说明不确定性。",
            ],
        }
        state["answer"] = self.client.chat(
            [
                {
                    "role": "system",
                    "content": "你是 AquaBio-AgentRAG，请用简洁中文回答水下生物、图像增强和 PDF 问答问题。",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ]
        )
        state["tool_trace"].append("answer_generation")
        if state["retrieval"] and not any(
            str(item.get("source", "")) in state["answer"] for item in state["retrieval"] if item.get("source")
        ):
            state["warnings"].append("生成答案可能未显式标注全部检索来源，请结合证据面板检查。")
        return state
