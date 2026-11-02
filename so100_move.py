#!/usr/bin/env python3
"""Drive the MuJoCo Menagerie SO-100 arm from joint angles.

Joint order (matches the model's actuators):
    Rotation, Pitch, Elbow, Wrist_Pitch, Wrist_Roll, Jaw

Live mode: continuously read angles from a serial port.
    Each line is one sample: six numbers separated by commas or spaces,
    newline-terminated, e.g.   0, -45, 90, 0, 0, 30
    python so100_move.py --menagerie ~/mujoco_menagerie --port /dev/ttyUSB0
    python so100_move.py ... --port /dev/ttyUSB0 --baud 115200 --radians
    python so100_move.py ... --port /dev/ttyUSB0 --no-viewer --duration 10   # headless

Waypoint mode: run fixed poses (no port needed).
    python so100_move.py --menagerie ~/mujoco_menagerie --angles 0 -45 90 0 0 30
    python so100_move.py ... --angles 0 -45 90 0 0 30 --angles 45 -90 60 20 0 0
    python so100_move.py ... --angles 0 -45 90 0 0 30 --video out.mp4
"""
import argparse
import contextlib
import re
import threading
import time
from pathlib import Path

import mujoco
import numpy as np

SETTLE_VEL = 1e-3      # rad/s: "arrived" once the arm has stopped moving
MAX_SECONDS = 5.0      # give up on a waypoint after this much simulated time
VIEWER_HZ = 60         # live mode: window refresh / physics pacing


def load(menagerie: Path):
    xml = menagerie / "trs_so_arm100" / "scene.xml"
    model = mujoco.MjModel.from_xml_path(str(xml))
    return model, mujoco.MjData(model)


def joint_names(model):
    return [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)]


def clamp_to_limits(model, target, warn=True):
    lo, hi = model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1]
    clamped = np.clip(target, lo, hi)
    if warn:
        names = joint_names(model)
        for i in np.flatnonzero(clamped != target):
            print(f"  warning: {names[i]} target {target[i]:+.3f} rad clamped to {clamped[i]:+.3f}")
    return clamped


def joint_angles(model, data):
    # Each actuator drives one joint; read that joint's position.
    jids = model.actuator_trnid[:, 0]
    return data.qpos[model.jnt_qposadr[jids]].copy()


# --------------------------------------------------------------------------
# Serial input
# --------------------------------------------------------------------------
class AngleReader(threading.Thread):
    """Background thread: read lines from a serial port, keep the newest sample."""

    def __init__(self, port, baud, n_joints=6):
        super().__init__(daemon=True)
        import serial  # pyserial

        self._serial_exc = serial.SerialException
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.n = n_joints
        self._lock = threading.Lock()
        self._latest = None        # newest valid sample (raw units)
        self._seq = 0              # increments on every valid sample
        self.bad_lines = 0
        self.error = None
        self._halt = threading.Event()

    def run(self):
        while not self._halt.is_set():
            try:
                raw = self.ser.readline()
            except (self._serial_exc, OSError) as e:
                self.error = e
                return
            if not raw:
                continue
            try:
                parts = [p for p in re.split(r"[,\s;]+", raw.decode("ascii", "ignore").strip()) if p]
                vals = np.array([float(p) for p in parts])
                if vals.shape != (self.n,) or not np.all(np.isfinite(vals)):
                    raise ValueError
            except ValueError:
                self.bad_lines += 1    # partial line at startup, noise, wrong field count...
                continue
            with self._lock:
                self._latest, self._seq = vals, self._seq + 1

    def get(self):
        with self._lock:
            return self._seq, (None if self._latest is None else self._latest.copy())

    def close(self):
        self._halt.set()
        self.join(timeout=1)
        self.ser.close()


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------
def run_live(model, data, reader, radians, headless, duration):
    """Apply the newest serial sample to the arm, in real time, until closed."""
    import mujoco.viewer

    dt = model.opt.timestep
    steps_per_frame = max(1, round(1 / VIEWER_HZ / dt))
    frame_time = steps_per_frame * dt
    names = joint_names(model)
    lo, hi = model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1]

    # Hold the current pose until the first sample arrives.
    data.ctrl[:] = clamp_to_limits(model, joint_angles(model, data), warn=False)

    cm = contextlib.nullcontext() if headless else mujoco.viewer.launch_passive(model, data)
    last_seq, got_first = 0, False
    last_report = last_warn = t_start = time.perf_counter()
    rx_count = 0
    print(f"Listening on {reader.ser.port} @ {reader.ser.baudrate} baud "
          f"({'radians' if radians else 'degrees'}). Ctrl+C to quit.")

    with cm as viewer:
        try:
            next_frame = time.perf_counter()
            while viewer is None or viewer.is_running():
                now = time.perf_counter()
                if duration and now - t_start >= duration:
                    break
                if reader.error:
                    print(f"\nSerial port error: {reader.error}. Holding last pose.")
                    reader.error = None
                    break

                seq, sample = reader.get()
                if sample is not None and seq != last_seq:
                    rx_count += seq - last_seq
                    last_seq = seq
                    target = sample if radians else np.radians(sample)
                    clipped = np.clip(target, lo, hi)
                    if np.any(clipped != target) and now - last_warn > 1.0:
                        bad = [names[i] for i in np.flatnonzero(clipped != target)]
                        print(f"\n  warning: out of range, clamped: {', '.join(bad)}")
                        last_warn = now
                    data.ctrl[:] = clipped
                    if not got_first:
                        print("Receiving data.")
                        got_first = True

                for _ in range(steps_per_frame):
                    mujoco.mj_step(model, data)
                if viewer is not None:
                    viewer.sync()

                if now - last_report >= 1.0:
                    rate = rx_count / (now - last_report)
                    ang = np.degrees(joint_angles(model, data))
                    print(f"\r{rate:5.0f} Hz in | joints(deg): "
                          + " ".join(f"{a:+7.1f}" for a in ang)
                          + f" | bad lines: {reader.bad_lines}   ", end="", flush=True)
                    last_report, rx_count = now, 0

                # Pace physics to wall-clock time.
                next_frame += frame_time
                delay = next_frame - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_frame = time.perf_counter()   # fell behind; don't try to catch up
        except KeyboardInterrupt:
            pass
    print()
    report(model, data)


