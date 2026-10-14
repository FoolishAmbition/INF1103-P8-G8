from src.io_manager import (
    get_main_menu_choice,
    display_message,
    edit_profile,
    empty_profile,
    get_event_information,
    display_event_result,
    display_all_events,
)

from src.ai_manager import (
    analyze_event,
)

from src.data_manager import (
    save_profile,
    load_profile,
    save_events,
    load_events,
)

from src.logic_manager import (
    generate_summary,
    add_dummy_event,
)

MAIN_MENU_CHOICES = [
    "Profile",
    "Analyse New Events",
    "View Analysed Events",
    "Add Dummy Event",
    "Exit",
]


def main():
    # profile
    profile = load_profile() or empty_profile()
    events = load_events()

    # init
    status = None
    is_error = False

    # main loop
    while True:
        choice = get_main_menu_choice(MAIN_MENU_CHOICES, status, is_error)

        # reset
        status = None
        is_error = False

        match choice:
            case "Exit" | None:
                # Save profile if not empty else dont save
                if not (profile == empty_profile()):
                    save_profile(profile)
                if events:
                    save_events(events)

                display_message("Goodbye!")
                break

            case "Profile":
                updated = edit_profile(profile)
                if updated is not profile:
                    status = "Profile saved!"
                profile = updated

            case "Analyse New Event":
                if profile == empty_profile():
                    status = "Please create your profile first"
                    is_error = True
                    continue

                event_info = get_event_information()
                if event_info is None:
                    status = "Cancelled. No event was added."
                    continue

                event_name, event_description, workload = event_info

                # check ai result
                ai_result, error_message = analyze_event(
                    profile, event_name, event_description
                )
                # Checks if ai result gives none ---> meaning error
                if ai_result is None:
                    status = error_message
                    is_error = True
                    continue

                # validate and process result
                event_summary, error_message = generate_summary(ai_result, workload)
                if event_summary is None:
                    status = error_message
                    is_error = True
                    continue

                event_summary |= {
                    "event_name": event_name,
                    "event_description": event_description,
                    "workload": workload,
                }
                display_event_result(event_summary)
                events.append(event_summary)
                status = "Event analyzed successfully"

            case "Add Dummy Event":
                dummy_result = add_dummy_event()

                # validate and process result
                event_summary, error_message = generate_summary(dummy_result, dummy_result.get("workload", "Low"))
                if event_summary is None:
                    status = error_message
                    is_error = True
                    continue

                display_event_result(event_summary)
                events.append(event_summary)
                status = "Dummy event added successfully"

            case "View Analysed Events":
                display_all_events(events)


if __name__ == "__main__":
    main()
