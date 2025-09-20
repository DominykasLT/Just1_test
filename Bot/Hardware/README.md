# Just1 Hardware

This folder contains hardware documentation and files for the Just1 robot.

## Bill of Materials
See `Bill_of_material.md` for complete parts list and pricing. Total cost is around $250.

**Key Components:**
- Raspberry Pi 4 (8GB) - Control unit
- 4x Mecanum wheels with TT motors - Omnidirectional movement
- 2x L298N motor drivers - Motor control
- LD19 Lidar - 2D scanning for navigation
- MPU6050 IMU - Orientation sensing
- Camera Module 3 - Optional vision sensor
- Power bank (5V 3A) - Pi power supply
- 6x AA battery holder - Motor power (9V)
The 6x AA battery holder can eventually be replaced with a rechargeable battery pack or by connecting the motors directly to the power bank using an appropriate power adapter.

**Additional parts:** Jumper wires, screws, hex pylons, on/off switch, and basic tools.

## 3D Models
- **Assembly**: `CAD/Just1Assembly.STEP` - Complete robot model
- **Print Files**: `CAD/ToPrint/` - STL files for 3D printing the different parts.

## Wiring Schematics
- `WiringMotorDrivers.png` - Motor driver connections
- `WiringPower.png` - Power distribution diagram


