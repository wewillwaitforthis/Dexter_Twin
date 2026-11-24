import numpy as np
import quest.quest_server as quest_server

ROLL_SPEED = 60
CLAW_SPEED = 60
SCALE = 1.0
prev_pos = None                  

def change_axis(p):
    # xr system x: right y:up z:towards user 
    # mujoco x:forward y:left z:up
    return np.array([-p[0], p[2], p[1]])

def init():
    quest_server.start()
    return quest_server.latest

def movement(src, dt):
    global prev_pos
    controller = src.get("right")
    if not controller:
        prev_pos = None
        return (0, 0, 0), 0.0, 0.0, 0.0

    dxyz = (0.0, 0.0, 0.0)
    if controller["grip"]:
        pos = change_axis(controller["pos"])
        if prev_pos is not None:
            dxyz = tuple(SCALE * (pos - prev_pos))
        prev_pos = pos
    else:
        prev_pos = None

    droll = controller.get("stick_x", 0.0) * ROLL_SPEED * dt
    dclaw = (controller.get("a", 0) - controller.get("b", 0)) * CLAW_SPEED * dt
    #dummy dpitch
    dpitch = 0
    return dxyz, droll, dclaw, dpitch