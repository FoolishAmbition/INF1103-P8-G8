import questionary
from questionary import Choice, form

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.logic_manager import (format_scores)

console = Console()


# ----------------------------------------------------------------------------------
# HELPER
# ----------------------------------------------------------------------------------


# validation for empty
def not_empty(text):
    if not text or not str(text).strip():
        return "This field cannot be empty."
    return True


# just display header !! COSMETIC !!
def display_welcome():
    console.print(
        Panel(
            "[bold cyan]EventWise[/bold cyan]\n"
            "AI-assisted student event decision system\n\n"
            "[dim]Tip: press Ctrl+C to go back without saving that step.[/dim]",
            expand=False,
        )
    )


# this to refresh the screen everytime an option is chosen
# so to clear space and remove clutter
def refresh_screen(status=None, is_error=False):
    console.clear()
    display_welcome()

    if status:
        if is_error:
            display_error(status)
        else:
            display_message(status)


# Display the main menu and return the option selected by the user
def get_main_menu_choice(main_menu_choice, status=None, is_error=False):
    refresh_screen(status, is_error)

    return questionary.select(
        "What would you like to do?",
        choices=main_menu_choice,
    ).ask()


# create empty profile
def empty_profile():
    return {
        "field_of_study": "",
        "interests": [],
    }


# SHALLOW copy profile
def copy_profile(profile):
    return {
        "field_of_study": profile["field_of_study"],
        "interests": list(profile["interests"]),
    }


# default if the field already contains information
def ask_text(message, default=""):
    value = questionary.text(
        message,
        default=default,
        validate=not_empty,
    ).ask()

    # cancelled the input
    if value is None:
        return None

    return value.strip()


def display_error(message):
    console.print(f"\n[red]Error:[/red] {message}")


def display_message(message):
    console.print(f"\n{message}")


def color_guide():
    return { 
        1: "bold green", 
        2: "bold yellow", 
        3: "bold red" 
    }

# ----------------------------------------------------------------------------------
# FUNCTIONS
# ----------------------------------------------------------------------------------
def edit_profile(profile):

    # Work on a copy so that changes are only applied when the user saves
    draft = copy_profile(profile)

    status = None
    is_error = False

    while True:

        # Display initial field
        field_label = draft["field_of_study"] or "(not set)"
        if draft["interests"]:
            interests_label = ", ".join(draft["interests"])
        else:
            interests_label = "(not set)"

        refresh_screen(status, is_error)
        status = None
        is_error = False

        # Edit profile menu
        choice = questionary.select(
            "Edit Profile",
            choices=[
                f"Field of study: {field_label}",
                f"Interests:      {interests_label}",
                "Save",
                "Cancel",
            ],
        ).ask()

        # If cancels, return original
        if choice is None or choice == "Cancel":
            return profile

        # Edit the field of study
        if choice.startswith("Field of study:"):
            refresh_screen()

            new_value = ask_text(
                "What are you studying?",
                default=draft["field_of_study"],
            )
            if new_value is not None:
                draft["field_of_study"] = new_value

        # Edit the interests
        elif choice.startswith("Interests:"):
            draft["interests"] = edit_interests(draft["interests"])

        # Save
        elif choice == "Save":

            # Check if filled or empty
            if not draft["field_of_study"].strip() or not draft["interests"]:
                status = "Field of study and at least one interest are required."
                is_error = True
                continue

            return draft


# add & remove interest
def edit_interests(interests):
    original = list(interests)  # copy original list of interest
    draft = list(interests)  # draft list of interest
    status = None
    is_error = False

    while True:

        # show interest if there is existing
        if draft:
            listed = f"Current interests: {', '.join(draft)}"
        else:
            listed = "Current interests: (none yet)"

        refresh_screen(status, is_error=is_error)
        display_message(listed)

        status = None
        is_error = False

        # Only show Remove interest if there is at least one interest
        if draft:
            choices = ["Add interest", "Remove interest", "Done"]
        else:
            choices = ["Add interest", "Done"]

        choice = questionary.select(
            "Edit interests",
            choices=choices,
        ).ask()

        # cancel, keep original
        if choice is None:
            return original

        # done, return the draft
        if choice == "Done":
            return draft

        # Add a new interest
        if choice == "Add interest":
            refresh_screen(listed)

            new_interest = ask_text("Add an interest:")
            if new_interest is None:
                continue

            # check if duplicate, if yes return error
            if new_interest.lower() in (item.lower() for item in draft):
                status = "That interest is already in your list."
                is_error = True
                continue

            draft.append(new_interest)

        # Remove an existing interest
        elif choice == "Remove interest":
            refresh_screen(listed)

            to_remove = questionary.select(
                "Remove which interest?",
                choices=draft,
            ).ask()

            if to_remove is None:
                continue

            draft.remove(to_remove)


