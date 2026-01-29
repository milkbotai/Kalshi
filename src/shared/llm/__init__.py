"""LLM integration module for OpenRouter API access.

Provides advisory LLM capabilities for signal explanations and
anomaly classification. LLM outputs are for human understanding
only - they never affect trading decisions.
"""

from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig
from src.shared.llm.explanation import ExplanationGenerator, SignalExplanation
from src.shared.llm.anomaly import AnomalyClassifier, AnomalyClassification, AnomalyType

__all__ = [
    # OpenRouter client
    "OpenRouterClient",
    "OpenRouterConfig",
    # Explanation generator
    "ExplanationGenerator",
    "SignalExplanation",
    # Anomaly classifier
    "AnomalyClassifier",
    "AnomalyClassification",
    "AnomalyType",
]
