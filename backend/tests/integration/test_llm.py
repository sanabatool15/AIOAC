"""Proves: the configured LLM_PROVIDER (openrouter or azure) accepts our key and answers a tiny prompt.

Costs a fraction of a cent (one short completion, no tools).
Run: RUN_REAL=1 pytest tests/real/test_llm.py -v -s
"""
from tests.integration.conftest import need


def test_one_tiny_completion(real_settings):
    if real_settings.llm_provider == "azure":
        need(real_settings.azure_openai_api_key, "AZURE_OPENAI_API_KEY")
        need(real_settings.azure_openai_base_url, "AZURE_OPENAI_BASE_URL")
        need(real_settings.azure_openai_model, "AZURE_OPENAI_MODEL")
    else:
        need(real_settings.openrouter_api_key, "OPENROUTER_API_KEY")
    from app.integrations.factory import get_llm

    r = get_llm().chat([{"role": "user", "content": "Reply with the single word: ok"}], [])
    print("llm said:", r.text, "usage:", r.usage)
    assert r.text and r.text.strip()
