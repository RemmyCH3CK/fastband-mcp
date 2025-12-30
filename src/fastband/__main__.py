"""
Fastband MCP CLI entry point.

Usage:
    fastband [OPTIONS] COMMAND [ARGS]...
    fb [OPTIONS] COMMAND [ARGS]...  # Short alias
"""

from fastband.cli.main import cli


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
