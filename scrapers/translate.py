"""
Translation helper. Uses DeepL if DEEPL_API_KEY is set, otherwise falls back
to GoogleTranslator via deep-translator (free, no key required).
"""
import os

_deepl_client = None


def _get_deepl():
    global _deepl_client
    if _deepl_client is None:
        api_key = os.getenv("DEEPL_API_KEY", "")
        if api_key:
            import deepl
            server_url = None if os.getenv("DEEPL_API_TYPE", "free") == "pro" else "https://api-free.deepl.com"
            _deepl_client = deepl.Translator(api_key, server_url=server_url)
    return _deepl_client


def translate_to_english(text: str) -> str:
    """Translate French text to English. Returns original if translation fails."""
    if not text or not text.strip():
        return text

    # Try DeepL first
    client = _get_deepl()
    if client:
        try:
            result = client.translate_text(text, source_lang="FR", target_lang="EN-GB")
            return str(result)
        except Exception as e:
            print(f"DeepL translation failed: {e}")

    # Fallback: deep-translator (Google Translate, no key needed)
    try:
        from deep_translator import GoogleTranslator
        # Truncate to avoid hitting limits
        chunk = text[:4500]
        return GoogleTranslator(source="fr", target="en").translate(chunk)
    except Exception as e:
        print(f"Google Translate fallback failed: {e}")
        return text  # Return original if all else fails
