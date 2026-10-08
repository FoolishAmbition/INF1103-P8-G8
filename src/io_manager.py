import questionary

from rich.console import Console
from rich.panel import Panel

console = Console()

MAIN_MENU_CHOICES = [
    "Profile",
    "Add Event",
    "Analyse Events",
    "Exit",
]


# Validation
def not_empty(text):
    if not text or not str(text).strip():
        return "This field cannot be empty."
    return True


def display_welcome():
    console.print(
        Panel(
            "[bold cyan]EventWise[/bold cyan]\n"
            "AI-assisted student event decision system\n\n"
            "[dim]Tip: press Ctrl+C to go back without saving that step.[/dim]",
            expand=False,
        )
    )


# Clear the terminal and display the welcome message again
# If a status message is provided, display it below the welcome message
# is_error determines whether the status should be displayed as an error instead
def refresh_screen(status=None, is_error=False):
    console.clear()
    display_welcome()

    if status:
        if is_error:
            display_error(status)
        else:
            display_message(status)


# Display the main menu and return the option selected by the user
def get_main_menu_choice(status=None, is_error=False):
    refresh_screen(status, is_error)

    return questionary.select(
        "What would you like to do?",
        choices=MAIN_MENU_CHOICES,
    ).ask()


# Create and return a new empty profile
def empty_profile():
    return {
        "field_of_study": "",
        "interests": [],
    }


# Create a copy of the profile so that the original profile
# is not changed while the user is editing it
def copy_profile(profile):
    return {
        "field_of_study": profile["field_of_study"],
        "interests": list(profile["interests"]),
    }


# default is the value shown if the field already contains information
def ask_text(message, default=""):
    value = questionary.text(
        message,
        default=default,
        validate=not_empty,
    ).ask()

    # None means the user cancelled the input
    if value is None:
        return None

    # Remove unnecessary spaces before returning the input
    return value.strip()


# Allow the user to add or remove interests
def edit_interests(interests):

    # Keep a copy of the original interests in case the user cancels
    original = list(interests)

    # Create a separate list that can be modified while editing
    draft = list(interests)

    status = None
    is_error = False

    while True:

        # Create a message showing the user's current interests
        if draft:
            listed = f"Current interests: {', '.join(draft)}"
        else:
            listed = "Current interests: (none yet)"

        # Refresh the screen and display the current status/interests
        # If status is empty, listed is displayed instead
        refresh_screen(status or listed, is_error=is_error)

        # If there was an error, also show the current interests
        if status:
            display_message(listed)

        # Reset the status after displaying it
        status = None
        is_error = False

        # Only show "Remove interest" when there is at least one interest
        if draft:
            choices = ["Add interest", "Remove interest", "Done"]
        else:
            choices = ["Add interest", "Done"]

        choice = questionary.select(
            "Edit interests",
            choices=choices,
        ).ask()

        # If the user cancels, discard the draft and keep the original
        if choice is None:
            return original

        # If the user chooses Done, return the edited list
        if choice == "Done":
            return draft

        # Add a new interest
        if choice == "Add interest":
            refresh_screen(listed)

            new_interest = ask_text("Add an interest:")

            # If the user cancels, return to the edit menu
            if new_interest is None:
                continue

            # Prevent duplicate interests, ignoring capitalisation
            if new_interest.lower() in (item.lower() for item in draft):
                status = "That interest is already in your list."
                is_error = True
                continue

            # Add the new interest to the temporary draft
            draft.append(new_interest)

        # Remove an existing interest
        elif choice == "Remove interest":
            refresh_screen(listed)

            to_remove = questionary.select(
                "Remove which interest?",
                choices=draft,
            ).ask()

            # If the user cancels, return to the edit menu
            if to_remove is None:
                continue

            # Remove the selected interest from the draft
            draft.remove(to_remove)


# Allow the user to edit their profile
def edit_profile(profile):

    # Work on a copy so that changes are only applied when the user saves
    draft = copy_profile(profile)

    status = None
    is_error = False

    while True:

        # Display the current field of study
        # "(not set)" is shown if the field is empty
        field_label = draft["field_of_study"] or "(not set)"

        # Display the current interests
        if draft["interests"]:
            interests_label = ", ".join(draft["interests"])
        else:
            interests_label = "(not set)"

        # Refresh the screen and show any status/error message
        refresh_screen(status, is_error)

        # Clear the status after displaying it
        status = None
        is_error = False

        # Display the profile editing menu
        choice = questionary.select(
            "Edit Profile",
            choices=[
                f"Field of study: {field_label}",
                f"Interests:      {interests_label}",
                "Save",
                "Cancel",
            ],
        ).ask()

        # If the user cancels, discard the draft and return the original profile
        if choice is None or choice == "Cancel":
            return profile

        # Edit the field of study
        if choice.startswith("Field of study:"):
            refresh_screen()

            new_value = ask_text(
                "What are you studying?",
                default=draft["field_of_study"],
            )

            # Only update the draft if the user did not cancel
            if new_value is not None:
                draft["field_of_study"] = new_value

        # Edit the interests
        elif choice.startswith("Interests:"):
            draft["interests"] = edit_interests(draft["interests"])

        # Save the changes
        elif choice == "Save":

            # Make sure the required profile information has been entered
            if not draft["field_of_study"].strip() or not draft["interests"]:
                status = "Field of study and at least one interest are required."
                is_error = True
                continue

            # Return the edited profile
            return draft


def display_error(message):
    console.print(f"\n[red]Error:[/red] {message}")


def display_message(message):
    console.print(f"\n{message}")


# -------------------------------------------------------------------------------------------------\
# ------------------------------------- ALYSSIA CODE -----------------------------------------------
# Alyssia code TODO: Refactor this code to use questionary
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
