"""
Пакет агентов для LangGraph
"""
from .base_agent import BaseAgent
from .dialogue_stages import DialogueStage
from .stage_detector_agent import StageDetectorAgent, StageDetection
from .admin_agent import AdminAgent
from .demo_agent import DemoAgent, create_demo_actor_agent_with_config
from .demo_setup_agent import DemoSetupAgent

__all__ = [
    "BaseAgent",
    "DialogueStage",
    "StageDetectorAgent",
    "StageDetection",
    "AdminAgent",
    "DemoAgent",
    "DemoSetupAgent",
    "create_demo_actor_agent_with_config",
]

