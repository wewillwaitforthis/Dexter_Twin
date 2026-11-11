#!/usr/bin/env python3
"""
Dextertwin: XYZ target + URDF  ->  SO100 motor rotation angles.

Pipeline
  1. Read the URDF and build the joint chain from the base link to the tool
     point ("tcp"). Each joint contributes:  T_origin (fixed offset from the
     URDF <origin>)  x  Rot(axis, q) (rotation about the URDF <axis>).
  2. Forward kinematics (FK): multiply those transforms -> where the tool
     point is for a given set of joint angles q.
  3. Inverse kinematics (IK): we want the q that puts the tool point at the
     target (x, y, z). There is no simple closed form for a general arm, so
     we solve it numerically with damped least squares (DLS):
         error  e  = target - FK(q)                 (3-vector, meters)
         Jacobian J = d FK / d q                    (3 x n)
         step  dq = J^T (J J^T + lambda^2 I)^-1 e   (small, stable step)
         q <- clamp(q + dq, joint limits)           repeat until |e| < 0.5 mm
  4. Convert joint angles to motor units: degrees and Feetech STS3215
     servo steps (4096 steps per revolution, 2048 = joint zero).

Only numpy is required.

Usage
  python so100_ik.py so100_tcp.urdf X Y Z            # meters, in base frame
  python so100_ik.py so100_tcp.urdf 0.0 -0.25 0.10
  python so100_ik.py so100_tcp.urdf 0.0 -0.25 0.10 --pitch -90
      (--pitch also asks the gripper to point at that angle, e.g. -90 = straight down)
"""
import argparse
import math
import sys
import xml.etree.ElementTree as ET

import numpy as np

# Joints the IK is allowed to move to reach a position. wrist_roll only spins
# the gripper and the gripper joint opens/closes the jaw, so they stay fixed.
IK_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex"]
STEPS_PER_REV = 4096
STEP_CENTER = 2048

# The MuJoCo Menagerie SO-100 model (trs_so_arm100) uses the same meshes and
# joint axes as this URDF, but some joints have a different "zero" pose.
# menagerie_angle = urdf_angle + offset   (checked to within 0.01 mm on 500 poses)
MENAGERIE_ORDER = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
MENAGERIE_NAMES = ["Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw"]
MENAGERIE_OFFSET = [0.0, -1.8 - math.pi / 2, math.pi, math.pi / 2 - 1.0, 0.0, 0.0]


def to_menagerie_deg(q):
    """URDF joint angles (rad dict) -> 6 Menagerie angles in degrees, in actuator order."""
    return [math.degrees(q.get(n, 0.0) + o) for n, o in zip(MENAGERIE_ORDER, MENAGERIE_OFFSET)]


# ----------------------------------------------------------------- URDF -> chain
def rpy_to_matrix(r, p, y):
    """URDF convention: fixed-axis roll (X), pitch (Y), yaw (Z) -> R = Rz Ry Rx."""
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ])


def axis_angle(axis, q):
    """Rodrigues' formula: rotation of q radians about a unit axis."""
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * K @ K


def load_chain(urdf_path, tip="tcp"):
    """Return the list of joints from the root link to `tip`, in order."""
    root = ET.parse(urdf_path).getroot()
    by_child = {}
    for j in root.findall("joint"):
        o = j.find("origin")
        xyz = [float(v) for v in (o.get("xyz", "0 0 0") if o is not None else "0 0 0").split()]
        rpy = [float(v) for v in (o.get("rpy", "0 0 0") if o is not None else "0 0 0").split()]
        T = np.eye(4)
        T[:3, :3] = rpy_to_matrix(*rpy)
        T[:3, 3] = xyz
        ax = j.find("axis")
        lim = j.find("limit")
        by_child[j.find("child").get("link")] = {
            "name": j.get("name"),
            "type": j.get("type"),
            "parent": j.find("parent").get("link"),
            "origin": T,
            "axis": [float(v) for v in ax.get("xyz").split()] if ax is not None else [1, 0, 0],
            "lower": float(lim.get("lower")) if lim is not None else -math.pi,
            "upper": float(lim.get("upper")) if lim is not None else math.pi,
        }
    chain, link = [], tip
    while link in by_child:
        chain.append(by_child[link])
        link = by_child[link]["parent"]
    if not chain:
        sys.exit(f"Link '{tip}' not found in {urdf_path}")
    return chain[::-1]


# ------------------------------------------------------------ forward kinematics
def fk(chain, q):
    """q: dict joint name -> angle (rad). Returns 4x4 tool pose and joint frames."""
    T = np.eye(4)
    frames = []  # (joint name, joint origin in base frame, joint axis in base frame)
    for j in chain:
        T = T @ j["origin"]
        if j["type"] in ("revolute", "continuous"):
            frames.append((j["name"], T[:3, 3].copy(), T[:3, :3] @ np.asarray(j["axis"], float)))
            R = np.eye(4)
            R[:3, :3] = axis_angle(j["axis"], q.get(j["name"], 0.0))
            T = T @ R
    return T, frames


def tool_pitch(T):
    """Angle of the gripper's pointing direction above horizontal (deg). -90 = down."""
    d = T[:3, :3] @ np.array([0.0, -1.0, 0.0])  # tcp is along -Y of the gripper frame
    return math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))


