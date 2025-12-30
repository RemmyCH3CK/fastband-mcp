"""
Provider Selection Wizard Step.

Allows users to select and configure their preferred AI provider.
Detects available API keys and provides setup instructions.
"""

import os
from dataclasses import dataclass

from rich import box
from rich.table import Table

from fastband.wizard.base import StepResult, WizardContext, WizardStep


@dataclass
class ProviderInfo:
    """Information about an AI provider."""

    name: str
    display_name: str
    env_var: str
    default_model: str
    setup_url: str
    description: str


# Provider definitions with their configuration details
PROVIDERS: dict[str, ProviderInfo] = {
    "claude": ProviderInfo(
        name="claude",
        display_name="Claude (Anthropic)",
        env_var="ANTHROPIC_API_KEY",
        default_model="claude-sonnet-4-20250514",
        setup_url="https://console.anthropic.com/settings/keys",
        description="Advanced reasoning, extended thinking, excellent for code",
    ),
    "openai": ProviderInfo(
        name="openai",
        display_name="OpenAI (GPT-4)",
        env_var="OPENAI_API_KEY",
        default_model="gpt-4-turbo",
        setup_url="https://platform.openai.com/api-keys",
        description="Versatile, function calling, vision support",
    ),
    "gemini": ProviderInfo(
        name="gemini",
        display_name="Gemini (Google)",
        env_var="GOOGLE_API_KEY",
        default_model="gemini-pro",
        setup_url="https://aistudio.google.com/app/apikey",
        description="Long context, multimodal, fast inference",
    ),
    "ollama": ProviderInfo(
        name="ollama",
        display_name="Ollama (Local)",
        env_var="OLLAMA_HOST",  # Optional, defaults to localhost
        default_model="llama2",
        setup_url="https://ollama.ai/download",
        description="Local models, privacy-focused, no API key required",
    ),
}

# Provider priority for auto-selection (first available wins)
PROVIDER_PRIORITY = ["claude", "openai", "gemini", "ollama"]


