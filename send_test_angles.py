#!/usr/bin/env python3
"""Send joint angles to the AngleReader HTTP server (POST /angles).

    python send_angles.py --once                  # send one pose and exit
    python send_angles.py                         # smooth demo sweep at 30 Hz
    python send_angles.py --rate 60 --duration 20
    python send_angles.py --host 100.82.127.15 --port 51234
    python send_angles.py --radians               # same motion, sent as radians

Needs:  pip install requests
"""
import argparse
import math
from pathlib import Path
import numpy as np
import pygame
import requests

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller detected")
    quit()
else:
    controller = pygame.joystick.Joystick(0)
    print("Controller plugged into port 0 and operable")

HERE = Path(__file__).resolve().parent                                  # NEW
sys.path.append(str(HERE / "URDF"))  
from so100_ik import load_chain, fk, ik, to_menagerie_deg   
URDF = str(HERE / "URDF" / "so100_tcp.urdf")

JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")

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
XYZ_SPEED = 0.3
DT = 0.02
HOST = '127.0.0.1'
PORT = 51234

chain = load_chain(URDF)
q = {"shoulder_pan": 0.0, "shoulder_lift": 1.5, "elbow_flex": -1.5,
     "wrist_flex": 0.0, "wrist_roll": 0.0, "gripper": 0.0}
target = fk(chain, q)[0][:3, 3].copy()

def dead(v):                                  
    return v if abs(v) > 0.12 else 0.0

t0 = time.time()
while True:
    pygame.event.pump()
    t = time.time() - t0

    delta = np.array([
        dead(controller.get_axis(0)),
        dead(-controller.get_axis(1)),
        dead(-controller.get_axis(3)),
    ]) * XYZ_SPEED * DT

    roll = angles[4] + (controller.get_button(5) - controller.get_button(4)) * SPEED * DT
    claw = angles[5] + (controller.get_button(0) - controller.get_button(1)) * SPEED * DT
    roll = max(limits[4][0], min(limits[4][1], roll))
    claw = max(limits[5][0], min(limits[5][1], claw))
    q["wrist_roll"] = math.radians(roll)

    if delta.any():
        new_target = target + delta
        q_new, err, ok = ik(chain, new_target, q_init=q, seeds=1, iters=50)
        if ok:
            target, q = new_target, q_new

    angles = to_menagerie_deg(q)
    angles[4] = roll
    angles[5] = claw

    print("Joint angles:", angles, flush=True)

    data_json = {"units": "deg", "angles" : {}}

    for i in angles:
        data_json["angles"][JOINTS[i]] = angles[i]

    session = requests.Session()
    session.post(f"http://{HOST}:{PORT}/angles", json=data_json, timeout=2)
    time.sleep(DT)
