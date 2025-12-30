"""
Project detection wizard step.

Detects project type, language, frameworks, and other characteristics
using the detection system and allows user confirmation/override.
"""

from rich import box
from rich.console import Console
from rich.table import Table

from fastband.core.detection import (
    Framework,
    Language,
    ProjectInfo,
    ProjectType,
    detect_project,
)
from fastband.wizard.base import StepResult, WizardContext, WizardStep

# Display name mappings for better user experience
LANGUAGE_DISPLAY_NAMES: dict[Language, str] = {
    Language.PYTHON: "Python",
    Language.JAVASCRIPT: "JavaScript",
    Language.TYPESCRIPT: "TypeScript",
    Language.RUST: "Rust",
    Language.GO: "Go",
    Language.JAVA: "Java",
    Language.KOTLIN: "Kotlin",
    Language.SWIFT: "Swift",
    Language.CSHARP: "C#",
    Language.CPP: "C++",
    Language.C: "C",
    Language.RUBY: "Ruby",
    Language.PHP: "PHP",
    Language.DART: "Dart",
    Language.UNKNOWN: "Unknown",
}

PROJECT_TYPE_DISPLAY_NAMES: dict[ProjectType, str] = {
    ProjectType.WEB_APP: "Web Application",
    ProjectType.API_SERVICE: "API Service",
    ProjectType.MOBILE_IOS: "iOS Mobile App",
    ProjectType.MOBILE_ANDROID: "Android Mobile App",
    ProjectType.MOBILE_CROSS: "Cross-Platform Mobile App",
    ProjectType.DESKTOP_ELECTRON: "Desktop App (Electron)",
    ProjectType.DESKTOP_NATIVE: "Desktop App (Native)",
    ProjectType.CLI_TOOL: "CLI Tool",
    ProjectType.LIBRARY: "Library/Package",
    ProjectType.MONOREPO: "Monorepo",
    ProjectType.UNKNOWN: "Unknown",
}

FRAMEWORK_DISPLAY_NAMES: dict[Framework, str] = {
    Framework.FLASK: "Flask",
    Framework.DJANGO: "Django",
    Framework.FASTAPI: "FastAPI",
    Framework.PYTEST: "pytest",
    Framework.REACT: "React",
    Framework.VUE: "Vue.js",
    Framework.ANGULAR: "Angular",
    Framework.SVELTE: "Svelte",
    Framework.NEXTJS: "Next.js",
    Framework.NUXT: "Nuxt.js",
    Framework.EXPRESS: "Express",
    Framework.NESTJS: "NestJS",
    Framework.REACT_NATIVE: "React Native",
    Framework.FLUTTER: "Flutter",
    Framework.SWIFTUI: "SwiftUI",
    Framework.JETPACK_COMPOSE: "Jetpack Compose",
    Framework.ELECTRON: "Electron",
    Framework.TAURI: "Tauri",
    Framework.QT: "Qt",
    Framework.SPRING: "Spring",
    Framework.RAILS: "Ruby on Rails",
    Framework.LARAVEL: "Laravel",
}


