#!/usr/bin/env python3
"""Drive the MuJoCo Menagerie SO-100 arm from joint angles, with a cube to pick up.

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

Pick demo: scripted grasp-and-lift of the default cube.
    python so100_move.py --menagerie ~/mujoco_menagerie --pick-demo
    python so100_move.py ... --pick-demo --video pick.mp4

The cube sits on the floor in front of the arm (--cube-pos X Y, --cube-size SIDE,
or --no-cube). In the viewer, press Backspace to reset the simulation.
"""
import argparse
import contextlib
import re
import socket
import threading
import time
from pathlib import Path

import mujoco
import numpy as np

SETTLE_VEL = 1e-3      # rad/s: "arrived" once the arm has stopped moving
MAX_SECONDS = 5.0      # give up on a waypoint after this much simulated time
MIN_HOLD = 0.3         # seconds to hold each waypoint after the ramp, at least
DEFAULT_RAMP = 1.0     # seconds to glide between waypoints
VIEWER_HZ = 60         # live mode: window refresh / physics pacing

# Cube: a 2.5 cm, 20 g box with high friction, 25 cm in front of the base.
# The pick demo was solved for exactly these values.
DEFAULT_CUBE_XY = (0.0, -0.25)
DEFAULT_CUBE_SIDE = 0.025
CUBE_MASS = 0.02
CUBE_FRICTION = (1.5, 0.005, 0.0001)

# Scripted grasp for the default cube: (joint angles in degrees, ramp seconds).
# These are the *commanded* angles. The actuators are plain P-controllers, so
# they include a small gravity offset, which is why e.g. Pitch is not a round number.
PICK_DEMO = [
    ([-0.3, -119.3, 130.5, 58.0, 90.3, 51.6], 3.0),   # above/behind the cube, jaw open
    ([-0.2,  -91.5, 134.5, 26.1, 90.2, 51.6], 1.5),   # slide jaws around the cube
    ([-0.2,  -91.5, 134.5, 26.1, 90.2, -9.9], 0.8),  # close the jaw
    ([-0.2, -108.2, 106.4, 71.0, 90.2, -9.9], 1.5),  # lift
]

PORT = 51234
HOST = '100.82.127.15'



def load(menagerie: Path, cube=None):
    """Load the SO-100 scene. cube = (x, y, side_m) adds a free-floating box, or None."""
    xml = menagerie / "trs_so_arm100" / "scene.xml"
    spec = mujoco.MjSpec.from_file(str(xml))
    if cube is not None:
        x, y, side = cube
        body = spec.worldbody.add_body(name="cube", pos=[x, y, side / 2])
        body.add_freejoint()
        body.add_geom(
            name="cube", type=mujoco.mjtGeom.mjGEOM_BOX, size=[side / 2] * 3,
            mass=CUBE_MASS, rgba=[0.9, 0.15, 0.1, 1], friction=list(CUBE_FRICTION),
            condim=4,   # adds torsional friction so the cube doesn't spin in the grip
        )
    model = spec.compile()
    return model, mujoco.MjData(model)


def has_cube(model):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cube") >= 0


def cube_pos(model, data):
    return data.body("cube").xpos.copy()


