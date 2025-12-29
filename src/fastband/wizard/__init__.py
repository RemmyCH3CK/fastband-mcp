"""
Fastband Setup Wizard - Interactive configuration wizard.

Provides a step-based wizard for initializing Fastband in a project,
guiding users through configuration options with a rich terminal UI.
"""

from fastband.wizard.base import (
    WizardStep,
    StepResult,
    SetupWizard,
    WizardContext,
)

from fastband.wizard.bible_generator import (
    AgentBibleGenerator,
    ProjectConfig,
    DatabaseRule,
    generate_agent_bible,
    create_agent_bible_for_project,
    EXAMPLE_CONFIGS,
)

__all__ = [
    # Wizard core
    "WizardStep",
    "StepResult",
    "SetupWizard",
    "WizardContext",
    # Agent Bible generator
    "AgentBibleGenerator",
    "ProjectConfig",
    "DatabaseRule",
    "generate_agent_bible",
    "create_agent_bible_for_project",
    "EXAMPLE_CONFIGS",
]
