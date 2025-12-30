"""
Wizard steps package.

Contains all the individual steps for the setup wizard.
"""

from typing import List

from fastband.wizard.base import WizardStep


def get_default_steps() -> list[WizardStep]:
    """
    Get the default wizard steps in order.

    Returns:
        List of wizard steps for standard setup flow
    """
    from fastband.wizard.steps.backup import BackupConfigurationStep
    from fastband.wizard.steps.bible import AgentBibleStep
    from fastband.wizard.steps.github import GitHubIntegrationStep
    from fastband.wizard.steps.project import ProjectDetectionStep
    from fastband.wizard.steps.provider import ProviderSelectionStep
    from fastband.wizard.steps.tickets import TicketManagerStep
    from fastband.wizard.steps.tools import ToolSelectionStep

    return [
        ProjectDetectionStep(),
        ProviderSelectionStep(),
        ToolSelectionStep(),
        GitHubIntegrationStep(),
        TicketManagerStep(),
        BackupConfigurationStep(),
        AgentBibleStep(),  # Must be last - generates bible from all collected config
    ]


__all__ = [
    "get_default_steps",
]
