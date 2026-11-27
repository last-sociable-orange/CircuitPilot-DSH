# Battery Charger IC Design Checklist

## 1. Battery Chemistry Verification

- [ ] Confirm charger IC supports the target battery chemistry (Li-Ion, LiFePO4, Lead-Acid, NiMH, etc.)
- [ ] Verify charge voltage (float voltage) per cell is set correctly and within the battery's specification
- [ ] Check that charge current (fast charge, pre-charge, termination) is configured appropriately for the battery capacity and manufacturer recommendations
- [ ] Confirm pre-charge (trickle) threshold voltage for deeply discharged cells is appropriate
- [ ] Verify termination method (current threshold, timer, ΔV detection) matches the battery chemistry

## 2. Input Supply Verification

- [ ] Verify input voltage range covers all expected sources (USB, adapter, etc.) and includes overvoltage protection threshold
- [ ] Confirm input current limit is configured correctly for the source capability (USB 100/500 mA, BC 1.2, USB-C PD, or adapter rating)
- [ ] Check undervoltage lockout (UVLO) threshold prevents charging from a depleted input source
- [ ] Verify input reverse polarity protection is present (internal or external)

## 3. Charge Profile Verification

- [ ] Verify the charge profile (pre-conditioning → CC → CV → termination → recharge) matches the battery manufacturer's requirements
- [ ] Confirm constant current (CC) value and constant voltage (CV) threshold are set correctly
- [ ] Check recharge threshold — verify charging resumes at the appropriate battery voltage level
- [ ] Verify charge current accuracy and voltage accuracy meet battery safety requirements

### Safety Timer (if applicable)
- [ ] Confirm safety timer is enabled and its duration is appropriate for the battery capacity and charge rate
- [ ] Verify safety timer behavior on timeout (stop charging, fault indication)

## 4. Battery Protection

- [ ] Verify overvoltage protection (OVP) threshold prevents exceeding the battery's absolute maximum voltage
- [ ] Confirm overcurrent protection is set above the maximum charge current but below the battery's safe limit
- [ ] Check thermal regulation and thermal shutdown thresholds — verify the charger reduces current or stops at safe temperatures
- [ ] Verify reverse battery protection (if the battery can be inserted backwards)
- [ ] Confirm battery temperature monitoring (NTC thermistor) is connected and configured:
  - Verify NTC resistor value and B-coefficient match the charger IC's requirements
  - Confirm temperature suspend/resume thresholds are appropriate for the battery chemistry
- [ ] Check battery absent detection is functional

## 5. Power Path Management

- [ ] Confirm power path topology (no power path, linear, switching, NVDC) is appropriate for the system requirements
- [ ] Verify instant-on capability — system powers up from input even with a dead or absent battery
- [ ] Check that system load has priority over battery charging (charging current is reduced if input current limit is exceeded)
- [ ] For NVDC architecture: verify system voltage regulation during battery-powered and input-powered modes
- [ ] Confirm ideal diode or FET OR-ing is present to isolate battery when input is removed

## 6. Status / Indicator Verification

- [ ] Verify charge status, power-good, and fault indicator pin connections (open-drain with appropriate pull-up resistors)
- [ ] Confirm indicator behavior (state during charging, done, fault, no battery) is documented and used correctly

## 7. Configuration Interface Verification

- [ ] **Standalone (hardware):** verify that programming resistors for charge current, float voltage, and timer are within datasheet tolerance
- [ ] **I2C/SMBus:** confirm I2C voltage level compatibility with host MCU and that register settings match the required charge parameters
- [ ] Verify that default / power-up settings (for I2C-controlled chargers before initialization) are safe for the battery

## 8. Thermal Verification

- [ ] Verify power dissipation at worst-case operating conditions (V_in_max, V_bat_min, I_charge_max) does not exceed the IC package limit
- [ ] Confirm junction temperature stays within the IC's rated range at maximum ambient temperature
- [ ] For linear chargers: verify the headroom (V_in − V_bat) × I_charge is within the package's dissipation capability — if not, confirm a switching charger or lower current is used
- [ ] For switching chargers: verify the design uses appropriate external components (inductor, capacitors) rated for the charge current

## 9. Connector and Wiring

- [ ] Verify battery connector is keyed to prevent reverse connection and rated for the charge current with margin
- [ ] Confirm wire gauge is adequate for the charge current
- [ ] If separate sense wires (Kelvin connection) are used for accurate voltage sensing, verify the routing is correct
- [ ] Check that protection diode or built-in reverse protection is present on the battery connection

## 10. USB Compliance (if USB-powered)

- [ ] Verify USB suspend mode current requirement (< 2.5 mA suspended) is met
- [ ] Confirm USB BC 1.2 detection is correctly implemented if higher current (> 100 mA) is drawn before enumeration
- [ ] Check inrush current at plug-in does not exceed USB specifications

## 11. USB-C / USB PD (if USB-C powered)

### Without Dedicated PD Controller (Resistor-Controlled)
- [ ] Verify the USB-C CC pull-down resistors (Rd) are the correct value for the intended sink current:
  - 5.1 kΩ (Rd) on both CC1 and CC2 = default USB power (500 mA USB 2.0, 900 mA USB 3.0)
  - 10 kΩ (Rd) on both CC1 and CC2 = 1.5 A @ 5V (USB Type-C Current)
  - 22 kΩ (Rd) on both CC1 and CC2 = 3 A @ 5V (USB Type-C Current)
- [ ] Confirm the charger IC's input current limit is set to match the advertised current via the CC resistors
- [ ] Verify CC1 and CC2 lines are connected to the USB-C connector with ESD protection (low-capacitance TVS)
- [ ] Check VBUS voltage rating — confirm the charger IC can tolerate 5V nominal (up to 20V with PD) if the system may later be upgraded to PD

### With Dedicated PD Controller
- [ ] Verify the PD controller's I2C/SPI voltage level and address are compatible with the host MCU
- [ ] Confirm the PD controller's sink PDOs (Power Data Objects) are configured to request the correct voltage (5V, 9V, 15V, 20V) and current from the source
- [ ] Verify the PD controller's VBUS voltage rating — confirm the charger IC and all downstream components can tolerate the maximum negotiated voltage (up to 20V for USB PD 3.0)
- [ ] Check that the charger IC's overvoltage protection (OVP) threshold is set above the negotiated VBUS voltage with margin
- [ ] If the system supports multiple PD voltages: verify the charger IC and downstream converter can operate across the full negotiated voltage range
- [ ] Confirm the PD controller's CC pins are connected to the USB-C connector with appropriate ESD protection
- [ ] Verify the PD negotiation sequence (source capability → sink request → transition) is correctly handled in firmware
- [ ] Check dead battery mode — confirm the PD controller can bootstrap from VBUS even when the system battery is fully depleted
- [ ] Verify that VBUS voltage transitions (e.g., 5V → 9V) do not cause inrush current spikes that trip overcurrent protection
- [ ] Confirm that the PD controller's fault outputs (overcurrent, overvoltage, thermal) are connected to the system controller
- [ ] For dual-role / DRP designs: verify the CC pin orientation detection (CC1 vs. CC2 swap) is handled correctly
- [ ] Verify compliance with USB PD 3.0 / PPS (Programmable Power Supply) if required for fast charging
