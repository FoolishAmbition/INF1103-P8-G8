from rich import print
from src.io_manager import (
    display_error,
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
)

MAIN_MENU_CHOICES = [
    "Profile",
    "Analyse New Events",
    "View Analysed Events",
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

        #reset
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

            case "Analyse New Events":
                if profile == empty_profile(): 
                    status = "Please create your profile first"
                    is_error = True
                    continue

                event_info = get_event_information()
                if event_info is None:
                    status = "Cancelled. No event was added."
                    continue

                event_name, event_description, curr_workload = event_info

                ai_res = analyze_event(profile, event_name, event_description) 

                # TODO: Remove hard coded WORKLOAD
                event_summary = generate_summary(ai_res, curr_workload)
                event_summary |= {"event_name": event_name, "event_description":event_description, "curr_workload": curr_workload}
                display_event_result(event_summary, event_name, event_description)
                events.append(event_summary);
                
            case "View Analysed Events":
                # get events
                # then i pass it to a function to display all events to console
                display_all_events(events)

if __name__ == "__main__":
    main()
