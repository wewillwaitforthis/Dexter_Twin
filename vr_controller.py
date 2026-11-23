import numpy as np
import quest_server            # the WebSocket server from earlier

ROLL_SPEED = 60                # deg/s
CLAW_SPEED = 60
SCALE = 1.0
_last = None                   # previous controller position while the grip is held

def xr_to_mj(p):
    return np.array([-p[2], -p[0], p[1]])

def init():
    quest_server.start()
    return quest_server.latest  # "src" is just the shared dict

def movement(src, dt):
    global _last
    h = src.get("right")
    if not h:
        return (0, 0, 0), 0.0, 0.0

    dxyz = (0.0, 0.0, 0.0)
    if h["grip"]:
        p = xr_to_mj(h["pos"])
        if _last is not None:
            dxyz = tuple(SCALE * (p - _last))
        _last = p
    else:
        _last = None            # clutch released: re-anchor next time

    droll = h.get("stick_x", 0.0) * ROLL_SPEED * dt
    dclaw = (h.get("a", 0) - h.get("b", 0)) * CLAW_SPEED * dt
    return dxyz, droll, dclaw