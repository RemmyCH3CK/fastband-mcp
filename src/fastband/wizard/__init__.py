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

__all__ = [
    "WizardStep",
    "StepResult",
    "SetupWizard",
    "WizardContext",
]
