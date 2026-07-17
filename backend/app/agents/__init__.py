"""LangGraph-based agent layer for Car2LEGO.

Replaces the legacy custom provider abstraction (`app.integrations`) with
LangChain/LangGraph idioms:

- `models.create_text_llm()` / `create_vision_llm()` — LangChain ChatModel factory
- `security.mask_api_key()` — API key sanitization for logs/errors
- `state.*State` — TypedDict state definitions for each graph
- `tools.*` — Real callable tools (parts catalog, brand colors, templates)
- `*_graph.py` — Compiled LangGraph StateGraphs (added in later phases)
"""
