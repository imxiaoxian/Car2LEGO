"""API key masking utilities.

Migrated from `app/integrations/provider.py` to keep the security helper
available after the legacy provider layer is removed (Phase 5).

All API keys (sk-*, ark-*, sk-ant-*) are masked in error messages and
log output so that real keys never leak through exception traces.
"""

import re


def mask_api_key(text: str) -> str:
    """Mask API keys in error messages to prevent accidental exposure.

    Masks patterns like:
      - sk-... (OpenAI/DeepSeek): keep first 4 and last 4 of the secret segment
      - ark-... (Doubao/Volcano Engine): keep first 4 and last 10 chars
      - sk-ant-... (Anthropic): keep first 4 and last 4 of the secret segment

    Returns the sanitized string.
    """
    # Mask sk-* keys (OpenAI, DeepSeek): keep first 7 and last 4 chars
    text = re.sub(r'(sk-[a-zA-Z0-9]{4})[a-zA-Z0-9]+([a-zA-Z0-9]{4})', r'\1****\2', text)
    # Mask ark-* keys (Doubao): keep first 15 and last 5 chars
    text = re.sub(r'(ark-[a-f0-9]{4}-)[a-f0-9\-]+([a-f0-9\-]{10})', r'\1****\2', text)
    # Mask sk-ant-* keys (Anthropic): keep prefix and last 4
    text = re.sub(r'(sk-ant-[a-zA-Z0-9]{4})[a-zA-Z0-9]+([a-zA-Z0-9]{4})', r'\1****\2', text)
    return text
