# Power Architecture

## Overview

Just1 uses a single 4S Graphene LiPo drone battery (14.8V nominal, 16.8V max, 1300mAh, 75C) as the sole power source for the entire robot. A single battery eliminates the need for a separate Pi power bank and a motor pack. The LiPo is extremely lightweight, heavily improving the robot's agility and TT motor performance. A BX100 buzzer MUST be plugged into the balance port during operation for low-voltage warning.

## Power Distribution Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  4S Graphene LiPo Battery (14.8V nominal, 16.8V max)       │
│  Requires external BX100 buzzer for low-voltage alarm!      │
└──────────────────┬──────────────────────────────────────────┘
                   │ XT60 (red + / black −) → master switch (see Step 1) → XT60 out → 1→2 splitter → loads
                   │
      ┌────────────┴────────────┐
      │                         │
      ▼                         ▼
┌───────────────┐     ┌──────────────────────────────────┐
│ DC-DC Buck    │     │  DC-DC Buck Converter            │
│ Converter     │     │  Input: up to 16.8V              │
│ (XL4016)      │     │  Output: 5V / 8A (40W)           │
│ Out: 6.0V/8A  │     │  (XL4016)                        │
└──────┬────────┘     └─────────────┬────────────────────┘
       │                            │ BuckVout (5V rail)
       │               ┌────────────┴──────────────────────────────┐
       ▼               │                                           │
┌───────────────┐      ▼                    ▼                      │
│  2× TB6612FNG │ ┌──────────────┐   ┌─────────────────┐           │
│  Motor Driver │ │ RelayCoil+   │   │ Esp32VIN        │           │
│               │ │ Pi5V path    │   │ (always on 5V)  │           │
│  VM: 6.0V     │ │ (switched)   │   └────────┬────────┘           │
│  (safe limits)│ └──────┬───────┘            │                    │
│               │        │    ESP32 GPIO      │                    │
│  4× Encoder   │        │    closes relay    │                    │
│  TT Motors    │        ▼                    │                    │
└───────────────┘ ┌──────────────┐◄───────────┘                    │
                  │ Pi5V_USB-C   │                                 │
                  │ via relay NO │                                 │
                  └──────────────┘                                 │
