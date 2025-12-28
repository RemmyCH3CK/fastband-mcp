"""Fastband core engine components."""

from fastband.core.config import FastbandConfig, get_config
from fastband.core.engine import FastbandEngine, create_engine, run_server
from fastband.core.detection import (
    ProjectDetector,
    ProjectInfo,
    DetectedFramework,
    DetectedLanguage,
    Language,
    ProjectType,
    Framework,
    PackageManager,
    BuildTool,
    detect_project,
)

__all__ = [
    # Config
    "FastbandConfig",
    "get_config",
    # Engine
    "FastbandEngine",
    "create_engine",
    "run_server",
    # Detection
    "ProjectDetector",
    "ProjectInfo",
    "DetectedFramework",
    "DetectedLanguage",
    "Language",
    "ProjectType",
    "Framework",
    "PackageManager",
    "BuildTool",
    "detect_project",
]