class ProjectDetectionStep(WizardStep):
    """
    Wizard step for detecting and confirming project information.

    This step:
    1. Automatically detects project type, language, and frameworks
    2. Displays detection results to the user
    3. In interactive mode, allows user to override/confirm detection
    4. Saves project info to the wizard context
    """

    def __init__(self, console: Console | None = None):
        super().__init__(console)
        self._detected_info: ProjectInfo | None = None

    @property
    def name(self) -> str:
        return "project"

    @property
    def title(self) -> str:
        return "Project Detection"

    @property
    def description(self) -> str:
        return "Analyze your project to detect language, type, and frameworks"

    @property
    def required(self) -> bool:
        return True

    async def execute(self, context: WizardContext) -> StepResult:
        """
        Execute project detection step.

        Args:
            context: The wizard context containing project path and configuration

        Returns:
            StepResult with success status and detected project info
        """
        # Detect project information
        self.show_info("Analyzing project structure...")

        try:
            project_info = detect_project(context.project_path)
            self._detected_info = project_info
        except Exception as e:
            self.show_error(f"Failed to detect project: {e}")
            return StepResult(
                success=False,
                message=f"Project detection failed: {e}",
            )

        # Display detection results
        self._display_detection_results(project_info)

        # In interactive mode, allow user to confirm or override
        if context.interactive:
            confirmed = await self._confirm_or_override(context, project_info)
            if not confirmed:
                return StepResult(
                    success=False,
                    go_back=True,
                    message="User cancelled project detection",
                )
        else:
            # Non-interactive mode: accept detected values
            self.show_info("Non-interactive mode: accepting detected values")

        # Save to context
        context.project_info = project_info

        # Update config with project info
        if project_info.name:
            context.config.project_name = project_info.name
        context.config.project_type = project_info.primary_type.value
        context.config.primary_language = project_info.primary_language.value

        self.show_success("Project detection complete")

        return StepResult(
            success=True,
            data={
                "project_info": project_info.to_dict(),
                "language": project_info.primary_language.value,
                "type": project_info.primary_type.value,
                "frameworks": [f.framework.value for f in project_info.frameworks],
            },
            message="Project detected successfully",
        )

    def _display_detection_results(self, info: ProjectInfo) -> None:
        """Display the detection results in a formatted table."""
        self.console.print()

        # Main project info table
        table = Table(
            title="Detected Project Information",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Property", style="dim", width=20)
        table.add_column("Value", style="bold")
        table.add_column("Confidence", justify="right", width=12)

        # Project name and path
        if info.name:
            table.add_row("Name", info.name, "")
        if info.version:
            table.add_row("Version", info.version, "")

        # Primary language
        lang_display = LANGUAGE_DISPLAY_NAMES.get(
            info.primary_language, info.primary_language.value
        )
        lang_confidence = f"{info.language_confidence:.0%}"
        table.add_row("Language", lang_display, lang_confidence)

        # Project type
        type_display = PROJECT_TYPE_DISPLAY_NAMES.get(info.primary_type, info.primary_type.value)
        type_confidence = f"{info.type_confidence:.0%}"
        table.add_row("Type", type_display, type_confidence)

        self.console.print(table)

        # Frameworks table (if any detected)
        if info.frameworks:
            self.console.print()
            fw_table = Table(
                title="Detected Frameworks",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold green",
            )
            fw_table.add_column("Framework", style="cyan")
            fw_table.add_column("Version", style="dim")
            fw_table.add_column("Confidence", justify="right")

            for fw in info.frameworks[:5]:  # Limit to top 5
                fw_display = FRAMEWORK_DISPLAY_NAMES.get(fw.framework, fw.framework.value)
                version = fw.version or "-"
                confidence = f"{fw.confidence:.0%}"
                fw_table.add_row(fw_display, version, confidence)

            self.console.print(fw_table)

        # Package managers and build tools (inline)
        if info.package_managers:
            pm_list = ", ".join(pm.value for pm in info.package_managers)
            self.console.print(f"\n[dim]Package Managers:[/dim] {pm_list}")

        if info.build_tools:
            bt_list = ", ".join(bt.value for bt in info.build_tools)
            self.console.print(f"[dim]Build Tools:[/dim] {bt_list}")

        # Monorepo info
        if info.is_monorepo:
            self.console.print(
                f"\n[yellow]Monorepo detected[/yellow] with {len(info.subprojects)} subprojects"
            )
            if info.subprojects:
                for sp in info.subprojects[:5]:
                    self.console.print(f"  - {sp}")
                if len(info.subprojects) > 5:
                    self.console.print(f"  ... and {len(info.subprojects) - 5} more")

        self.console.print()

    async def _confirm_or_override(self, context: WizardContext, info: ProjectInfo) -> bool:
        """
        Allow user to confirm or override detection results.

        Returns:
            True if user confirmed, False if they want to go back
        """
        if self.confirm("Is this detection correct?", default=True):
            return True

        # Let user override
        self.console.print("\n[bold]Override Detection[/bold]")
        self.console.print("You can override the detected values.\n")

        # Override language
        language_options = [
            {"value": lang.value, "label": LANGUAGE_DISPLAY_NAMES.get(lang, lang.value)}
            for lang in Language
            if lang != Language.UNKNOWN
        ]

        override_language = self.confirm("Override primary language?", default=False)
        if override_language:
            selected = self.select_from_list(
                "Select primary language",
                language_options,
                allow_multiple=False,
            )
            if selected:
                # Update the info with the new language
                for lang in Language:
                    if lang.value == selected[0]:
                        info.primary_language = lang
                        info.language_confidence = 1.0  # User-confirmed
                        break

        # Override project type
        type_options = [
            {"value": pt.value, "label": PROJECT_TYPE_DISPLAY_NAMES.get(pt, pt.value)}
            for pt in ProjectType
            if pt != ProjectType.UNKNOWN
        ]

        override_type = self.confirm("Override project type?", default=False)
        if override_type:
            selected = self.select_from_list(
                "Select project type",
                type_options,
                allow_multiple=False,
            )
            if selected:
                for pt in ProjectType:
                    if pt.value == selected[0]:
                        info.primary_type = pt
                        info.type_confidence = 1.0  # User-confirmed
                        break

        # Show updated info
        self.console.print("\n[bold]Updated Detection:[/bold]")
        self._display_detection_results(info)

        return self.confirm("Proceed with these settings?", default=True)

    async def validate(self, context: WizardContext) -> bool:
        """Validate that project info was saved correctly."""
        if context.project_info is None:
            self.show_error("Project info not saved to context")
            return False
        return True
