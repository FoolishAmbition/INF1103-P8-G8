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


def display_error(message):
    print("\nError:", message)