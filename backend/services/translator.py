# Translator helper using deep_translator (reliable alternative to googletrans).
# Provides language detection and translation with fallback to no-op behavior.

from typing import Optional

try:
    from deep_translator import GoogleTranslator, single_detection
    _translation_enabled = True
except Exception:
    _translation_enabled = False


def translate_text(text: str, dest_lang: str) -> str:
    """
    Translate text to destination language using deep_translator.

    Args:
        text: Text to translate
        dest_lang: Destination language code (e.g., 'en', 'hi', 'es', 'fr')

    Returns:
        Translated text, or original text on failure.
    """
    if not _translation_enabled or not text or not text.strip():
        return text

    dest_lang = dest_lang.lower().strip()
    
    try:
        translator = GoogleTranslator(source='auto', target=dest_lang)
        translated = translator.translate(text)
        return translated if translated else text
    except Exception:
        return text


def detect_language(text: str) -> str:
    """
    Detect the language of the input text using deep_translator.
    
    Returns:
        2-letter ISO 639-1 language code (e.g., 'en', 'es', 'hi')
    """
    if not _translation_enabled or not text or not text.strip():
        return "en"

    try:
        detected = single_detection(text)
        if detected and len(detected) == 2:
            return detected.lower()
        return "en"
    except Exception:
        return "en"
