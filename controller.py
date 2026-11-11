import pygame

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller detected")
    quit()
else:
    controller = pygame.joystick.Joystick(0)
    print("Controller plugged into port 0 and operable")


SPEED = 0.5
DEADZONE = 0.1
clock = pygame.time.Clock()

def main():

    x, y, z = 0.0, 0.0, 0.0
    claw = 90.0 

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        if(abs(controller.get_axis(0))>0.7):#x
            x += deadzone(controller.get_axis(0)) * SPEED
            print(x)
        if(abs(controller.get_axis(1))>0.7): #y
            y += deadzone(-controller.get_axis(1)) * SPEED
            print(y)
        if(abs(controller.get_axis(3))>0.7): #z
            z += deadzone(-controller.get_axis(3)) * SPEED
            print(z)
        if(controller.get_axis(4)>0.7):#open left
            if(claw < 180):
                claw += deadzone(controller.get_axis(4)) * SPEED
                print(claw)
        if(controller.get_axis(5)>0.7):#close right
            if(claw > 0):
                claw += deadzone(-controller.get_axis(5)) * SPEED
                print(claw)

def deadzone(value):
    if(abs(value) > 0.15):
        return value
    else:
        return 0

if __name__ == "__main__":
    main()
    pygame.quit()