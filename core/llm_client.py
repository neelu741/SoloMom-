"""
core/llm_client.py
LLM API client wrapper for SoloMom Advisor.
Supports Gemini API and OpenAI API with graceful error handling.
"""

import os
from typing import Optional


def complete(system_prompt: str, user_prompt: str) -> str:
    """
    Sends system and user prompt to the configured LLM API.
    Raises Exception if no key or API failure occurs, triggering fallback.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_prompt,
            )
            response = model.generate_content(user_prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            # Try next client or raise for fallback
            pass

    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception:
            pass

    raise RuntimeError("No configured LLM API key available or call failed.")
