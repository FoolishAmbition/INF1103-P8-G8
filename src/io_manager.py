import questionary
from questionary import Choice

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.base_manager import BaseManager
from src.logic_manager import format_scores
from src.event_filter import EventFilter
from src.analytics_reporter import AnalyticsReporter


class IOManager(BaseManager):
    """Handles all terminal I/O: prompts, menus, validation and Rich output."""

    # Style lookups (immutable class-level config, not mutable globals)
    LEVEL_STYLES = {
        1: "bold green",
        2: "bold yellow",
        3: "bold red",
    }
    RECOMMENDATION_LEVELS = {"ATTEND": 1, "MAYBE": 2, "SKIP": 3}
    PRIORITY_LEVELS = {"High": 1, "Medium": 2, "Low": 3}
    DEFAULT_STYLE = "bold cyan"

    def __init__(self, name="IOManager", console=None):
        super().__init__(name)
        self.console = console or Console()

    def run(self) -> None:
        """Entry point required by BaseManager.

        IOManager is driven by the app's controller (which calls the
        collect_* / display_* methods), so its own "run" just starts a
        fresh terminal session by drawing the welcome screen.
        """
        self.refresh_screen()

    # ------------------------------------------------------------------
    # Validation / small helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _not_empty(text):
        if not text or not str(text).strip():
            return "This field cannot be empty."
        return True

    @staticmethod
    def _empty_profile():
        return {"field_of_study": "", "interests": []}

    @staticmethod
    def _copy_profile(profile):
        if hasattr(profile, "to_dict"):
            return profile.to_dict()
        if isinstance(profile, dict):
            return {
                "field_of_study": profile.get("field_of_study", ""),
                "interests": list(profile.get("interests", [])),
            }
        return {"field_of_study": "", "interests": []}

    def _ask_text(self, message, default=""):
        value = questionary.text(
            message,
            default=default,
            validate=self._not_empty,
        ).ask()

        # Input cancelled
        if value is None:
            return None
        return value.strip()

    # ------------------------------------------------------------------
    # Basic display
    # ------------------------------------------------------------------
    def display_welcome(self):
        self.console.print(
            Panel(
                "[bold cyan]EventWise[/bold cyan]\n"
                "AI-assisted student event decision system\n\n"
                "[dim]Tip: press Ctrl+C to go back without saving that step.[/dim]",
                expand=False,
            )
        )

    def display_error(self, message):
        self.console.print(f"\n[red]Error:[/red] {message}")

    def display_message(self, message):
        self.console.print(f"\n{message}")

    def refresh_screen(self, status=None, is_error=False):
        """Clear the terminal, redraw the header and show an optional status."""
        self.console.clear()
        self.display_welcome()

        if status:
            if is_error:
                self.display_error(status)
            else:
                self.display_message(status)

    # ------------------------------------------------------------------
    # Main menu
    # ------------------------------------------------------------------
    def get_main_menu_choice(self, main_menu_choice, status=None, is_error=False):
        self.refresh_screen(status, is_error)

        return questionary.select(
            "What would you like to do?",
            choices=main_menu_choice,
        ).ask()

    # ------------------------------------------------------------------
    # Profile collection
    # ------------------------------------------------------------------
    def collect_profile(self, profile):
        """Edit a profile. Returns the new profile if saved, else the original."""
        # Work on a copy so changes only apply when the user saves
        draft = self._copy_profile(profile)
        status = None
        is_error = False

        while True:
            field_label = draft["field_of_study"] or "(not set)"
            interests_label = (
                ", ".join(draft["interests"]) if draft["interests"] else "(not set)"
            )

            self.refresh_screen(status, is_error)
            status = None
            is_error = False

            choice = questionary.select(
                "Edit Profile",
                choices=[
                    f"Field of study: {field_label}",
                    f"Interests:      {interests_label}",
                    "Save",
                    "Cancel",
                ],
            ).ask()

            if choice is None or choice == "Cancel":
                return profile

            if choice.startswith("Field of study:"):
                self.refresh_screen()
                new_value = self._ask_text(
                    "What are you studying?",
                    default=draft["field_of_study"],
                )
                if new_value is not None:
                    draft["field_of_study"] = new_value

            elif choice.startswith("Interests:"):
                draft["interests"] = self._collect_interests(draft["interests"])

            elif choice == "Save":
                if not draft["field_of_study"].strip() or not draft["interests"]:
                    status = "Field of study and at least one interest are required."
                    is_error = True
                    continue
                return draft

    def _collect_interests(self, interests):
        """Add / remove interests. Cancelling returns the original list."""
        original = list(interests)
        draft = list(interests)
        status = None
        is_error = False

        while True:
            if draft:
                listed = f"Current interests: {', '.join(draft)}"
            else:
                listed = "Current interests: (none yet)"

            self.refresh_screen(status, is_error)
            self.display_message(listed)
            status = None
            is_error = False

            # Only offer removal when there is something to remove
            if draft:
                choices = ["Add interest", "Remove interest", "Done"]
            else:
                choices = ["Add interest", "Done"]

            choice = questionary.select("Edit interests", choices=choices).ask()

            if choice is None:
                return original

            if choice == "Done":
                return draft

            if choice == "Add interest":
                self.refresh_screen(listed)

                new_interest = self._ask_text("Add an interest:")
                if new_interest is None:
                    continue

                if new_interest.lower() in (item.lower() for item in draft):
                    status = "That interest is already in your list."
                    is_error = True
                    continue

                draft.append(new_interest)

            elif choice == "Remove interest":
                self.refresh_screen(listed)

                to_remove = questionary.select(
                    "Remove which interest?",
                    choices=draft,
                ).ask()

                if to_remove is None:
                    continue

                draft.remove(to_remove)

    # ------------------------------------------------------------------
    # Event collection
    # ------------------------------------------------------------------
    def collect_event_info(self, previous=None):
        """Collect (name, description, workload). Returns None if cancelled."""
        status = None
        is_error = False

        if previous:
            event_name, event_description, workload = previous
        else:
            event_name = event_description = workload = ""

        while True:
            self.refresh_screen(status, is_error)
            status = None
            is_error = False

            choice = questionary.select(
                "Analyse Events",
                choices=[
                    f"Event Name:        {event_name or '(not set)'}",
                    f"Event Description: {event_description or '(not set)'}",
                    f"Current workload:  {workload or '(not set)'}",
                    "Submit",
                    "Cancel",
                ],
            ).ask()

            if choice is None or choice == "Cancel":
                return None

            if choice.startswith("Event Name"):
                self.refresh_screen()
                new_value = self._ask_text(
                    "Paste Your Event Name here:",
                    default=event_name,
                )
                if new_value is not None:
                    event_name = new_value

            elif choice.startswith("Event Description"):
                self.refresh_screen()
                new_value = self._ask_text(
                    "Paste Your Event Description here:",
                    default=event_description,
                )
                if new_value is not None:
                    event_description = new_value

            elif choice.startswith("Current workload"):
                self.refresh_screen()
                new_value = questionary.select(
                    "What is your current workload",
                    choices=[
                        "Low",
                        "Medium",
                        "High",
                        Choice(title="Cancel", value=0),
                    ],
                ).ask()

                # 0 = Cancel choice, None = Ctrl+C; keep existing value in both cases
                if new_value not in (0, None):
                    workload = new_value

            elif choice == "Submit":
                if (
                    not event_name.strip()
                    or not event_description.strip()
                    or not workload
                ):
                    status = "All the fields are required."
                    is_error = True
                    continue

                return (event_name, event_description, workload)

    # ------------------------------------------------------------------
    # Event result display
    # ------------------------------------------------------------------
    def display_event_summary(
        self, event_summary, back_label="Return to the main menu"
    ):
        self.refresh_screen()

        # Support both EventRecord domain entities and dictionaries
        if hasattr(event_summary, "to_dict"):
            data = event_summary.to_dict()
        elif isinstance(event_summary, dict):
            data = event_summary
        else:
            data = {}

        priority = data.get("priority", "No priority")
        recommendation = data.get("recommendation", "No recommendation")
        rec_style = {
            "ATTEND": "bold green",
            "MAYBE": "bold yellow",
            "SKIP": "bold red",
        }.get(str(recommendation).upper(), self.DEFAULT_STYLE)

        # Event info
        self.console.rule("[bold cyan]Event[/bold cyan]", align="left", style="cyan")
        self.console.print(
            f'[bold]{data.get("event_name", "Unnamed event")}[/bold]\n'
            f'{data.get("event_description", "")}\n'
        )

        # Score breakdown
        scores = format_scores(
            data.get("career_relevance", 0),
            data.get("learning_value", 0),
            data.get("networking_value", 0),
        )
        self.console.rule(
            "[bold magenta]Score Breakdown[/bold magenta]",
            align="left",
            style="magenta",
        )
        self.console.print(
            f'Career Relevance: {scores["career_relevance"]}  •  '
            f'Learning Value: {scores["learning_value"]}  •  '
            f'Networking Value: {scores["networking_value"]}\n'
        )

        # Priority and recommendation
        self.console.rule(
            f"[{rec_style}]Priority: {priority} - Recommendation: {recommendation}[/{rec_style}]",
            align="left",
            style=rec_style,
        )
        self.console.print(f"{data.get('reason', 'No reason provided.')}\n")

        # AI reasoning
        self.console.rule(
            "[bold blue]AI Reasoning[/bold blue]", align="left", style="blue"
        )
        self.console.print(
            f"{data.get('ai_reasoning', 'No AI reasoning provided.')}\n"
        )

        questionary.select(back_label, choices=["Back"]).ask()

    def _style_for(self, value, levels):
        return self.LEVEL_STYLES.get(levels.get(value), self.DEFAULT_STYLE)

    def _build_event_table(self, events):
        table = Table(title="Analysed Events", show_lines=True)

        table.add_column("No.", style="cyan")
        table.add_column("Event", style="cyan", max_width=25)
        table.add_column("Priority", style="yellow")
        table.add_column("Recommendation", style="green")
        table.add_column("Reason", style="white", max_width=50)
        table.add_column("Career", style="white")
        table.add_column("Learning", style="white")
        table.add_column("Networking", style="white")

        for i, event in enumerate(events, start=1):
            if hasattr(event, "to_dict"):
                item = event.to_dict()
            elif isinstance(event, dict):
                item = event
            else:
                item = {}

            rec = str(item.get("recommendation", "Unknown"))
            rec_style = self._style_for(rec.upper(), self.RECOMMENDATION_LEVELS)

            priority = str(item.get("priority", "Unknown"))
            priority_style = self._style_for(priority, self.PRIORITY_LEVELS)

            table.add_row(
                str(i),
                str(item.get("event_name", "Unnamed event")),
                f"[{priority_style}]{priority}[/{priority_style}]",
                f"[{rec_style}]{rec}[/{rec_style}]",
                str(item.get("reason", "No reason provided")),
                str(item.get("career_relevance", 0)),
                str(item.get("learning_value", 0)),
                str(item.get("networking_value", 0)),
            )

        return table

    def display_event_list(self, events):
        if not events:
            self.refresh_screen()
            self.display_message("No analysed events found.")
            questionary.select("Return to the main menu", choices=["Close"]).ask()
            return

        while True:
            self.refresh_screen()
            self.console.print(self._build_event_table(events))

            choices = []
            for i, event in enumerate(events, start=1):
                name = getattr(event, "event_name", None) or (
                    event.get("event_name") if isinstance(event, dict) else "Unnamed event"
                )
                choices.append(Choice(title=f"{i}. {name}", value=event))
            choices.append("Back")

            selected = questionary.select(
                "Select an event to view", choices=choices
            ).ask()

            if selected is None or selected == "Back":
                return

            self.display_event_summary(selected, back_label="Return to event table")

    # ------------------------------------------------------------------
    # Event filter and search
    # ------------------------------------------------------------------
    def filter_events(self, events):
        """Interactive filter and keyword search menu for events."""
        if not events:
            self.refresh_screen()
            self.display_message("No analysed events found.")
            questionary.select("Return to the main menu", choices=["Close"]).ask()
            return

        filter_engine = EventFilter(events)

        while True:
            self.refresh_screen()
            choice = questionary.select(
                "Filter & Search Events",
                choices=[
                    "Filter by Recommendation (ATTEND / MAYBE / SKIP)",
                    "Search by Keyword",
                    "Filter by Minimum Score",
                    "Back",
                ],
            ).ask()

            if choice is None or choice == "Back":
                return

            filtered = None
            if choice.startswith("Filter by Recommendation"):
                self.refresh_screen()
                rec = questionary.select(
                    "Select Recommendation:",
                    choices=["ATTEND", "MAYBE", "SKIP", Choice(title="Cancel", value=0)],
                ).ask()
                if rec not in (0, None):
                    filtered = filter_engine.filter_by_recommendation(rec)

            elif choice.startswith("Search by Keyword"):
                self.refresh_screen()
                keyword = self._ask_text("Enter keyword to search (matches name, description, category):")
                if keyword is not None:
                    filtered = filter_engine.filter_by_keyword(keyword)

            elif choice.startswith("Filter by Minimum Score"):
                self.refresh_screen()
                score_choice = questionary.select(
                    "Select minimum score threshold:",
                    choices=[
                        "High Value (11+)",
                        "Medium Value (7+)",
                        "Custom Score",
                        Choice(title="Cancel", value=0),
                    ],
                ).ask()

                if score_choice == "High Value (11+)":
                    filtered = filter_engine.filter_by_min_score(11)
                elif score_choice == "Medium Value (7+)":
                    filtered = filter_engine.filter_by_min_score(7)
                elif score_choice == "Custom Score":
                    score_str = self._ask_text("Enter minimum total score (3-15):")
                    if score_str and score_str.isdigit():
                        filtered = filter_engine.filter_by_min_score(int(score_str))

            if filtered is not None:
                if not filtered:
                    self.refresh_screen()
                    self.display_message("No matching events found.")
                    questionary.select("Continue", choices=["Back"]).ask()
                else:
                    self.display_event_list(filtered)

    # ------------------------------------------------------------------
    # Analytics display
    # ------------------------------------------------------------------
    def display_analytics(self, events):
        """Display summary statistics and trends using AnalyticsReporter."""
        if not events:
            self.refresh_screen()
            self.display_message("No analysed events found.")
            questionary.select("Return to the main menu", choices=["Close"]).ask()
            return

        reporter = AnalyticsReporter(events)
        summary = reporter.generate_summary()
        total = summary["total_events"]
        ratio = summary["attendance_ratio"]
        attend_pct = round(ratio * 100, 1)

        self.refresh_screen()

        # 1. Overview Panel
        rec_breakdown = summary["recommendation_breakdown"]
        overview_text = (
            f"[bold]Total Analysed Events:[/bold] {total}\n"
            f"[bold]Attendance Rate:[/bold] {attend_pct}% "
            f"([green]{rec_breakdown.get('ATTEND', 0)} ATTEND[/green], "
            f"[yellow]{rec_breakdown.get('MAYBE', 0)} MAYBE[/yellow], "
            f"[red]{rec_breakdown.get('SKIP', 0)} SKIP[/red])"
        )
        self.console.print(
            Panel(overview_text, title="[bold cyan]Event Analytics Overview[/bold cyan]", expand=False)
        )

        # 2. Category Distribution Table
        cat_dist = summary["category_distribution"]
        cat_table = Table(title="Category Distribution", show_lines=True)
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Count", style="white")
        cat_table.add_column("Share", style="yellow")
        for cat, count in sorted(cat_dist.items(), key=lambda x: x[1], reverse=True):
            pct = round((count / total) * 100, 1) if total > 0 else 0
            cat_table.add_row(cat, str(count), f"{pct}%")
        self.console.print(cat_table)

        # 3. Workload vs Recommendation Table
        workload_table = Table(title="Workload vs Recommendation", show_lines=True)
        workload_table.add_column("Workload", style="cyan")
        workload_table.add_column("ATTEND", style="green")
        workload_table.add_column("MAYBE", style="yellow")
        workload_table.add_column("SKIP", style="red")
        workload_table.add_column("Total", style="white")

        for wl in ("Low", "Medium", "High"):
            counts = summary["workload_breakdown"].get(wl, {})
            att = counts.get("ATTEND", 0)
            may = counts.get("MAYBE", 0)
            skp = counts.get("SKIP", 0)
            wl_total = att + may + skp
            workload_table.add_row(wl, str(att), str(may), str(skp), str(wl_total))
        self.console.print(workload_table)

        # 4. Average Scores Panel
        avg = summary["average_scores"]
        scores_text = (
            f"Career Relevance:  {avg.get('career_relevance', 0.0)} / 5.0\n"
            f"Learning Value:    {avg.get('learning_value', 0.0)} / 5.0\n"
            f"Networking Value:  {avg.get('networking_value', 0.0)} / 5.0\n"
            f"Total Event Value: {avg.get('total_value', 0.0)} / 15.0"
        )
        self.console.print(
            Panel(scores_text, title="[bold magenta]Average Scores[/bold magenta]", expand=False)
        )

        questionary.select("Return to the main menu", choices=["Back"]).ask()
