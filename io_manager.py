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

    return {
        "field_of_study": field_of_study,
        "interests": interests
    }


def get_event_information():
    print("\n--- Event Information ---")

    event_info = input(
        "Paste the event name and description here:\n"
    ).strip()

    while event_info == "":
        print("Event information cannot be empty.")
        event_info = input(
            "Please enter the event name and description:\n"
        ).strip()

    return event_info


def get_workload():
    WORKLOAD_OPTIONS = {
        "1": "Low",
        "2": "Medium",
        "3": "High"
    }
    print("\n--- Current Workload ---")
    print("1. Low")
    print("2. Medium")
    print("3. High")

    while True:
        workload = input("Enter your workload (1-3): ").strip()

        if workload in WORKLOAD_OPTIONS:
            return WORKLOAD_OPTIONS[workload]
        else:
            print("Invalid input. Please enter 1, 2 or 3.")


def display_recommendation(recommendation, reason):
    print("\n--- EventWise Recommendation ---")
    print("Recommendation:", recommendation)
    print("Reason:", reason)


def display_error(message):
    print("\nError:", message)

def ask_to_use_saved_profile():

    prompt = "\nDo you want to use the saved student profile? (yes/no): "
    answer = input(prompt).strip().lower()

    while answer not in ["yes", "no", "y", "n"]:
        print("Please answer 'yes' or 'no'.")
        answer = input(prompt).strip().lower()

    return answer in ("yes", "y")

def show_main_menu():
    """placeholder for main menu for now, will be updated in the future"""
    print("\n===== EventWise =====")
    print("1. Evaluate a new event")
    print("2. View event history")
    print("3. Update profile")
    print("4. Quit")

def get_menu_choice():
    """returns the user's chosen menu option either from 1 to 4"""
    while True:
        choice = input("Choose an option (1-4): ").strip()
        if choice in ("1", "2", "3", "4"):
            return int(choice)
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")