def cube_lifted(model, data):
    side = 2 * model.geom("cube").size[0]
    return cube_pos(model, data)[2] > side / 2 + 0.02


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

    def __init__(self, n_joints=6):
        super().__init__(daemon=True)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.sock.bind((HOST,PORT))
        self.sock.listen(5)
        print(f"server is listening on {HOST}:{PORT}...")
        self.n = n_joints
        self._lock = threading.Lock()
        self._latest = None
        self._seq = 0
        self.bad_lines = 0
        self.error = None
        self._halt = threading.Event()


    def run(self):
        self.sock.settimeout(1.0)  # so accept() can notice _halt
        while not self._halt.is_set():
            try:
                conn, addr = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break  # socket was closed

            print(f"Connected to {addr}")
            with conn:
                conn.settimeout(1.0)
                data_buffer = bytearray()

                while not self._halt.is_set():
                    try:
                        chunk = conn.recv(1024)
                    except socket.timeout:
                        continue
                    except OSError:
                        break

                    if not chunk:  # client disconnected
                        print(f"{addr} disconnected")
                        break

                    data_buffer.extend(chunk)

                    while b'\n' in data_buffer:
                        line, data_buffer = data_buffer.split(b'\n', 1)
                        message = line.decode('utf-8', errors='replace').rstrip('\r')

                        try:
                            parts = [p for p in re.split(r"[,\s;]+", message) if p]
                            vals = np.array([float(p) for p in parts])
                            if vals.shape != (self.n,) or not np.all(np.isfinite(vals)):
                                raise ValueError
                        except ValueError:
                            self.bad_lines += 1
                            continue

                        with self._lock:
                            self._latest, self._seq = vals, self._seq + 1

    def get(self):
        with self._lock:
            return self._seq, (None if self._latest is None else self._latest.copy())

    def close(self):
        self._halt.set()
        self.join(timeout=1)
        self.sock.close()


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
    print(f"Listening on {PORT}"
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
                    cube = ""
                    if has_cube(model):
                        cube = f" | cube z={cube_pos(model, data)[2] * 100:4.1f}cm" \
                               + (" LIFTED" if cube_lifted(model, data) else "")
                    print(f"\r{rate:5.0f} Hz in | joints(deg): "
                          + " ".join(f"{a:+7.1f}" for a in ang)
                          + f" | bad lines: {reader.bad_lines}{cube}   ", end="", flush=True)
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


def move_to(model, data, target, on_step=None, ramp=DEFAULT_RAMP):
    """Glide the position targets to `target`, then step until the arm settles."""
    goal = clamp_to_limits(model, target)
    start = data.ctrl.copy()
    dt = model.opt.timestep

    # Smoothstep ramp: abrupt setpoint jumps whip the arm around and can knock the cube.
    n_ramp = max(1, int(ramp / dt))
    for i in range(n_ramp):
        s = (i + 1) / n_ramp
        data.ctrl[:] = start + (goal - start) * (s * s * (3 - 2 * s))
        mujoco.mj_step(model, data)
        if on_step:
            on_step()

    # Then hold until still. Settle on velocity, not position error: the actuators
    # are plain P-controllers, so gravity leaves a few degrees of steady-state sag
    # and the error never reaches zero.
    data.ctrl[:] = goal
    for i in range(int(MAX_SECONDS / dt)):
        mujoco.mj_step(model, data)
        if on_step:
            on_step()
        if i * dt > MIN_HOLD and np.max(np.abs(data.qvel)) < SETTLE_VEL:
            break


def report(model, data):
    ee = data.body("Fixed_Jaw").xpos
    angles = np.degrees(joint_angles(model, data))
    print("  joints (deg): " + ", ".join(f"{n}={a:+.1f}" for n, a in zip(joint_names(model), angles)))
    print(f"  Fixed_Jaw position (m): x={ee[0]:+.3f} y={ee[1]:+.3f} z={ee[2]:+.3f}")
    if has_cube(model):
        c = cube_pos(model, data)
        state = "LIFTED" if cube_lifted(model, data) else "on the floor"
        print(f"  cube position (m): x={c[0]:+.3f} y={c[1]:+.3f} z={c[2]:+.3f}  [{state}]")


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

        for i, (wp, ramp) in enumerate(waypoints, 1):
            if not viewer.is_running():
                return
            print(f"Waypoint {i}: {np.degrees(wp).round(1)} deg")
            move_to(model, data, wp, on_step, ramp)
            report(model, data)
        while viewer.is_running():   # keep the window open at the end
            viewer.sync()
            time.sleep(0.05)


def run_video(model, data, waypoints, path, fps=30):
    import imageio.v2 as imageio

    renderer = mujoco.Renderer(model, height=480, width=640)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.lookat[:] = [0, -0.25, 0.08]
    cam.distance, cam.azimuth, cam.elevation = 0.8, 140, -25
    frames, next_t = [], 0.0

    def on_step():
        nonlocal next_t
        if data.time >= next_t:
            renderer.update_scene(data, camera=cam)
            frames.append(renderer.render())
            next_t += 1 / fps

    for i, (wp, ramp) in enumerate(waypoints, 1):
        print(f"Waypoint {i}: {np.degrees(wp).round(1)} deg")
        move_to(model, data, wp, on_step, ramp)
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
    p.add_argument("--ramp", type=float, default=DEFAULT_RAMP,
                   help=f"waypoint mode: seconds to glide between waypoints (default {DEFAULT_RAMP})")
    p.add_argument("--radians", action="store_true", help="angles are radians (default: degrees)")
    p.add_argument("--video", type=str, help="waypoint/pick mode: render to this mp4 instead of opening a window")
    p.add_argument("--pick-demo", action="store_true", help="run a scripted grasp-and-lift of the default cube")
    p.add_argument("--no-cube", action="store_true", help="leave the cube out of the scene")
    p.add_argument("--cube-pos", type=float, nargs=2, metavar=("X", "Y"), default=DEFAULT_CUBE_XY,
                   help="cube centre on the floor, metres (default: %g %g; base is at 0 0, arm reaches toward -Y)"
                        % DEFAULT_CUBE_XY)
    p.add_argument("--cube-size", type=float, default=DEFAULT_CUBE_SIDE,
                   help="cube side length in metres (default %g)" % DEFAULT_CUBE_SIDE)
    args = p.parse_args()

    if sum([bool(args.port), bool(args.angles), args.pick_demo]) != 1:
        p.error("give exactly one of --port (live), --angles (waypoints) or --pick-demo")

    cube = None
    if not args.no_cube:
        x, y = args.cube_pos
        cube = (x, y, args.cube_size)
        if args.pick_demo and (tuple(args.cube_pos) != DEFAULT_CUBE_XY or args.cube_size != DEFAULT_CUBE_SIDE):
            print("note: --pick-demo only works for the default cube; ignoring --cube-pos/--cube-size")
            cube = (*DEFAULT_CUBE_XY, DEFAULT_CUBE_SIDE)
    elif args.pick_demo:
        p.error("--pick-demo needs the cube; drop --no-cube")

    model, data = load(args.menagerie, cube)

    if args.port:
        reader = AngleReader()
        reader.start()
        try:
            run_live(model, data, reader, args.radians, args.no_viewer, args.duration)
        finally:
            reader.close()
        return

    if args.pick_demo:
        waypoints = [(np.radians(a), r) for a, r in PICK_DEMO]
    else:
        waypoints = [(np.array(a) if args.radians else np.radians(a), args.ramp) for a in args.angles]
    if args.video:
        run_video(model, data, waypoints, args.video)
    else:
        run_viewer(model, data, waypoints)


if __name__ == "__main__":
    main()