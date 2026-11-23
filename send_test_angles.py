#!/usr/bin/env python3
"""Send joint angles to the AngleReader HTTP server (POST /angles).

    python send_angles.py --once                  # send one pose and exit
    python send_angles.py                         # smooth demo sweep at 30 Hz
    python send_angles.py --rate 60 --duration 20
    python send_angles.py --host 100.82.127.15 --port 51234
    python send_angles.py --radians               # same motion, sent as radians

Needs:  pip install requests
"""
import math
from pathlib import Path
import numpy as np
import requests
import sys
import time
from controller import init, movement

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


DT = 0.02
HOST = '127.0.0.1'
PORT = 8000

session = requests.Session()
URL = f"http://{HOST}:{PORT}/angles"

def main():
    global angles
    c = init()
    chain = load_chain(URDF)
    q = {"shoulder_pan": 0.0, "shoulder_lift": 1.5, "elbow_flex": -1.5,
        "wrist_flex": 0.0, "wrist_roll": 0.0, "gripper": 0.0}
    target = fk(chain, q)[0][:3, 3].copy()


    while True:
        dxyz, droll, dclaw = movement(c, DT)
        delta = np.array(dxyz)

        roll = max(limits[4][0], min(limits[4][1], angles[4] + droll))
        claw = max(limits[5][0], min(limits[5][1], angles[5] + dclaw))
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

        for i in range(len(angles)):
            data_json["angles"][JOINTS[i]] = angles[i]

        session.post(URL, json=data_json, timeout=2)        
        time.sleep(DT)

if __name__ == "__main__":
    main()