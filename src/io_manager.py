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


def display_welcome():
    console.print(
        Panel(
            "[bold cyan]EventWise[/bold cyan]\n"
            "AI-assisted student event decision system\n\n"
            "[dim]Tip: press Ctrl+C to go back without saving that step.[/dim]",
            expand=False,
        )
    )


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
