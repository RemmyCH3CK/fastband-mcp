#!/usr/bin/env python3
"""
Dashboard Build Script - Builds React app and copies to package static directory.

This script:
1. Runs npm install (if node_modules missing)
2. Runs npm run build (Vite production build)
3. Copies dist/ to hub/static/ for packaging

Usage:
    python -m fastband.hub.web.build

    Or via CLI:
    fastband build-dashboard

The static/ directory is included in the Python package via
pyproject.toml [tool.hatch.build.targets.wheel.force-include].
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Paths
WEB_DIR = Path(__file__).parent
DIST_DIR = WEB_DIR / "dist"
STATIC_DIR = WEB_DIR.parent / "static"


def check_node_available() -> bool:
    """Check if Node.js and npm are available."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(f"  Node.js: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False


def check_npm_available() -> bool:
    """Check if npm is available."""
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(f"  npm: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False


def install_dependencies() -> bool:
    """Run npm install if node_modules doesn't exist."""
    node_modules = WEB_DIR / "node_modules"

    if node_modules.exists():
        print("  Dependencies already installed")
        return True

    print("  Installing npm dependencies...")

    try:
        result = subprocess.run(
            ["npm", "install"],
            cwd=WEB_DIR,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            print("  ERROR: npm install failed")
            print(result.stderr)
            return False

        print("  Dependencies installed successfully")
        return True

    except subprocess.TimeoutExpired:
        print("  ERROR: npm install timed out")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def build_dashboard() -> bool:
    """Run npm run build to create production build."""
    print("  Building React dashboard...")

    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=WEB_DIR,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            print("  ERROR: npm run build failed")
            print(result.stderr)
            return False

        print("  Build completed successfully")
        return True

    except subprocess.TimeoutExpired:
        print("  ERROR: npm run build timed out")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def copy_to_static() -> bool:
    """Copy dist/ to static/ for packaging."""
    if not DIST_DIR.exists():
        print(f"  ERROR: Build output not found: {DIST_DIR}")
        return False

    # Remove existing static directory
    if STATIC_DIR.exists():
        print(f"  Removing existing: {STATIC_DIR}")
        shutil.rmtree(STATIC_DIR)

    # Copy dist to static
    print(f"  Copying to: {STATIC_DIR}")
    shutil.copytree(DIST_DIR, STATIC_DIR)

    # Verify copy
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        print("  ERROR: index.html not found in static/")
        return False

    # Count files
    file_count = sum(1 for _ in STATIC_DIR.rglob("*") if _.is_file())
    total_size = sum(f.stat().st_size for f in STATIC_DIR.rglob("*") if f.is_file())
    size_kb = total_size / 1024

    print(f"  Copied {file_count} files ({size_kb:.1f} KB)")
    return True


def build():
    """Main build function."""
    print("\n" + "=" * 50)
    print("Fastband Dashboard Build")
    print("=" * 50)

    # Check prerequisites
    print("\n[1/4] Checking prerequisites...")
    if not check_node_available():
        print("  ERROR: Node.js not found. Please install Node.js 18+")
        return False

    if not check_npm_available():
        print("  ERROR: npm not found. Please install Node.js with npm")
        return False

    # Install dependencies
    print("\n[2/4] Installing dependencies...")
    if not install_dependencies():
        return False

    # Build
    print("\n[3/4] Building dashboard...")
    if not build_dashboard():
        return False

    # Copy to static
    print("\n[4/4] Copying to package...")
    if not copy_to_static():
        return False

    print("\n" + "=" * 50)
    print("Build complete!")
    print("=" * 50)
    print(f"\nStatic files: {STATIC_DIR}")
    print("\nTo run the dashboard:")
    print("  fastband serve --hub")
    print("  Open http://localhost:8080/")

    return True


def clean():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")

    # Remove dist
    if DIST_DIR.exists():
        print(f"  Removing: {DIST_DIR}")
        shutil.rmtree(DIST_DIR)

    # Remove static
    if STATIC_DIR.exists():
        print(f"  Removing: {STATIC_DIR}")
        shutil.rmtree(STATIC_DIR)

    # Optionally remove node_modules
    node_modules = WEB_DIR / "node_modules"
    if "--all" in sys.argv and node_modules.exists():
        print(f"  Removing: {node_modules}")
        shutil.rmtree(node_modules)

    print("Clean complete")


def main():
    """CLI entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
        sys.exit(0)

    success = build()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
