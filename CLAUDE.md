# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project identity

AquaScope is a multimodal underwater organism identification workbench. It combines OpenCV image analysis, VLM-based species recognition, dual-mode retrieval (TF-IDF + MiniLM semantic), and a Streamlit UI with Pokémon-style species cards. The knowledge base covers 20 marine species across echinoderms, fish, mollusks, crustaceans, and cnidarians.

## Commands

All commands run from repo root. `PYTHONPATH` must include `src` (Windows semicolon separator):

```bash
# Install dependencies
pip install -r requirements.txt

# Build/rebuild the vector database (required after changing knowledge JSONL files)
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli build-vector-db

# Check vector DB metadata
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli vector-db-info

# Run tests
python -m pytest tests/test_core.py -v

# CLI — text question, offline (no API key needed)
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "海星有什么特征" --offline

# CLI — text question, online (requires QWEN_API_KEY in .env)
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "海星有什么特征"

# CLI — use semantic (MiniLM) retriever instead of TF-IDF
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "会喷墨汁的动物" --semantic

# CLI — image + question (requires QWEN_API_KEY)
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ask "这是什么生物" --image data/samples/starfish_01.jpg

# Launch Streamlit UI (MUST use run_app.py, not streamlit run app.py directly)
python run_app.py

# Parse PDFs into knowledge chunks (before rebuild)
PYTHONPATH="src;$PYTHONPATH" python -m aquabio.cli ingest "data/pdfs"
```

## Architecture

### Hard-coded pipeline

`AquaBioAgent.run()` executes a **fixed sequence** — there is no dynamic tool selection:

1. `analyze_quality(image)` → brightness, contrast, sharpness, color cast
2. `create_enhancements(image)` → 4 variants: white_balance, clahe, white_balance_clahe, gamma
3. `client.analyze_image(image)` → VLM structured output (possible_species, visible_features, degradation)
4. `retriever.search(query + species_names)` → hybrid TF-IDF + lexical overlap, top_k=7
5. `_match_species_cards(state)` → intersect VLM candidates with retrieval hits, resolve image paths
6. `client.chat(prompt)` → final Chinese answer from evidence

The state dict tracks: `query`, `route`, `image_path`, `retrieval`, `image_quality`, `enhancements`, `vision_analysis`, `matched_species`, `tool_trace`, `warnings`, `answer`.

### Species card matching

`_match_species_cards()` uses weighted scoring:
- VLM direct hit = +5, Chinese name match = +2, retrieval keyword hit = weighted by retrieval score
- Cards below threshold (score < 2.0) are discarded; max 3 cards returned
- Each matched card gets `image_path` (from `data/species_images.json`) and `match_score` injected

### Retrieval (dual-mode)

`HybridRetriever` (TF-IDF, default) uses:
- Vector score: TF-IDF char_wb ngrams(2,4) × query vector, weight 0.78
- Lexical score: CJK bigram + Latin token overlap, weight 0.22
- Query expansion via `DOMAIN_TRANSLATIONS` dict (Chinese→English domain terms)
- Persistent storage: records.jsonl + vectorizer.joblib + vectors.npz + manifest.json

`SemanticRetriever` (MiniLM, `--semantic` flag) uses:
- all-MiniLM-L6-v2 (~80 MB) for dense vector similarity
- Same record set as HybridRetriever; no rebuild needed
- Better for conceptual/descriptive queries; TF-IDF better for exact keyword matches

### Knowledge base

`data/knowledge/species_cards.jsonl` — 20 species, each with: `id`, `class_name`, `chinese_name`, `scientific_name`, `category`, `habitat`, `size`, `color_pattern`, `visual_features`, `fun_fact`, `content`, `keywords`.

`data/species_images.json` — maps `class_name` to list of local image paths. Only 9 of 20 species have images.

### LLM clients

`OpenRouterClient` in `src/aquabio/openrouter.py` supports `chat()`, `analyze_image()` (base64 image + prompt → structured JSON), and `select_tools()` (native function-calling, exists but not used in current pipeline).

Provider selection via `AQUABIO_LLM_PROVIDER` env var: `qwen` (primary), `openrouter`, `gemini`. Default provider is `qwen`; API key goes in `.env` as `QWEN_API_KEY=sk-xxx`.

### Starlette patch

`src/aquabio/_patch_starlette.py` injects `DEFAULT_EXCLUDED_CONTENT_TYPES` and `IdentityResponder` into `starlette.middleware.gzip`. Needed for streamlit ≤1.58 with starlette ≥0.35. The `run_app.py` launcher imports this patch **before** streamlit, so `streamlit run app.py` directly WILL crash — always use `python run_app.py`. The CLI does **not** need it (it doesn't import streamlit).

## Key constraints

- **Environment**: Python 3.11 on Windows. `PYTHONPATH="src;$PYTHONPATH"` is mandatory (semicolons, not colons).
- **Streamlit launch**: Must use `python run_app.py`, never `streamlit run app.py` (starlette patch must load first).
- **Offline mode**: When API key is unset, VLM and answer generation are skipped. The agent returns retrieval evidence.
- **Vector DB rebuild**: Required after ANY change to `data/knowledge/*.jsonl` or `data/index/*.jsonl`. The test suite creates temp directories and is isolated from the real DB.
- **No toxicity/edibility data**: The knowledge base intentionally contains only natural history facts (habitat, morphology, behavior). Do not add food safety claims.
