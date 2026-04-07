"""
CodeAutopsy AI Package
======================
Unified AI gateway with provider fallback (Groq → Ollama).
Import `get_ai_gateway()` to access the singleton AIGateway instance.
"""

from app.services.ai.gateway import AIGateway, get_ai_gateway

__all__ = ["AIGateway", "get_ai_gateway"]
