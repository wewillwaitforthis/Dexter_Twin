#ps2 controller
import pygame

CLAW_SPEED = 60
XYZ_SPEED = 0.3

def dz(v):
    #deadzone                            
    return v if abs(v) > 0.12 else 0.0

def init():
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No controller detected")
        quit()
    else:
        controller = pygame.joystick.Joystick(0)
        print("Controller plugged into port 0 and operable")
        return controller
        
def movement(controller, dt):
    pygame.event.pump()
    dxyz = (dz(controller.get_axis(0)) * XYZ_SPEED * dt,
            dz(-controller.get_axis(1)) * XYZ_SPEED * dt,
            dz(-controller.get_axis(3)) * XYZ_SPEED * dt)
    droll = (controller.get_button(5) - controller.get_button(4)) * CLAW_SPEED * dt
    left_trigger = (controller.get_axis(4) + 1) / 2
    right_trigger = (controller.get_axis(5) + 1) / 2
    dclaw = (left_trigger - right_trigger) * CLAW_SPEED * dt
    return dxyz, droll, dclaw