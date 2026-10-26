# Dexter_Twin
> CS 461 Senior Software Engineering Project, Fall 2026
> **Status:** Early development. Expect things to change.

## Overview

A VR/AR app that uses AI motion tracking to make a robot hand mimic the user's hand movements in real time, from the shoulder down to the fingers.

We're starting with the basics: getting a robotic arm to move in simulation and controlling it with an Xbox controller. VR joint tracking comes later.

## Goals

**Current phase**
- [ ] Load a robot arm model (URDF) into simulation
- [ ] Move the arm's joints in Isaac Sim
- [ ] Control the arm with an Xbox controller

**Long-term**
- [ ] Track shoulder-to-finger joint movement from VR input
- [ ] Map tracked human joints onto the robot arm

## Team

| Name | Role |
| --- | --- |
| Nour | Robot model (URDF) and basic robotic movements |
| Jack | Simulation setup (Isaac Sim) |
| Katarina | Xbox controller input for the robotic arm |

We meet with our industry partner weekly and with our TA every two weeks.

## Tech Stack

- **Simulation:** NVIDIA Isaac Sim
- **Robot model:** URDF
- **Language:** Python
- **Input:** Xbox controller
- **Later:** VR tracking (TBD)

## Repository Structure

```
.
├── README.md
├── docs/
│   └── rfcs/          # Design decisions (RFCs)
├── urdf/              # Robot arm model files
├── sim/               # Isaac Sim scripts and scenes
└── controller/        # Xbox controller input code
```

_Update this as folders are added._

## Getting Started

### Requirements
- NVIDIA GPU that meets Isaac Sim's requirements
- Isaac Sim version: `[fill in]`
- Python version: `[fill in]`
- Xbox controller (wired or Bluetooth)

### Setup
```bash
git clone [repo URL]
cd [repo folder]
# [install steps go here]
```

### Running
```bash
# [command to launch the simulation]
# [command to start controller input]
```

## Design Decisions

Major, hard-to-reverse decisions are written up as RFCs in [`docs/rfcs/`](docs/rfcs/).

## Contributing

- Work on a branch, not directly on `main`
- Open a pull request and get at least one teammate's review before merging
- Write clear commit messages

## License

[TBD. Check with our partner before choosing one.]
