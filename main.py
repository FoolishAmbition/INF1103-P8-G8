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