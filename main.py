from src.io_manager import (
    get_main_menu_choice,
    display_message,
    edit_profile,
    empty_profile,
)


def main():
    profile = empty_profile()
    status = None
    is_error = False

    while True:
        choice = get_main_menu_choice(status, is_error)

        if choice is None or choice == "Exit":
            display_message("Goodbye!")
            break

        if choice == "Profile":
            updated = edit_profile(profile)
            if updated is not profile:
                status = "Profile saved!"
            profile = updated

if __name__ == "__main__":
    main()
