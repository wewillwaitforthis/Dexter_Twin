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
import time

import requests

JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")

# Demo motion, in degrees: each joint swings around a centre by +/- amplitude.
# The centres are the example pose (0, -45, 90, 0, 0, 30); the amplitudes are
# kept modest so the arm stays well inside its joint limits.
CENTRE = {"Rotation": 0, "Pitch": -45, "Elbow": 90, "Wrist_Pitch": 0, "Wrist_Roll": 0, "Jaw": 30}
AMPLITUDE = {"Rotation": 30, "Pitch": 20, "Elbow": 20, "Wrist_Pitch": 15, "Wrist_Roll": 20, "Jaw": 15}
PERIOD = 8.0   # seconds per full swing


def make_payload(angles_deg, radians=False):
    """Build the JSON body the server expects, converting units if asked."""
    if radians:
        angles = {name: math.radians(v) for name, v in angles_deg.items()}
        units = "radians"
    else:
        angles = dict(angles_deg)
        units = "deg"
    return {"units": units, "angles": angles}


def sweep_pose(t):
    """Joint angles (degrees) at time t seconds. Joints are phase-shifted so they don't move in lockstep."""
    w = 2 * math.pi / PERIOD
    return {
        name: CENTRE[name] + AMPLITUDE[name] * math.sin(w * t + i * math.pi / 3)
        for i, name in enumerate(JOINTS)
    }


def send_once(session, url, payload):
    r = session.post(url, json=payload, timeout=2)   # json= sets Content-Type and Content-Length
    return r


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="localhost", help="server address (default localhost)")
    p.add_argument("--port", type=int, default=8000, help="server port (default 8000)")
    p.add_argument("--rate", type=float, default=30.0, help="messages per second (default 30)")
    p.add_argument("--duration", type=float, help="stop after this many seconds (default: run until Ctrl+C)")
    p.add_argument("--once", action="store_true", help="send the example pose one time and exit")
    p.add_argument("--radians", action="store_true", help="send radians instead of degrees")
    args = p.parse_args()

    url = f"http://{args.host}:{args.port}/angles"

    with requests.Session() as session:
        if args.once:
            payload = make_payload(CENTRE, args.radians)
            try:
                r = send_once(session, url, payload)
            except requests.exceptions.RequestException as e:
                raise SystemExit(f"could not reach {url}: {e}")
            print(r.status_code, r.json())
            return

        print(f"Sending to {url} at {args.rate:g} Hz. Ctrl+C to stop.")
        period = 1 / args.rate
        t0 = next_send = time.perf_counter()
        sent = failed = 0
        try:
            while True:
                now = time.perf_counter()
                if args.duration and now - t0 >= args.duration:
                    break

                payload = make_payload(sweep_pose(now - t0), args.radians)
                try:
                    r = send_once(session, url, payload)
                except requests.exceptions.RequestException as e:
                    # Server not up yet, or it went away: report once per second and keep trying.
                    print(f"\rcannot reach server ({type(e).__name__}); retrying...   ", end="", flush=True)
                    time.sleep(1.0)
                    next_send = time.perf_counter()
                    continue

                if r.status_code == 200:
                    sent += 1
                else:
                    failed += 1
                    print(f"\nrejected: {r.status_code} {r.text.strip()}")
                print(f"\rsent {sent}  rejected {failed}", end="", flush=True)

                # Hold a steady rate by scheduling against a clock, not by sleeping a fixed amount.
                next_send += period
                delay = next_send - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_send = time.perf_counter()   # fell behind; don't try to catch up
        except KeyboardInterrupt:
            pass
        print()


if __name__ == "__main__":
    main()