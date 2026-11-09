#!/usr/bin/env python3
"""Send fake joint angles (degrees) over a serial port, to test so100_move.py.
 
    python send_test_angles.py /dev/ttyUSB1            # or one end of a virtual pair
Virtual pair on Linux/macOS:  socat -d -d pty,raw,echo=0 pty,raw,echo=0
"""
import time

import pygame
pygame.init()
pygame.joystick.init()
import socket

if pygame.joystick.get_count() == 0:
    print("No controller detected")
    quit()
else:
    controller = pygame.joystick.Joystick(0)
    print("Controller plugged into port 0 and operable")

angles = [
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    45.0
]

limits = [
    (-180, 180),
    (-90, 90),
    (-90, 90),
    (-90, 90),
    (-180, 180),
    (0, 90)
]

SPEED = 60 
HOST = '127.0.0.1'
PORT = 51234

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
    client_sock.connect((HOST, PORT))

    t0 = time.time()
    while True:
        pygame.event.pump()
        t = time.time() - t0

        controls = [
            controller.get_axis(0),
            -controller.get_axis(1),
            -controller.get_axis(2),
            controller.get_axis(3),
            controller.get_button(5) - controller.get_button(4),
            controller.get_button(0) - controller.get_button(1)
        ]

        for joint, value in enumerate(controls):
            if abs(value) > 0.12:
                angles[joint] += value * SPEED * 0.2

            low, high = limits[joint]
            angles[joint] = max(low, min(high, angles[joint]))

        print("Joint angles:", angles, flush=True)

        client_sock.sendall((", ".join(f"{a:.2f}" for a in angles) + "\n").encode())
        time.sleep(0.2)   # 50 Hz
