"""
Wizard steps package.

Contains all the individual steps for the setup wizard.
"""

from typing import List

from fastband.wizard.base import WizardStep


def get_default_steps() -> List[WizardStep]:
    """
    Get the default wizard steps in order.

    Returns:
        List of wizard steps for standard setup flow
    """
    from fastband.wizard.steps.project import ProjectDetectionStep
    from fastband.wizard.steps.provider import ProviderSelectionStep
    from fastband.wizard.steps.tools import ToolSelectionStep
    from fastband.wizard.steps.github import GitHubIntegrationStep
    from fastband.wizard.steps.tickets import TicketManagerStep
    from fastband.wizard.steps.backup import BackupConfigurationStep

    return [
        ProjectDetectionStep(),
        ProviderSelectionStep(),
        ToolSelectionStep(),
        GitHubIntegrationStep(),
        TicketManagerStep(),
        BackupConfigurationStep(),
    ]


__all__ = [
    "get_default_steps",
]
