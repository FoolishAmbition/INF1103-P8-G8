<<<<<<< HEAD
import questionary
from rich.console import Console
from rich.panel import Panel

console = Console()


profile = {
    "name": "Andrew",
    "age": "20",
    "course": "Computer Science",
    "email": "andrew@email.com"
}

def edit_profile():
    while True:
        choices = [
            f"Name:   {profile['name']}",
            f"Age:    {profile['age']}",
            f"Course: {profile['course']}",
            f"Email:  {profile['email']}",
            "Save",
            "Cancel"
        ]

        choice = questionary.select(
            "Edit Profile",
            choices=choices
        ).ask()

        if choice.startswith("Name:"):
            new_value = questionary.text(
                "Enter your name:",
                default=profile["name"]
            ).ask()

            if new_value is not None:
                profile["name"] = new_value

        elif choice.startswith("Age:"):
            new_value = questionary.text(
                "Enter your age:",
                default=profile["age"]
            ).ask()

            if new_value is not None:
                profile["age"] = new_value

        elif choice.startswith("Course:"):
            new_value = questionary.text(
                "Enter your course:",
                default=profile["course"]
            ).ask()

            if new_value is not None:
                profile["course"] = new_value

        elif choice.startswith("Email:"):
            new_value = questionary.text(
                "Enter your email:",
                default=profile["email"]
            ).ask()

            if new_value is not None:
                profile["email"] = new_value

        elif choice == "Save":
            print("\n✓ Profile saved!")
            return

        elif choice == "Cancel":
            return


def main():
    console.print(
        Panel(
            "[bold cyan]EVENT SUGGESTOR APP[/bold cyan]",
            expand=False
        )
    )
    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Profile",
                "Add Event",
                "Analyse Events",
                "Exit"
            ]
        ).ask()

        if choice == "Profile":
            edit_profile()

        elif choice == "Add Event":
            print("\nAdd Event selected.")

        elif choice == "Analyse Events":
            print("\nAnalyse Events selected.")

        elif choice == "Exit":
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
=======
import io_manager


def main():
    profile = io_manager.get_student_profile()
    event_info = io_manager.get_event_information()
    workload = io_manager.get_workload()

    print("\n--- Test Output ---")
    print("Profile:", profile)
    print("Event Info:", event_info)
    print("Workload:", workload)

main()
>>>>>>> origin/io_manager