class ProviderSelectionStep(WizardStep):
    """
    AI Provider selection wizard step.

    Detects available providers based on environment variables,
    allows user to select a default provider, and provides
    setup instructions for providers that aren't configured.
    """

    @property
    def name(self) -> str:
        return "provider"

    @property
    def title(self) -> str:
        return "AI Provider Selection"

    @property
    def description(self) -> str:
        return "Choose your default AI provider for code generation and analysis"

    @property
    def required(self) -> bool:
        return True

    def _check_provider_available(self, provider_name: str) -> bool:
        """
        Check if a provider has necessary credentials/configuration.

        For most providers, checks for API key environment variable.
        For Ollama, it's always considered available (local model).
        """
        if provider_name not in PROVIDERS:
            return False

        provider = PROVIDERS[provider_name]

        # Ollama doesn't require an API key
        if provider_name == "ollama":
            return True

        # Check for API key
        return bool(os.environ.get(provider.env_var))

    def _get_available_providers(self) -> list[str]:
        """Get list of providers with valid credentials."""
        return [name for name in PROVIDER_PRIORITY if self._check_provider_available(name)]

    def _get_all_providers(self) -> list[str]:
        """Get list of all registered providers."""
        return list(PROVIDERS.keys())

    def _display_provider_table(self) -> None:
        """Display a table of available providers with their status."""
        table = Table(
            title="Available AI Providers",
            box=box.ROUNDED,
            show_header=True,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Provider", style="cyan")
        table.add_column("Status", width=10)
        table.add_column("Description", style="dim")

        for i, name in enumerate(PROVIDER_PRIORITY, 1):
            provider = PROVIDERS[name]
            is_available = self._check_provider_available(name)

            if is_available:
                status = "[green]Ready[/green]"
            else:
                status = "[yellow]No Key[/yellow]"

            table.add_row(
                str(i),
                provider.display_name,
                status,
                provider.description,
            )

        self.console.print(table)

    def _show_setup_instructions(self, provider_name: str) -> None:
        """Show setup instructions for a provider."""
        if provider_name not in PROVIDERS:
            return

        provider = PROVIDERS[provider_name]

        self.console.print()
        self.console.print(f"[bold]Setup Instructions for {provider.display_name}:[/bold]")
        self.console.print()

        if provider_name == "ollama":
            self.console.print("  1. Download and install Ollama:")
            self.console.print(f"     [blue]{provider.setup_url}[/blue]")
            self.console.print()
            self.console.print("  2. Pull a model:")
            self.console.print("     [dim]ollama pull llama2[/dim]")
            self.console.print()
            self.console.print("  3. Start the Ollama server:")
            self.console.print("     [dim]ollama serve[/dim]")
        else:
            self.console.print("  1. Get your API key from:")
            self.console.print(f"     [blue]{provider.setup_url}[/blue]")
            self.console.print()
            self.console.print("  2. Set the environment variable:")
            self.console.print(f"     [dim]export {provider.env_var}='your-api-key'[/dim]")
            self.console.print()
            self.console.print("  3. Add to your shell profile for persistence:")
            self.console.print(
                f"     [dim]echo 'export {provider.env_var}=\"your-api-key\"' >> ~/.zshrc[/dim]"
            )

        self.console.print()

    async def execute(self, context: WizardContext) -> StepResult:
        """
        Execute the provider selection step.

        In interactive mode:
        - Shows available providers
        - Highlights which have API keys configured
        - Allows user to select default provider
        - Shows setup instructions for missing providers

        In non-interactive mode:
        - Selects first available provider (by priority)
        - Falls back to 'claude' if none available
        """
        available = self._get_available_providers()

        if context.interactive:
            return await self._execute_interactive(context, available)
        else:
            return self._execute_non_interactive(context, available)

    async def _execute_interactive(
        self,
        context: WizardContext,
        available: list[str],
    ) -> StepResult:
        """Execute in interactive mode."""
        # Show provider table
        self._display_provider_table()
        self.console.print()

        # Show summary of available providers
        if available:
            ready_names = ", ".join(PROVIDERS[p].display_name for p in available)
            self.show_success(f"Ready to use: {ready_names}")
        else:
            self.show_warning("No providers have API keys configured")
            self.show_info("Ollama is available for local use without an API key")
            self.console.print()

        # Let user select provider
        while True:
            choice = self.prompt(
                "Select default provider (number or name)",
                default="1" if available else "claude",
            )

            # Parse choice
            selected = self._parse_provider_choice(choice)
            if selected:
                break
            self.show_error(f"Invalid choice. Enter 1-{len(PROVIDER_PRIORITY)} or provider name")

        # Check if selected provider is available
        is_available = self._check_provider_available(selected)

        if not is_available:
            self.show_warning(f"{PROVIDERS[selected].display_name} is not configured yet")
            self._show_setup_instructions(selected)

            if not self.confirm("Continue with this provider anyway?", default=True):
                # Let them choose again
                return StepResult(
                    success=False,
                    go_back=False,
                    message="Please select a different provider",
                )

        # Save selection
        self._save_selection(context, selected)

        self.show_success(f"Selected {PROVIDERS[selected].display_name} as default provider")

        return StepResult(
            success=True,
            data={
                "selected_provider": selected,
                "provider_available": is_available,
                "available_providers": available,
            },
        )

    def _execute_non_interactive(
        self,
        context: WizardContext,
        available: list[str],
    ) -> StepResult:
        """Execute in non-interactive mode."""
        # Select first available provider by priority
        if available:
            selected = available[0]
        else:
            # Default to claude if nothing is available
            selected = "claude"

        self._save_selection(context, selected)

        is_available = self._check_provider_available(selected)

        return StepResult(
            success=True,
            data={
                "selected_provider": selected,
                "provider_available": is_available,
                "available_providers": available,
            },
        )

    def _parse_provider_choice(self, choice: str) -> str | None:
        """
        Parse user's provider choice.

        Accepts:
        - Number (1-4)
        - Provider name (claude, openai, gemini, ollama)
        - Partial match (clau -> claude)
        """
        choice = choice.strip().lower()

        # Empty input is invalid
        if not choice:
            return None

        # Try as number
        try:
            num = int(choice)
            if 1 <= num <= len(PROVIDER_PRIORITY):
                return PROVIDER_PRIORITY[num - 1]
        except ValueError:
            pass

        # Try exact match
        if choice in PROVIDERS:
            return choice

        # Try partial match
        for name in PROVIDERS:
            if name.startswith(choice):
                return name

        return None

    def _save_selection(self, context: WizardContext, provider: str) -> None:
        """Save the selected provider to context."""
        context.selected_provider = provider
        context.config.default_provider = provider

        # Also store provider info in metadata
        if provider in PROVIDERS:
            provider_info = PROVIDERS[provider]
            context.set(
                "provider_info",
                {
                    "name": provider_info.name,
                    "display_name": provider_info.display_name,
                    "default_model": provider_info.default_model,
                    "env_var": provider_info.env_var,
                },
            )
