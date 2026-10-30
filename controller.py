import pygame

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller detected")
    quit()
else:
    controller = pygame.joystick.Joystick(0)
    print("Controller plugged into port 0 and operable")

angles = {
    "Rotation": 0.0,
    "Pitch": 0.0,
    "Elbow": 0.0,
    "Wrist_Pitch": 0.0,
    "Wrist_Roll": 0.0,
    "Jaw": 45.0
}

limits = {
    "Rotation": (-180, 180),
    "Pitch": (-90, 90),
    "Elbow": (-90, 90),
    "Wrist_Pitch": (-90, 90),
    "Wrist_Roll": (-180, 180),
    "Jaw": (0, 90)
}

SPEED = 60  # degrees per second
clock = pygame.time.Clock()

def main():
    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        controls = {
            "Rotation": controller.get_axis(0),
            "Pitch": -controller.get_axis(1),
            "Elbow": -controller.get_axis(2),
            "Wrist_Pitch": controller.get_axis(3),
            "Wrist_Roll": controller.get_button(5) - controller.get_button(4),
            "Jaw": controller.get_button(0) - controller.get_button(1)
        }

        for joint, value in controls.items():
            if abs(value) > 0.12:
                angles[joint] += value * SPEED * dt

            low, high = limits[joint]
            angles[joint] = max(low, min(high, angles[joint]))


        print(
        f"{angles['Rotation']:.2f} "
        f"{angles['Pitch']:.2f} "
        f"{angles['Elbow']:.2f} "
        f"{angles['Wrist_Pitch']:.2f} "
        f"{angles['Wrist_Roll']:.2f} "
        f"{angles['Jaw']:.2f}"
        )

if __name__ == "__main__":
    main()
    pygame.quit()