import questionary
from questionary import Choice

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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


# TODO:
# 1.submit button
# 2.have them display together instead of one by one
# 3.erorr handling, like going back
def get_event_information():
    status = None
    is_error = False
    event_name = event_description = curr_workload = ""

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
                f"Current workload:  {curr_workload or '(not set)'}",
                "Submit",
                "Cancel",
            ],
        ).ask()

        # If cancels, return original
        if choice is None or choice == "Cancel":
            return

        # Edit the field of study
        if choice.startswith("Event Name"):
            refresh_screen()

            new_value = ask_text(
                "Paste Your Event Name here:",
                default=event_name,
            )
            if new_value is not None:
                event_name = new_value

        # Edit the field of study
        elif choice.startswith("Event Description"):
            refresh_screen()

            new_value = ask_text(
                "Paste Your Event Description here:",
                default=event_description,
            )
            if new_value is not None:
                event_description = new_value

        # Edit the field of study
        elif choice.startswith("Current workload"):
            refresh_screen()

            new_value = questionary.select(
                "What is your current workload",
                choices=[
                    Choice(title="Low", value=1),
                    Choice(title="Medium", value=2),
                    Choice(title="High", value=3),
                    Choice(title="Cancel", value=0),
                ],
            ).ask()

            if new_value != 0:
                curr_workload = new_value
        # Save
        elif choice == "Submit":

            # Check if filled or empty
            if not event_name.strip() or not event_description.strip():
                status = "All the fields are required."
                is_error = True
                continue

            return (event_name, event_description, curr_workload)

    # TODO: 1. ask for workload
    #      2. ask for event date and time using textual-datepicker

    event_name = ask_text("Paste the event name")
    event_description = ask_text("Paste the event description:")
    current_workload = ask_text("What is your current workload:")

    # Return None if the user cancels
    if event_name is None or event_description is None:
        return None

    return (event_name, event_description)


def recommendation_style(recommendation):
    label = str(recommendation).upper()
    if label == "ATTEND":
        return "bold green"
    if label == "MAYBE":
        return "bold yellow"
    if label == "SKIP":
        return "bold red"
    return "bold cyan"


def display_event_result(event_summary, event_name, event_description):
    refresh_screen()

    priority = event_summary.get("priority", "No priority")
    recommendation = event_summary.get("recommendation", "No recommendation")
    rec_style = recommendation_style(recommendation)

    console.rule("[bold cyan]Event[/bold cyan]", align="left", style="cyan")
    console.print(f"[bold]{event_name}[/bold]\n{event_description}\n")

    console.rule(
        f"[{rec_style}]Priority: {priority} - Verdict: {recommendation}[/{rec_style}]",
        align="left",
        style=rec_style,
    )
    console.print(f"{event_summary.get('reason', 'No reason provided.')}\n")

    console.rule(f"[bold blue]AI Reasoning[/bold blue]", align="left", style="blue")
    console.print(f"{event_summary.get("ai_reasoning", "No AI reasoning provided.")}\n")

    questionary.select("Return to the main menu", choices=["Close"]).ask()


# TODO: Display multiple event with click
def display_all_events(events: list):
    refresh_screen()

    if not events:
        display_message("No analysed events found.")
        questionary.select("Return to the main menu", choices=["Close"]).ask()
        return

    table = Table(title="Analysed Events", show_lines=True)

    table.add_column("Event", style="cyan", max_width=25)
    table.add_column("Priority", style="yellow")
    table.add_column("Recommendation", style="green")
    table.add_column("Reason", style="white", max_width=50)

    for event in events:
        table.add_row(
            str(event.get("event_name", "Unnamed event")),
            str(event.get("priority", "Unknown")),
            str(event.get("recommendation", "Unknown")),
            str(event.get("reason", "No reason provided")),
        )

    console.print(table)

    questionary.select("Return to the main menu", choices=["Close"]).ask()


# -------------------------------------------------------------------------------------------------\
# ------------------------------------- ALYSSIA CODE -----------------------------------------------
# Alyssia code TODO: Refactor this code to use questionary

"""
def get_student_profile():

    print("\n--- Student Profile ---")

    field_of_study = input("What are you studying? ").strip()

    while field_of_study == "":
        print("Field of study cannot be empty.")
        field_of_study = input("What are you studying? ").strip()

    interests = input("What are you interested in? ").strip()

    while interests == "":
        print("Interests cannot be empty.")
        interests = input("What are you interested in? ").strip()

    return {"field_of_study": field_of_study, "interests": interests}


def get_event_information():
    print("\n--- Event Information ---")

    event_info = input("Paste the event name and description here:\n").strip()

    while event_info == "":
        print("Event information cannot be empty.")
        event_info = input("Please enter the event name and description:\n").strip()

    return event_info


def get_workload():
    print("\n--- Current Workload ---")
    print("1. Low")
    print("2. Medium")
    print("3. High")

    while True:
        workload = input("Enter your workload (1-3): ").strip()

        if workload in ["1", "2", "3"]:
            return int(workload)

        print("Invalid input. Please enter 1, 2 or 3.")


def display_recommendation(recommendation, reason):
    print("\n--- EventWise Recommendation ---")
    print("Recommendation:", recommendation)
    print("Reason:", reason)
"""
