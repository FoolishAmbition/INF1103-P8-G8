from src.io_manager import (
    get_main_menu_choice,
)


def main():
    status = None
    is_error = False

    while True:
        choice = get_main_menu_choice(status, is_error)

if __name__ == "__main__":
    main()
