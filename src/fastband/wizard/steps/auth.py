"""
Authentication wizard step.

Integrates CLI OAuth with the setup wizard for optional account linking.
"""

from rich.panel import Panel

from fastband.wizard.base import StepResult, WizardContext, WizardStep


class AuthStep(WizardStep):
    """
    Optional authentication step for Fastband Hub.

    Offers users the choice to register/login for cloud features
    or continue with local-only setup.
    """

    @property
    def name(self) -> str:
        return "Authentication"

    @property
    def title(self) -> str:
        return "Fastband Account (Optional)"

    @property
    def description(self) -> str:
        return "Connect to Fastband Hub for cloud sync and collaboration"

    @property
    def required(self) -> bool:
        return False

    async def execute(self, context: WizardContext) -> StepResult:
        """Execute the authentication step."""
        # Import auth utilities
        try:
            from fastband.cli.auth import (
                HAS_KEYRING,
                Credentials,
                get_supabase_config,
                load_credentials,
            )
        except ImportError:
            self.show_warning("Auth module not available - skipping")
            return StepResult(success=True, data={"auth_skipped": True})

        # Check if already logged in
        existing_creds = load_credentials()
        if existing_creds:
            self.console.print(
                Panel(
                    f"[green]✓ Already logged in[/green]\n\n"
                    f"Email: [cyan]{existing_creds.email}[/cyan]\n"
                    f"Storage: {'System Keyring' if HAS_KEYRING else 'File'}",
                    border_style="green",
                )
            )
            context.set("auth_email", existing_creds.email)
            context.set("auth_user_id", existing_creds.user_id)
            return StepResult(
                success=True,
                data={
                    "authenticated": True,
                    "email": existing_creds.email,
                    "user_id": existing_creds.user_id,
                },
            )

        # Check Supabase config
        supabase_url, supabase_key = get_supabase_config()
        if not supabase_url or not supabase_key:
            self.console.print(
                Panel(
                    "[yellow]Supabase not configured[/yellow]\n\n"
                    "To enable cloud features, set SUPABASE_URL and SUPABASE_KEY\n"
                    "in your environment or .env file.\n\n"
                    "[dim]Continuing with local-only setup...[/dim]",
                    border_style="yellow",
                )
            )
            return StepResult(success=True, data={"auth_skipped": True})

        # Offer authentication options
        self.console.print(
            Panel(
                "[bold cyan]Fastband Hub Account[/bold cyan]\n\n"
                "Connect your Fastband account to enable:\n"
                "  • Cloud sync for settings and configurations\n"
                "  • Team collaboration features\n"
                "  • Usage analytics and insights\n"
                "  • Premium AI features\n\n"
                "[dim]This step is optional - you can always connect later.[/dim]",
                border_style="cyan",
            )
        )

        choices = [
            {"value": "register", "label": "Create Account", "description": "Register with Google OAuth"},
            {"value": "login", "label": "Login", "description": "Sign in to existing account"},
            {"value": "skip", "label": "Skip", "description": "Continue without account"},
        ]

        selection = self.select_from_list("What would you like to do?", choices)
        choice = selection[0] if selection else "skip"

        if choice == "skip":
            self.show_info("Continuing without Fastband account")
            return StepResult(success=True, data={"auth_skipped": True})

        # Run OAuth flow
        try:
            from fastband.cli.auth import (
                OAUTH_CALLBACK_PORT,
                get_user_info,
                run_oauth_server,
                save_credentials,
            )
            import urllib.parse
            import webbrowser

            self.console.print("\n[cyan]Opening browser for authentication...[/cyan]")

            # Build OAuth URL
            redirect_uri = f"http://localhost:{OAUTH_CALLBACK_PORT}/auth/callback"
            oauth_url = (
                f"{supabase_url}/auth/v1/authorize?"
                f"provider=google&"
                f"redirect_to={urllib.parse.quote(redirect_uri)}"
            )

            # Open browser
            webbrowser.open(oauth_url)

            self.console.print("[dim]Waiting for authentication...[/dim]")

            # Run OAuth server
            oauth_result = run_oauth_server()

            if not oauth_result or not oauth_result.get("success"):
                error = oauth_result.get("error", "Unknown error") if oauth_result else "Server error"
                self.show_error(f"Authentication failed: {error}")
                if self.confirm("Continue without account?", default=True):
                    return StepResult(success=True, data={"auth_skipped": True})
                return StepResult(success=False, message="Authentication cancelled")

            # Get user info
            user_info = get_user_info(
                oauth_result["access_token"],
                supabase_url,
                supabase_key,
            )

            email = user_info.get("email", "unknown") if user_info else "unknown"
            user_id = user_info.get("id", "") if user_info else ""

            # Save credentials
            creds = Credentials(
                access_token=oauth_result["access_token"],
                refresh_token=oauth_result.get("refresh_token", ""),
                email=email,
                user_id=user_id,
            )
            save_credentials(creds)

            self.show_success(f"Authenticated as {email}")

            context.set("auth_email", email)
            context.set("auth_user_id", user_id)

            return StepResult(
                success=True,
                data={
                    "authenticated": True,
                    "email": email,
                    "user_id": user_id,
                },
            )

        except Exception as e:
            self.show_error(f"Authentication error: {e}")
            if self.confirm("Continue without account?", default=True):
                return StepResult(success=True, data={"auth_skipped": True})
            return StepResult(success=False, message=str(e))