def move_to(model, data, target, on_step=None):
    """Set position targets and step physics until the arm settles (or times out)."""
    data.ctrl[:] = clamp_to_limits(model, target)
    steps = int(MAX_SECONDS / model.opt.timestep)
    for _ in range(steps):
        mujoco.mj_step(model, data)
        if on_step:
            on_step()
        # Settle on velocity, not position error: the actuators are plain
        # P-controllers, so gravity leaves a few degrees of steady-state sag
        # and the error never reaches zero.
        if data.time > 0.2 and np.max(np.abs(data.qvel)) < SETTLE_VEL:
            break


def report(model, data):
    ee = data.body("Fixed_Jaw").xpos
    angles = np.degrees(joint_angles(model, data))
    print("  joints (deg): " + ", ".join(f"{n}={a:+.1f}" for n, a in zip(joint_names(model), angles)))
    print(f"  Fixed_Jaw position (m): x={ee[0]:+.3f} y={ee[1]:+.3f} z={ee[2]:+.3f}")


def run_viewer(model, data, waypoints):
    import mujoco.viewer

    with mujoco.viewer.launch_passive(model, data) as viewer:
        last_sync = [0.0]

        def on_step():
            # Pace to real time and sync the window ~60 times a second.
            if data.time - last_sync[0] >= 1 / 60:
                last_sync[0] = data.time
                viewer.sync()
                time.sleep(1 / 60)

        for i, wp in enumerate(waypoints, 1):
            if not viewer.is_running():
                return
            print(f"Waypoint {i}: {np.degrees(wp).round(1)} deg")
            move_to(model, data, wp, on_step)
            report(model, data)
        while viewer.is_running():   # keep the window open at the end
            viewer.sync()
            time.sleep(0.05)


def run_video(model, data, waypoints, path, fps=30):
    import imageio.v2 as imageio

    renderer = mujoco.Renderer(model, height=480, width=640)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.lookat[:] = [0, -0.2, 0.1]
    cam.distance, cam.azimuth, cam.elevation = 0.9, 140, -25
    frames, next_t = [], 0.0

    def on_step():
        nonlocal next_t
        if data.time >= next_t:
            renderer.update_scene(data, camera=cam)
            frames.append(renderer.render())
            next_t += 1 / fps

    for i, wp in enumerate(waypoints, 1):
        print(f"Waypoint {i}: {np.degrees(wp).round(1)} deg")
        move_to(model, data, wp, on_step)
        report(model, data)
    imageio.mimsave(path, frames, fps=fps)
    print(f"Wrote {path} ({len(frames)} frames)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--menagerie", type=Path, required=True, help="path to mujoco_menagerie checkout")
    p.add_argument("--port", help="serial port to read angles from, e.g. /dev/ttyUSB0 or COM3 (live mode)")
    p.add_argument("--baud", type=int, default=115200, help="serial baud rate (default 115200)")
    p.add_argument("--no-viewer", action="store_true", help="live mode without a window (prints status only)")
    p.add_argument("--duration", type=float, help="live mode: stop after this many seconds")
    p.add_argument("--angles", type=float, nargs=6, action="append",
                   metavar=("ROT", "PITCH", "ELBOW", "WR_PITCH", "WR_ROLL", "JAW"),
                   help="6 joint angles; repeat the flag for multiple waypoints (no port needed)")
    p.add_argument("--radians", action="store_true", help="angles are radians (default: degrees)")
    p.add_argument("--video", type=str, help="waypoint mode: render to this mp4 instead of opening a window")
    args = p.parse_args()

    if bool(args.port) == bool(args.angles):
        p.error("give exactly one of --port (live) or --angles (waypoints)")

    model, data = load(args.menagerie)

    if args.port:
        reader = AngleReader(args.port, args.baud, model.nu)
        reader.start()
        try:
            run_live(model, data, reader, args.radians, args.no_viewer, args.duration)
        finally:
            reader.close()
    else:
        waypoints = [np.array(a) if args.radians else np.radians(a) for a in args.angles]
        if args.video:
            run_video(model, data, waypoints, args.video)
        else:
            run_viewer(model, data, waypoints)


if __name__ == "__main__":
    main()