# ------------------------------------------------------------ inverse kinematics
def ik(chain, target, q_init=None, pitch_deg=None, iters=300, tol=5e-4, damping=0.02, seeds=30):
    joints = {j["name"]: j for j in chain}
    names = [n for n in IK_JOINTS if n in joints]
    lo = np.array([joints[n]["lower"] for n in names])
    hi = np.array([joints[n]["upper"] for n in names])
    q_fixed = dict(q_init or {})
    rng = np.random.default_rng(0)

    def solve(q0):
        q = np.clip(q0, lo, hi)
        for _ in range(iters):
            qd = {**q_fixed, **dict(zip(names, q))}
            T, frames = fk(chain, qd)
            p = T[:3, 3]
            e = np.asarray(target) - p
            J = np.zeros((3, len(names)))
            for name, o, a in frames:  # revolute joint: dp/dq = axis x (p - origin)
                if name in names:
                    J[:, names.index(name)] = np.cross(a, p - o)
            if pitch_deg is not None:  # add pitch as a 4th, softer task row
                h = 1e-5
                row = np.zeros(len(names))
                for k in range(len(names)):
                    q2 = q.copy(); q2[k] += h
                    row[k] = (tool_pitch(fk(chain, {**q_fixed, **dict(zip(names, q2))})[0])
                              - tool_pitch(T)) / h
                w = 0.002  # 1 degree of pitch error weighs like 2 mm of position error
                J = np.vstack([J, w * row])
                e = np.append(e, w * (pitch_deg - tool_pitch(T)))
            if np.linalg.norm(e[:3]) < tol and (pitch_deg is None or abs(e[3] / 0.002) < 1.0):
                return q, np.linalg.norm(e[:3]), True
            dq = J.T @ np.linalg.solve(J @ J.T + damping ** 2 * np.eye(len(e)), e)
            q = np.clip(q + np.clip(dq, -0.2, 0.2), lo, hi)
        T, _ = fk(chain, {**q_fixed, **dict(zip(names, q))})
        return q, np.linalg.norm(np.asarray(target) - T[:3, 3]), False

    # An arm can usually reach a point in several ways (elbow up / down...).
    # Try several starting guesses and keep the solution that needs the least
    # motor movement from the start pose, so the arm doesn't flip around.
    start = np.array([q_fixed.get(n, (l + h) / 2) for n, l, h in zip(names, lo, hi)])
    solutions, best = [], None
    for k in range(seeds):
        q0 = start if k == 0 else rng.uniform(lo, hi)
        q, err, ok = solve(q0)
        if ok:
            solutions.append(q)
            if len(solutions) >= 6:
                break
        elif best is None or err < best[1]:
            best = (q, err)
    if solutions:
        q = min(solutions, key=lambda s: np.linalg.norm(s - start))
        T, _ = fk(chain, {**q_fixed, **dict(zip(names, q))})
        return {**q_fixed, **dict(zip(names, q))}, np.linalg.norm(np.asarray(target) - T[:3, 3]), True
    return {**q_fixed, **dict(zip(names, best[0]))}, best[1], False


def to_steps(q_rad):
    return int(round(STEP_CENTER + q_rad * STEPS_PER_REV / (2 * math.pi)))


# --------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urdf")
    ap.add_argument("x", type=float)
    ap.add_argument("y", type=float)
    ap.add_argument("z", type=float)
    ap.add_argument("--pitch", type=float, default=None, help="desired gripper pitch in degrees (-90 = down)")
    ap.add_argument("--tip", default="tcp", help="end-effector link name (default: tcp)")
    args = ap.parse_args()

    chain = load_chain(args.urdf, args.tip)
    target = np.array([args.x, args.y, args.z])
    q, err, ok = ik(chain, target, q_init={"shoulder_pan": 0.0, "shoulder_lift": 1.5,
                                         "elbow_flex": -1.5, "wrist_flex": 0.0,
                                         "wrist_roll": 0.0, "gripper": 0.0},
                    pitch_deg=args.pitch)
    T, _ = fk(chain, q)

    print(f"Target XYZ (m):   {target.round(4).tolist()}")
    print(f"Reached XYZ (m):  {T[:3, 3].round(4).tolist()}   error = {err * 1000:.2f} mm"
          f"   gripper pitch = {tool_pitch(T):.1f} deg")
    print("Status:", "SOLVED" if ok else "UNREACHABLE (closest pose shown)")
    print()
    print(f"{'joint / motor':<15}{'rad':>9}{'deg':>9}{'servo steps':>13}")
    for i, j in enumerate([c for c in chain if c["type"] == "revolute"], start=1):
        v = q.get(j["name"], 0.0)
        print(f"{i}. {j['name']:<12}{v:>9.4f}{math.degrees(v):>9.2f}{to_steps(v):>13d}")
    if ok:
        m = to_menagerie_deg(q)
        print()
        print("MuJoCo Menagerie (so100_move.py), degrees:")
        print("  " + ", ".join(f"{n}={v:.1f}" for n, v in zip(MENAGERIE_NAMES, m)))
        print("  --angles " + " ".join(f"{v:.1f}" for v in m))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
