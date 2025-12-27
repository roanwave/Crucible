"""Crucible: A plug-and-play multi-LLM deliberation engine.

Public exports:
- Crucible: The sole public interface for running queries
- EngineConfig: Configuration for the engine
- ExecutorResult: Result type returned by Crucible.run()
"""

from crucible.config import EngineConfig
from crucible.engine import Crucible
from crucible.schemas import ExecutorResult

__all__ = ["Crucible", "EngineConfig", "ExecutorResult"]