```

**5V topology:** **ESP32 VIN** and **relay module VCC** tie directly to **buck VOUT+**. Only the **Raspberry Pi 5V** path runs **through the relay contacts** (Pi off, ESP32 still powered). “Upstream of the relay” means **parallel to the Pi feed**, not “before the battery master switch.”

### How the Battery Connects to the System — Physical Wiring Guide

Your battery has two wires: **+ (red)** and **− (black)**. Here is exactly where each wire goes, step by step.

#### Step 1: Battery → XT60 → master switch → XT60 (your harness)

An **XT60** is always **two conductors**: **red = battery +**, **black = battery −** (same pin names on male and female).

Many RC-style harnesses use a **DPST** toggle: **both red and black** run through the switch. **OFF** disconnects the whole pack; **ON** connects both. That matches a battery XT60 on one side of the switch and a second XT60 on the load side — both polarities are switched together.

(Some builds switch **only** the red wire and leave black always tied to a ground bus. Your photos use **both** switched; that is fine and is often safer for storage.)

```
Battery ──XT60──► [ DPST: RED + BLACK both through switch ] ──XT60──► rest of robot
```

#### Step 2: After the switch — 1→2 Splitter → 5V Buck + 6V Buck

Plug the **load-side XT60** of the switch into a **1-to-2 parallel XT60 splitter** (or cut/splice thick wires directly). The two output pairs route the raw up to 16.8V battery voltage to your two buck converters:

| Branch | Red → | Black → |
| --- | --- | --- |
| 1 | Logic Buck (XL4016) **VIN+** | Logic Buck **VIN−** |
| 2 | Motor Buck (XL4016) **VIN+** | Motor Buck **VIN−** |

*Note: The Motor Buck's output (set to exactly 6V) then splices to feed the `VM` pins of both TB6612FNG drivers so they receive a safe 6V limit. Do not connect the battery directly to the TB6612FNG `VM` pins or they will explode (15V limit).*

**Yes — every branch needs both red and black.** DC only flows in a loop; **VM/VIN+ without GND/VIN−** (or the reverse) does nothing useful and can damage something if signals are connected without a common return.

The three blacks from the splitter are **electrically the same node** (battery negative after the switch). They still need to meet the **rest** of the system ground (ESP32, Pi, PCA9685, buck **VOUT−**, etc.) at one **common ground** so logic signals share a reference — use a ground bus, star point, or the splitter blacks as part of that bus.

#### Step 3: COMMON GND BUS — every device connects its ground here

The **three blacks** from the splitter (to TB6612 ×2 and XL4016 **VIN−**) are already on battery **−** (via the switch, if DPST). Tie those points together with **all other grounds** below (same metal/node):

From the common ground bus, run **black wires** to every device's GND:

| Wire | From | To | Terminal Name |
|------|------|----|---------------|
| Black wire 1 | GND bus | TB6612FNG chip #1 | **GND** |
| Black wire 2 | GND bus | TB6612FNG chip #2 | **GND** |
| Black wire 3 | GND bus | XL4016 Buck Converter | **VIN−** (or **IN−**) |
| Black wire 4 | GND bus | ESP32 DevKit | **GND** pin |
| Black wire 5 | GND bus | Relay module | **GND** |
| Black wire 6 | GND bus | Raspberry Pi 5 | **GND** pin (or USB-C ground) |
| Black wire 7 | GND bus | PCA9685 | **GND** |

> **Why is the shared ground critical?** Every signal wire (I2C, UART, GPIO, PWM) is measured as a voltage *relative to ground*. If two devices don't share the same ground, a "HIGH" signal from one device could look like noise to another. Worse, current can flow through data lines trying to find a ground path — this can damage GPIO pins.

#### Step 4: 5V rail from the Buck Converter

The XL4016 buck converter has output terminals: **VOUT+** and **VOUT−**. Set the output to **5.0V** using the adjustment potentiometer (measure with a multimeter before connecting anything!). 

From the buck converter's **VOUT+** (5V), run red wires to:

| Wire | From | To | Terminal Name | Notes |
|------|------|----|---------------|-------|
| Red wire 4 | VOUT+ | ESP32 DevKit | **VIN** pin | ESP32's onboard regulator converts 5V → 3.3V |
| Red wire 5 | VOUT+ | Relay module | **VCC** | Powers the relay coil |
| Red wire 6 | VOUT+ → through relay → | Pi 5 | **USB-C 5V** (or GPIO 5V) | Only powered when ESP32 closes the relay. Use 18AWG wire to minimise contact-resistance voltage drop (mechanical relay contacts can drop ~0.2–0.3V under 5A load). |
| Red wire 7 | VOUT+ | PCA9685 | **V+** only | Servo motor power rail (up to 1.4A stall for 2× SG90) |
| Red wire 8 | ESP32 3.3V out | PCA9685 | **VCC** | Logic power — MUST be 3.3V, NOT 5V. The PCA9685 has 10 kΩ I2C pull-ups tied to VCC; if VCC = 5V, SDA/SCL are pulled to 5V and will over-voltage the ESP32 GPIO (3.3V max), causing long-term damage. |

The buck converter's **VOUT−** connects to the same **common ground bus**.

#### Complete Physical Wiring Diagram

```
                                                    │
                                              VOUT+ (5V) ──► ESP32 / relay / PCA9685 / Pi (via relay)

(−) BLACK ─XT60─► both legs ON/OFF ──XT60──►  ├── black → TB6612 #1 GND
             (same switch)                   ├── black → TB6612 #2 GND
                                             └── black → XL4016 VIN−
                                                    │
                              COMMON GND ◄──── VOUT− + ESP32 GND + Pi GND + relay GND + PCA9685 GND
