import pygame
from URDF.so100_ik import load_chain, fk, ik, to_menagerie_deg
from pathlib import Path
import numpy as np


pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller detected")
    quit()
else:
    controller = pygame.joystick.Joystick(0)
    print("Controller plugged into port 0 and operable")

URDF = str(Path(__file__).resolve().parent / "URDF" / "so100_tcp.urdf")
CLAW_SPEED = 90.0
SPEED = 0.1
DEADZONE = 0.1
PITCH = None
clock = pygame.time.Clock()

def main():
    chain = load_chain(URDF)
    joints = {j["name"]: j for j in chain}
    
    q = {"shoulder_pan": 0.0, "shoulder_lift": 1.5, "elbow_flex": -1.5,
         "wrist_flex": 0.0, "wrist_roll": 0.0, "gripper": 0.0}
    T, _ = fk(chain, q)
    target = T[:3, 3].copy()        # start XYZ comes from FK, not (0, 0, 0)
    claw = 90.0

    x, y, z = 0.0, 0.0, 0.0
    claw = 90.0 

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        delta = np.array([
            deadzone(controller.get_axis(0)),
            deadzone(-controller.get_axis(1)),
            deadzone(-controller.get_axis(3)),
        ]) * SPEED * dt

        if delta.any():
            new_target = target + delta
            q_new, err, ok = ik(chain, new_target, q_init=q,
                                pitch_deg=PITCH, seeds=1, iters=50)
            if ok:
                target, q = new_target, q_new
            # else: out of reach, so keep the previous target and angles

        # Triggers -> claw
        if controller.get_axis(4) > 0.7:
            claw = min(180.0, claw + CLAW_SPEED * dt)
        if controller.get_axis(5) > 0.7:
            claw = max(0.0, claw - CLAW_SPEED * dt)
        g = joints.get("gripper")
        if g:
            q["gripper"] = g["lower"] + (claw / 180.0) * (g["upper"] - g["lower"])

        send_to_sim(to_menagerie_deg(q))


def deadzone(v):
    return v if abs(v)>0.15 else 0.0

def send_to_sim(angles):
    return angles


if __name__ == "__main__":
    main()
    pygame.quit()