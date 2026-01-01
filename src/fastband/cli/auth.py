"""
Fastband CLI - Authentication Commands.

Browser-based OAuth flow for CLI registration and login.
Supports shared Supabase authentication with Hub.
"""

import asyncio
import http.server
import json
import os
import socketserver
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Optional keyring import for secure credential storage
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

console = Console()

# Create the auth CLI app
auth_app = typer.Typer(
    name="auth",
    help="Authentication commands for Fastband Hub",
    no_args_is_help=False,
)

# Service name for keyring storage
KEYRING_SERVICE = "fastband"
CREDENTIALS_FILE = Path.home() / ".fastband" / "credentials.json"

# OAuth callback port
OAUTH_CALLBACK_PORT = 8765


@dataclass
class Credentials:
    """Stored user credentials."""

    access_token: str
    refresh_token: str
    email: str
    user_id: str
    expires_at: str = ""

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "email": self.email,
            "user_id": self.user_id,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Credentials":
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            email=data.get("email", ""),
            user_id=data.get("user_id", ""),
            expires_at=data.get("expires_at", ""),
        )


def get_supabase_config() -> tuple[str, str]:
    """Get Supabase URL and key from environment or config."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    # Try to load from .env file
    if not url or not key:
        env_file = Path.cwd() / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("SUPABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip('"\'')
                elif line.startswith("SUPABASE_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"\'')

    return url, key


def save_credentials(creds: Credentials) -> None:
    """Save credentials securely."""
    if HAS_KEYRING:
        # Use system keyring for secure storage
        try:
            keyring.set_password(KEYRING_SERVICE, creds.email, json.dumps(creds.to_dict()))
            # Also store email separately for lookup
            keyring.set_password(KEYRING_SERVICE, "current_user", creds.email)
            return
        except Exception as e:
            console.print(f"[yellow]Warning: Could not use system keyring: {e}[/yellow]")

    # Fallback to file storage
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(creds.to_dict(), indent=2))
    # Set restrictive permissions
    CREDENTIALS_FILE.chmod(0o600)


def load_credentials() -> Credentials | None:
    """Load stored credentials."""
    if HAS_KEYRING:
        try:
            email = keyring.get_password(KEYRING_SERVICE, "current_user")
            if email:
                data = keyring.get_password(KEYRING_SERVICE, email)
                if data:
                    return Credentials.from_dict(json.loads(data))
        except Exception:
            pass

    # Fallback to file storage
    if CREDENTIALS_FILE.exists():
        try:
            data = json.loads(CREDENTIALS_FILE.read_text())
            return Credentials.from_dict(data)
        except Exception:
            pass

    return None


def clear_credentials() -> None:
    """Clear stored credentials."""
    if HAS_KEYRING:
        try:
            email = keyring.get_password(KEYRING_SERVICE, "current_user")
            if email:
                keyring.delete_password(KEYRING_SERVICE, email)
                keyring.delete_password(KEYRING_SERVICE, "current_user")
        except Exception:
            pass

    # Also clear file
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress HTTP logs."""
        pass

    def do_GET(self) -> None:
        """Handle OAuth callback GET request."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/auth/callback":
            # Extract tokens from callback
            access_token = params.get("access_token", [""])[0]
            refresh_token = params.get("refresh_token", [""])[0]

            # Sometimes Supabase sends as fragment, handle that case
            if not access_token and "#" in self.path:
                fragment = self.path.split("#", 1)[1]
                fragment_params = urllib.parse.parse_qs(fragment)
                access_token = fragment_params.get("access_token", [""])[0]
                refresh_token = fragment_params.get("refresh_token", [""])[0]

            if access_token:
                # Store tokens for the main thread to access
                self.server.oauth_result = {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "success": True,
                }

                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                success_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Fastband - Authentication Successful</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            background: #0a0a0f;
                            color: #e2e8f0;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                        }
                        .container {
                            text-align: center;
                            padding: 40px;
                            background: #1a1a2e;
                            border-radius: 16px;
                            border: 1px solid #00d4ff33;
                            box-shadow: 0 0 60px rgba(0, 212, 255, 0.1);
                        }
                        h1 { color: #00d4ff; margin-bottom: 16px; }
                        p { color: #94a3b8; }
                        .checkmark {
                            width: 80px;
                            height: 80px;
                            margin: 0 auto 24px;
                            background: linear-gradient(135deg, #00d4ff22, #ff006e22);
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-size: 40px;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="checkmark">✓</div>
                        <h1>Authentication Successful</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())
            else:
                # Handle error
                error = params.get("error", ["Unknown error"])[0]
                error_description = params.get("error_description", [""])[0]

                self.server.oauth_result = {
                    "success": False,
                    "error": error,
                    "error_description": error_description,
                }

                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Fastband - Authentication Failed</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            background: #0a0a0f;
                            color: #e2e8f0;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                        }}
                        .container {{
                            text-align: center;
                            padding: 40px;
                            background: #1a1a2e;
                            border-radius: 16px;
                            border: 1px solid #ff006e33;
                        }}
                        h1 {{ color: #ff006e; }}
                        p {{ color: #94a3b8; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Authentication Failed</h1>
                        <p>{error}: {error_description}</p>
                        <p>Please try again from the terminal.</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
        else:
            self.send_response(404)
            self.end_headers()


def run_oauth_server(port: int = OAUTH_CALLBACK_PORT) -> dict | None:
    """Run temporary OAuth callback server."""

    class ReusableServer(socketserver.TCPServer):
        allow_reuse_address = True
        oauth_result: dict | None = None

    try:
        with ReusableServer(("", port), OAuthCallbackHandler) as httpd:
            httpd.oauth_result = None
            httpd.timeout = 120  # 2 minute timeout

            # Handle one request
            httpd.handle_request()

            return httpd.oauth_result
    except OSError as e:
        console.print(f"[red]Error starting OAuth server: {e}[/red]")
        return None


def get_user_info(access_token: str, supabase_url: str, supabase_key: str) -> dict | None:
    """Fetch user info from Supabase."""
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": supabase_key,
            }
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch user info: {e}[/yellow]")
        return None


@auth_app.command("register")
def register():
    """
    Register a new Fastband account.

    Opens your browser for OAuth authentication with Google.
    """
    supabase_url, supabase_key = get_supabase_config()

    if not supabase_url or not supabase_key:
        console.print(Panel(
            "[red]Supabase configuration not found.[/red]\n\n"
            "Please set SUPABASE_URL and SUPABASE_KEY in your environment or .env file.",
            title="Configuration Error",
            border_style="red",
        ))
        raise typer.Exit(1)

    # Check if already logged in
    existing = load_credentials()
    if existing:
        console.print(f"[yellow]Already logged in as {existing.email}[/yellow]")
        if not typer.confirm("Do you want to register a new account?"):
            raise typer.Exit(0)

    console.print(Panel(
        "[bold cyan]Fastband Registration[/bold cyan]\n\n"
        "Opening your browser for authentication...\n"
        "Please sign in with Google to create your account.",
        border_style="cyan",
    ))

    # Build OAuth URL
    redirect_uri = f"http://localhost:{OAUTH_CALLBACK_PORT}/auth/callback"
    oauth_url = (
        f"{supabase_url}/auth/v1/authorize?"
        f"provider=google&"
        f"redirect_to={urllib.parse.quote(redirect_uri)}"
    )

    # Start OAuth server in background
    server_thread = threading.Thread(target=lambda: None)
    oauth_result = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Waiting for authentication...", total=None)

        # Open browser
        webbrowser.open(oauth_url)

        # Run OAuth server
        oauth_result = run_oauth_server()

        progress.update(task, description="Processing...")

    if not oauth_result or not oauth_result.get("success"):
        error = oauth_result.get("error", "Unknown error") if oauth_result else "Server error"
        console.print(f"[red]Authentication failed: {error}[/red]")
        raise typer.Exit(1)

    # Get user info
    user_info = get_user_info(
        oauth_result["access_token"],
        supabase_url,
        supabase_key,
    )

    if user_info:
        email = user_info.get("email", "unknown")
        user_id = user_info.get("id", "")
    else:
        email = "unknown"
        user_id = ""

    # Save credentials
    creds = Credentials(
        access_token=oauth_result["access_token"],
        refresh_token=oauth_result.get("refresh_token", ""),
        email=email,
        user_id=user_id,
    )
    save_credentials(creds)

    console.print(Panel(
        f"[green]✓ Successfully registered![/green]\n\n"
        f"Email: [cyan]{email}[/cyan]\n"
        f"User ID: [dim]{user_id[:8]}...[/dim]" if user_id else "",
        title="Welcome to Fastband",
        border_style="green",
    ))


@auth_app.command("login")
def login():
    """
    Log in to your Fastband account.

    Opens your browser for OAuth authentication.
    """
    # Same flow as register - Supabase handles both
    register()


@auth_app.command("logout")
def logout():
    """
    Log out of your Fastband account.

    Clears stored credentials.
    """
    creds = load_credentials()

    if not creds:
        console.print("[yellow]Not currently logged in.[/yellow]")
        raise typer.Exit(0)

    email = creds.email
    clear_credentials()

    console.print(f"[green]✓ Logged out successfully.[/green]")
    console.print(f"[dim]Cleared credentials for {email}[/dim]")


@auth_app.command("whoami")
def whoami():
    """
    Show current logged-in user.
    """
    creds = load_credentials()

    if not creds:
        console.print("[yellow]Not logged in.[/yellow]")
        console.print("[dim]Run 'fastband auth login' to authenticate.[/dim]")
        raise typer.Exit(0)

    console.print(Panel(
        f"[bold]Email:[/bold] [cyan]{creds.email}[/cyan]\n"
        f"[bold]User ID:[/bold] [dim]{creds.user_id}[/dim]\n"
        f"[bold]Storage:[/bold] {'System Keyring' if HAS_KEYRING else 'File (~/.fastband/credentials.json)'}",
        title="Current User",
        border_style="cyan",
    ))


@auth_app.command("status")
def status():
    """
    Check authentication status and connectivity.
    """
    supabase_url, supabase_key = get_supabase_config()
    creds = load_credentials()

    console.print("[bold]Authentication Status[/bold]\n")

    # Supabase config
    if supabase_url and supabase_key:
        console.print(f"[green]✓[/green] Supabase configured: {supabase_url[:40]}...")
    else:
        console.print("[red]✗[/red] Supabase not configured")

    # Keyring
    if HAS_KEYRING:
        console.print("[green]✓[/green] System keyring available")
    else:
        console.print("[yellow]![/yellow] Using file-based credential storage")

    # Credentials
    if creds:
        console.print(f"[green]✓[/green] Logged in as: {creds.email}")

        # Verify token is still valid
        if supabase_url and supabase_key:
            user_info = get_user_info(creds.access_token, supabase_url, supabase_key)
            if user_info:
                console.print("[green]✓[/green] Token is valid")
            else:
                console.print("[yellow]![/yellow] Token may be expired - run 'fastband auth login' to refresh")
    else:
        console.print("[yellow]![/yellow] Not logged in")


# Standalone commands (aliases)
@auth_app.callback(invoke_without_command=True)
def auth_callback(ctx: typer.Context):
    """Authentication commands for Fastband Hub."""
    if ctx.invoked_subcommand is None:
        # Show status by default
        status()
