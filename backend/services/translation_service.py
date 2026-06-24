"""Translation service for friend chat messages.
Wraps googletrans translator with Gemini fallback and in‑memory caching.
Provides async detection and translation.
"""

import os
import logging
import asyncio
import threading
from typing import Optional, Tuple
from backend.services.translator import translate_text, detect_language

logger = logging.getLogger(__name__)

# Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_gemini_enabled = False
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_enabled = True
        logger.info("[TRANSLATION] Gemini API configured successfully for translation fallback.")
    except Exception as e:
        logger.error(f"[TRANSLATION] Failed to configure Gemini API: {e}")

# In‑memory caches with thread‑safe access
MAX_CACHE_SIZE = 1000
_translation_cache: dict = {}
_language_cache: dict = {}
_cache_lock = threading.Lock()

class TranslationService:
    """Service for translating friend chat messages with Gemini fallback and caching."""

    @staticmethod
    async def detect_and_translate(
        text: str,
        target_language: str,
        user_auto_translate: bool = True,
    ) -> Tuple[str, str, str]:
        """Detect source language and translate if needed.

        Returns (original_text, translated_text, source_language).
        
        IMPORTANT: Always translates to target language, even if detection 
        thinks source == target. Language detection can be unreliable.
        """
        if not text or not text.strip():
            return "", "", "en"
        if not user_auto_translate:
            return text, text, "en"

        try:
            loop = asyncio.get_event_loop()

            # Detect source language
            source_language = await loop.run_in_executor(None, detect_language, text)

            # ALWAYS translate to target language - don't skip based on detection
            # deep_translator handles same-language gracefully (returns unchanged)
            translated = await loop.run_in_executor(None, translate_text, text, target_language)

            logger.info(f"[TRANSLATION] '{text}' ({source_language}) → '{translated}' ({target_language})")
            return text, translated, source_language

        except Exception as e:
            logger.error(f"[TRANSLATION] Error: {e}")
            return text, text, "en"

    @staticmethod
    async def _detect_safe(text: str) -> str:
        """Safely detect language using cache, googletrans, then Gemini fallback."""
        txt = text.strip()
        if txt in _language_cache:
            return _language_cache[txt]
        # googletrans
        try:
            loop = asyncio.get_event_loop()
            detected = await loop.run_in_executor(None, detect_language, txt)
            if detected and len(detected) == 2:
                TranslationService._save_to_cache(_language_cache, txt, detected.lower())
                return detected.lower()
        except Exception as e:
            logger.warning(f"[TRANSLATION] googletrans detection failed: {e}")
        # Gemini fallback
        if _gemini_enabled:
            try:
                loop = asyncio.get_event_loop()
                detected = await loop.run_in_executor(None, TranslationService._gemini_detect, txt)
                if detected:
                    TranslationService._save_to_cache(_language_cache, txt, detected)
                    return detected
            except Exception as e:
                logger.error(f"[TRANSLATION] Gemini detection fallback failed: {e}")
        return "en"

    @staticmethod
    async def _translate_safe(text: str, target_language: str) -> str:
        """Safely translate text using cache, googletrans, then Gemini fallback."""
        txt = text.strip()
        cache_key = f"{txt}||{target_language}"
        if cache_key in _translation_cache:
            return _translation_cache[cache_key]
        # googletrans
        try:
            loop = asyncio.get_event_loop()
            translated = await loop.run_in_executor(None, translate_text, txt, target_language)
            if translated and translated.strip() != txt:
                TranslationService._save_to_cache(_translation_cache, cache_key, translated)
                return translated
        except Exception as e:
            logger.warning(f"[TRANSLATION] googletrans translation failed: {e}")
        # Gemini fallback
        if _gemini_enabled:
            try:
                loop = asyncio.get_event_loop()
                translated = await loop.run_in_executor(None, TranslationService._gemini_translate, txt, target_language)
                if translated and translated.strip() != txt:
                    TranslationService._save_to_cache(_translation_cache, cache_key, translated)
                    return translated
            except Exception as e:
                logger.error(f"[TRANSLATION] Gemini translation fallback failed: {e}")
        return txt

    @staticmethod
    def _gemini_detect(text: str) -> Optional[str]:
        """Synchronous Gemini call for language detection."""
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                f"Detect the language of the following text and return ONLY its 2-letter ISO 639-1 code "
                f"(e.g., 'en', 'es', 'fr', 'zh'). If unsure, return 'en'. "
                f"Do not include punctuation or explanations.\n\n"
                f"Text: {text}"
            )
            response = model.generate_content(prompt)
            lang = response.text.strip().lower()
            clean = "".join([c for c in lang if c.isalnum()])
            if len(clean) == 2:
                return clean
            return clean[:2] if len(clean) > 2 else "en"
        except Exception as e:
            logger.error(f"[TRANSLATION] Gemini detect helper failed: {e}")
            return None

    @staticmethod
    def _gemini_translate(text: str, target_language: str) -> Optional[str]:
        """Synchronous Gemini call for translation."""
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                f"Translate the following text into the language with code '{target_language}'. "
                f"Make it natural and preserve tone. "
                f"Respond ONLY with the translated text, no quotes or explanations.\n\n"
                f"Text: {text}"
            )
            response = model.generate_content(prompt)
            translation = response.text.strip()
            return translation if translation else None
        except Exception as e:
            logger.error(f"[TRANSLATION] Gemini translate helper failed: {e}")
            return None

    @staticmethod
    def _save_to_cache(cache: dict, key: str, value: str) -> None:
        """Thread‑safe cache insertion with size limit."""
        with _cache_lock:
            if len(cache) >= MAX_CACHE_SIZE:
                try:
                    first = next(iter(cache))
                    del cache[first]
                except Exception:
                    cache.clear()
            cache[key] = value

    @staticmethod
    async def translate_batch(texts: list, target_language: str) -> list:
        """Translate multiple texts in parallel."""
        tasks = [TranslationService.detect_and_translate(t, target_language, True) for t in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"[TRANSLATION] Batch translation error: {r}")
                out.append((None, None, None))
            else:
                out.append(r)
        return out

    @staticmethod
    def get_supported_languages() -> dict:
        """Return mapping of language codes to human‑readable names."""
        return {
            # Global languages
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "zh": "Chinese",
            "ja": "Japanese",
            "ar": "Arabic",
            "pt": "Portuguese",
            "ru": "Russian",
            "ko": "Korean",
            "it": "Italian",
            "nl": "Dutch",
            "tr": "Turkish",
            "pl": "Polish",
            # Indian languages
            "hi": "Hindi (हिन्दी)",
            "bn": "Bengali (বাংলা)",
            "ta": "Tamil (தமிழ்)",
            "te": "Telugu (తెలుగు)",
            "mr": "Marathi (मराठी)",
            "gu": "Gujarati (ગુજરાતી)",
            "kn": "Kannada (ಕನ್ನಡ)",
            "ml": "Malayalam (മലയാളം)",
            "pa": "Punjabi (ਪੰਜਾਬੀ)",
            "ur": "Urdu (اردو)",
            "or": "Odia (ଓଡ଼ିଆ)",
            "as": "Assamese (অসমীয়া)",
            "ne": "Nepali (नेपाली)",
            "sa": "Sanskrit (संस्कृतम्)",
            "sd": "Sindhi (سنڌي)",
        }
