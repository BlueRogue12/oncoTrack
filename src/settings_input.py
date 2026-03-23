from .config import TrackerConfig


def get_user_settings(config: TrackerConfig):

    print("\nConfigure TrackMate Settings")
    print("--------------------------------")

    radius = input(f"Blob radius [{config.radius}]: ")
    threshold = input(f"Threshold [{config.threshold}]: ")
    link_dist = input(f"Linking distance [{config.max_distance_gate}]: ")

    # Update values only if user typed something
    if radius:
        config.radius = float(radius)

    if threshold:
        config.threshold = float(threshold)

    if link_dist:
        config.max_distance_gate = float(link_dist)

    return config