```

> **Summary:** After the switch you have one **XT60 pair** (red + black). The **1→2 splitter** routes battery power to two buck converters. The 5V logic buck powers the compute string. The 6V motor buck feeds purely the VM pins of the dual TB6612FNG drivers. All blacks meet at a **common ground**.

## Rail Summary

| Rail | Voltage | Source | Powers |
| --- | --- | --- | --- |
| Main bus | 14.8V (16.8V max) | 4S Graphene LiPo | 5V Logic Buck input, 6V Motor Buck input |
| Motor rail | 6.0V | 6V Motor Buck → TB6612FNG **VM** | 4× TT encoder motors (Full 0-100% PWM safe) |
| 5V logic rail | 5V / up to 8A | High-current DC-DC Buck (XL4016) | ESP32 VIN (via onboard LDO), Relay coil VCC, Pi 5 (via relay), PCA9685 **V+** (servo motor power only) |
| 3.3V | 3.3V | ESP32 onboard AMS1117 LDO (from 5V VIN) | ESP32 logic, PCA9685 **VCC** (I2C logic power — avoids 5V pull-ups on ESP32 I2C bus), pan/tilt servo signal lines |

## Key Design Decisions

**Why 4S Graphene LiPo?**
At ~150g, a drone battery is massively lighter than standard Li-Ion or LiFePO4 robot packs. TT motors and mecanum wheels perform notoriously poorly under heavy payloads; dropping 600g out of the chassis yields a much faster, agile robot that can slide longitudinally without stalling. 

**Why power motors from a dedicated 6V buck?**
Because the drone battery reaches 16.8V fully charged, it exceeds the TB6612FNG motor driver's absolute maximum rating of 15V. Pumping 16.8V directly into the motor drivers will fry them. By using a second high-current XL4016 buck converter (8A) to cap the motor supply (VM) at exactly 6.0V, we protect the driver chip *and* allow the Python code to safely output a full 100% PWM duty cycle curve to the TT motors (which are rated for 6V). We strictly use an 8A XL4016 rather than a 3A LM2596 because 4 motors can generate a combined 5.6A+ load during simultaneous stalls; an LM2596 would collapse or overheat during the stall window.

Optional **INA219/INA226** (I2C) high-side or low-side shunt sensing on the motor path (see BOM) can back up encoder-based stall cutout if an encoder cable fails.

**Buck Converter and Servo Safety:**
The Pi 5 alone can draw up to 5A. Therefore, a high-current buck converter like the XL4016 (rated up to 8A) is strictly required — do not use an LM2596(HV) as it will overheat. The pan/tilt SG90 servos are powered through a PCA9685 servo driver: the PCA9685 has a dedicated **V+** servo power pin connected to the 5V rail (for motor current), and a separate **VCC** logic pin connected to the **ESP32 3.3V** output. This is critical: the PCA9685 has 10 kΩ I2C pull-up resistors tied to VCC. If VCC were 5V, the SDA/SCL lines would be pulled to 5V, over-voltaging the ESP32's 3.3V-tolerant I2C GPIO pins and causing hardware damage over time. At 3.3V VCC, the PCA9685 logic still functions correctly and the I2C bus stays safely within the ESP32's input voltage range.

**ESP32 standby behavior and Power Switching:**
The ESP32 **VIN** is fed from **buck VOUT+** on the **same** 5V bus as the relay coil — **not** through the relay’s switched path to the Pi — so the ESP32 stays alive when the Pi is off. (Do not confuse this with the **battery master** DPST switch, which removes all loads.) The ESP32 draws ~10μA in deep-sleep. On wake (BLE, RTC, or button), it drives the relay so **only** the Pi 5V feed is energized. **Crucial Note:** A high-side switch or relay on the **Pi 5V path** preserves a **shared system ground**. A low-side N-channel cut on Pi “ground” would break that reference and risks current through data lines.

**LiPo Protection (No BMS!):**
Drone LiPos **DO NOT** have an internal BMS. If you leave the robot on, it will drain the battery to 0V and cause a chemical fire hazard upon recharging. You must plug a BX100 low-voltage buzzer into the white balance port on the battery to screech at you when any cell hits 3.5V so you can immediately power off the robot.

---

## Battery Specifications

| Property | Value |
| --- | --- |
| Chemistry | Graphene LiPo |
| Configuration | 4S (4 cell series) |
| Nominal voltage | 14.8V |
| Full charge voltage | 16.8V |
| Absolute minimum limit | ~12.8V (3.2V/cell) |
| Capacity | 1300mAh (19.2Wh) |
| Discharge rating | 75C |
| Weight | ~150g |

> **Charger:** Use a standard RC **LiPo balance charger**. Ensure the mode is set to **LiPo (4.2V/cell)**, not LiFePO4!

---

## Power Budget Estimate

| Consumer | Voltage | Peak Current | Average Power |
| --- | --- | --- | --- |
| Raspberry Pi 5 (under load) | 5V | 5.0A | ~15.0W |
| 2× SG90 servos | 5V | 1.4A | ~2.0W |
| ESP32 + Aux (active) | 5V / 3.3V | 0.3A | ~1.5W |
| 4× TT motors (running loaded) | 6V | ~2.0A | ~12.0W |
| **System total** | — | — | **~30.5W** |

With an average draw of ~30W, the 19.2Wh drone battery will yield a runtime of **~35-45 minutes**. Keep the low voltage alarm loud!

The XL4016 buck converter is rated 8A — the 5V rail peak of ~6.7A is within spec with 1.3A headroom. ✅