def get_event_information(previous=None):
    status = None
    is_error = False
    if previous:
        event_name, event_description, workload = previous
    else:
        event_name = event_description = workload = ""

    while True:
        refresh_screen(status, is_error)
        status = None
        is_error = False

        # Edit profile menu
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

        # If cancels, return original
        if choice is None or choice == "Cancel":
            return

        # Edit event name
        if choice.startswith("Event Name"):
            refresh_screen()

            new_value = ask_text(
                "Paste Your Event Name here:",
                default=event_name,
            )
            if new_value is not None:
                event_name = new_value

        # Edit event description
        elif choice.startswith("Event Description"):
            refresh_screen()

            new_value = ask_text(
                "Paste Your Event Description here:",
                default=event_description,
            )
            if new_value is not None:
                event_description = new_value

        # Edit the workload
        elif choice.startswith("Current workload"):
            refresh_screen()

            new_value = questionary.select(
                "What is your current workload",
                choices=[
                    "Low",
                    "Medium",
                    "High",
                    Choice(title="Cancel", value=0),
                ],
            ).ask()

            if new_value != 0:
                workload = new_value
        # Save
        elif choice == "Submit":

            # Check if filled or empty
            if not event_name.strip() or not event_description.strip() or not workload:
                status = "All the fields are required."
                is_error = True
                continue

            return (event_name, event_description, workload)


def display_event_result(event_summary, back_label="Return to the main menu"):
    refresh_screen()

    # Event Info
    priority = event_summary.get("priority", "No priority")
    recommendation = event_summary.get("recommendation", "No recommendation")
    rec_style = {
        "ATTEND": "bold green",
        "MAYBE": "bold yellow",
        "SKIP": "bold red"
    }.get(str(recommendation).upper(), "bold cyan")

    console.rule("[bold cyan]Event[/bold cyan]", align="left", style="cyan")
    console.print(f'[bold]{event_summary.get("event_name")}[/bold]\n{event_summary.get("event_description")}\n')

    # Score breakdown
    format_dict = format_scores(event_summary["career_relevance"], event_summary["learning_value"], event_summary["networking_value"])
    console.rule(f"[bold magenta]Score Breakdown[/bold magenta]", align="left", style="magenta")
    console.print(f'Career Relevance: {format_dict["career_relevance"]}  •  Learning Value: {format_dict["learning_value"]}  •  Networking Value: {format_dict["networking_value"]}\n')

    # Priority and Recommendation
    console.rule(
        f"[{rec_style}]Priority: {priority} - Recommendation: {recommendation}[/{rec_style}]",
        align="left",
        style=rec_style,
    )
    console.print(f"{event_summary.get('reason', 'No reason provided.')}\n")

    # AI reasoning
    console.rule(f"[bold blue]AI Reasoning[/bold blue]", align="left", style="blue")
    console.print(f"{event_summary.get('ai_reasoning', 'No AI reasoning provided.')}\n")

    questionary.select(back_label, choices=["Back"]).ask()


def display_all_events(events: list):
    if not events:
        refresh_screen()
        display_message("No analysed events found.")
        questionary.select("Return to the main menu", choices=["Close"]).ask()
        return

    while True:
        refresh_screen()

        table = Table(title="Analysed Events", show_lines=True)

        table.add_column("No.", style="cyan")
        table.add_column("Event", style="cyan", max_width=25)
        table.add_column("Priority", style="yellow")
        table.add_column("Recommendation", style="green")
        table.add_column("Reason", style="white", max_width=50)
        table.add_column("Career", style="white")
        table.add_column("Learning", style="white")
        table.add_column("Networking", style="white")

        styles = color_guide()
        rec_levels = {"ATTEND": 1, "MAYBE": 2, "SKIP": 3}
        priority_levels = {"High": 1, "Medium": 2, "Low": 3}

        for i, event in enumerate(events, start=1):
            
            rec = str(event.get("recommendation", "Unknown"))
            rec_style = styles.get(rec_levels.get(rec.upper()), "bold cyan")

            priority = str(event.get("priority", "Unknown"))
            priority_style = styles.get(priority_levels.get(priority), "bold cyan")

            table.add_row(
                str(i),
                str(event.get("event_name", "Unnamed event")),
                #str(event.get("priority", "Unknown")),
                f"[{priority_style}]{priority}[/{priority_style}]",
                f"[{rec_style}]{rec}[/{rec_style}]",
                # str(event.get("recommendation", "Unknown")),
                str(event.get("reason", "No reason provided")),
                str(event.get("career_relevance", 0)),
                str(event.get("learning_value", 0)),
                str(event.get("networking_value", 0)),
            )

        console.print(table)

        choices = [
            questionary.Choice(
                title=f"{i}. {event.get('event_name', 'Unnamed event')}",
                value=event,
            )
            for i, event in enumerate(events, start=1)
        ]
        choices.append("Back")

        selected = questionary.select("Select an event to view", choices=choices).ask()

        if selected is None or selected == "Back":
            return

        display_event_result(selected, back_label="Return to event table")
