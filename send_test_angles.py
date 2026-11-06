#!/usr/bin/env python3
"""Send fake joint angles (degrees) over a serial port, to test so100_move.py.
 
    python send_test_angles.py /dev/ttyUSB1            # or one end of a virtual pair
Virtual pair on Linux/macOS:  socat -d -d pty,raw,echo=0 pty,raw,echo=0
"""
import math
import sys
import time

import socket

HOST = '100.82.127.15'
PORT = 51234

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
    client_sock.connect((HOST, PORT))

    t0 = time.time()
    while True:
        t = time.time() - t0
        angles = [
            60 * math.sin(0.5 * t),            # Rotation
            -60 + 30 * math.sin(0.7 * t),      # Pitch
            80 + 30 * math.sin(0.9 * t),       # Elbow
            30 * math.sin(1.1 * t),            # Wrist_Pitch
            40 * math.sin(1.3 * t),            # Wrist_Roll
            40 + 40 * math.sin(1.5 * t),       # Jaw
        ]
        client_sock.sendall((", ".join(f"{a:.2f}" for a in angles) + "\n").encode())
        time.sleep(0.2)   # 50 Hz
