# Electromechanical I/O (Switches, Buttons, Keypads) Design Checklist

## 1. Switch / Button Type Selection

### Tactile Switch
- [ ] Verify actuation force meets application requirements (check datasheet for force rating)
- [ ] Verify travel distance is appropriate per datasheet
- [ ] Verify lifecycle rating meets expected product lifetime
- [ ] Verify terminal type (SMT, THT) is compatible with PCB assembly process
- [ ] Verify package size fits PCB layout constraints

### Slide Switch / DIP Switch
- [ ] Verify number of poles and positions (SPST, SPDT, DPDT, DIP) meets application requirements
- [ ] Verify pitch matches PCB footprint per datasheet
- [ ] Verify actuator type (raised vs. recessed) is appropriate for accessibility requirements
- [ ] Verify current rating meets application requirements per datasheet

### Push Button (Panel Mount)
- [ ] Verify momentary vs. latching type is correct for application
- [ ] Verify contact rating meets load requirements per datasheet
- [ ] Verify IP rating meets environmental requirements

### Rotary Switch
- [ ] Verify number of positions meets application requirements
- [ ] Verify coding type (BCD, hexadecimal, gray code) matches system interface

### Keypad / Matrix
- [ ] Verify key count and layout meet user interface requirements
- [ ] Verify switch technology (membrane, dome-switch, mechanical) meets feel and durability needs
- [ ] Verify backlight requirements (individual LED vs. edge-lit) per datasheet

## 2. Electrical Interface

### GPIO Reading (Single Switch)
- [ ] Verify switch circuit configuration (pull-up to VCC or pull-down to GND) per application requirements
- [ ] Verify pull-up/pull-down resistor value provides adequate debounce and meets GPIO drive strength
- [ ] Verify logic level (active-low or active-high) matches firmware design

### Matrix Keypad Scanning
- [ ] Verify row pin configuration as outputs and column pins as inputs with pull-ups
- [ ] Verify scanning sequence timing meets firmware constraints
- [ ] Verify debounce time is adequate for switch type per datasheet
- [ ] Verify ghosting prevention (diodes on each key) for larger matrices

### Interrupt Generation
- [ ] Verify wake-from-sleep capability: GPIO interrupt is active in sleep mode
- [ ] If using GPIO expander with interrupt output, verify interrupt routing to host

## 3. Debouncing

### Hardware Debounce
- [ ] Verify RC filter time constant (τ = R × C) provides adequate debounce per switch datasheet
- [ ] If Schmitt trigger used after RC filter, verify part number and thresholds
- [ ] If dedicated debounce IC used, verify configuration per datasheet

### Software Debounce
- [ ] Verify debounce timing (sample interval, stable count) matches switch bounce characteristics per datasheet
- [ ] Verify debounce algorithm handles edge detection correctly

## 4. LED / Illumination Integration

- [ ] If switch has integrated LED, verify series resistor value per LED datasheet (consider V_F and I_LED)
- [ ] Verify total current draw when multiple switch LEDs are simultaneously on
- [ ] If PWM dimming used, verify PWM frequency avoids visible flicker
- [ ] For bi-color LED: verify common cathode or common anode configuration matches driver circuit

## 5. ESD Protection

- [ ] If switch contacts external panel, verify TVS diode or ESD protection array is included
- [ ] Verify series resistor between switch and GPIO for current limiting during ESD events
- [ ] For exposed panel switches: verify RC filtering (e.g., 10 kΩ + 100 nF) for ESD protection

## 6. Mechanical Integration

### Panel Mounting
- [ ] Verify panel thickness is compatible with switch mounting type (snap-in vs. screw-mount)
- [ ] If waterproofing required, verify sealing gasket is included
- [ ] Verify nut torque per manufacturer specification
- [ ] Verify keycap/actuator height provides adequate protrusion for user operation

### PCB Mounting
- [ ] Verify tactile switch footprint includes alignment features for soldering
- [ ] Verify DIP switch pitch matches PCB footprint per datasheet
- [ ] For aftermarket keypads: verify connector type (FPC, ZIF, pogo pins) is compatible
- [ ] Verify locating holes or edge alignment features for keypad overlay

### Environmental Sealing
- [ ] Verify IP rating meets application environmental requirements per datasheet
- [ ] If conformal coating used, verify compatibility with switch feel and actuation
- [ ] If outdoor use, verify drain holes in enclosure for condensation
