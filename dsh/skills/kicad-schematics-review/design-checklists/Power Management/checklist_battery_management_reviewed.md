# Battery Management IC (Fuel Gauge / Monitor / Protector) Design Checklist

## 1. Fuel Gauge Selection Verification

- [ ] Confirm gauge algorithm (voltage-based, coulomb-counting, Impedance Track, CEDV) meets the accuracy requirements for the application
- [ ] Verify the gauge IC supports the correct number of series cells and battery chemistry
- [ ] Check that voltage, current, and temperature measurement ranges cover all operating conditions
- [ ] Confirm communication interface (I2C, SMBus, HDQ, Onewire) is compatible with the host controller

## 2. Current Sense Verification

- [ ] Verify sense resistor value and power rating are adequate for the maximum charge/discharge current
- [ ] Confirm sense resistor tolerance and TCR (temperature coefficient) are suitable for the required measurement accuracy
- [ ] Check that sense resistor layout uses Kelvin (4-terminal) connection or equivalent — verify sense traces are routed as a differential pair from the resistor pads to the gauge IC
- [ ] Verify RC filter on sense lines (resistor + capacitor) matches datasheet recommendations

## 3. Battery Monitoring

- [ ] Confirm cell voltage measurement accuracy (±mV) is sufficient for the application
- [ ] Verify ADC resolution is adequate for the required voltage/current/temperature precision
- [ ] For multi-cell packs: confirm cell balancing support (passive or active) and balancing current are appropriate for the cell capacity
- [ ] Verify current measurement dynamic range covers sleep current (nA) through maximum discharge current (A)
- [ ] Confirm temperature monitoring — verify NTC thermistor value and B-coefficient match the gauge IC's configuration, and that the number of temperature channels is sufficient

## 4. Protection Features

### Primary Protection
- [ ] Verify overvoltage protection (OVP) threshold prevents cell voltage exceeding the battery's absolute maximum
- [ ] Confirm undervoltage protection (UVP) threshold prevents deep discharge below the battery's minimum safe voltage
- [ ] Check overcurrent thresholds for charge and discharge — verify they are set above normal operating currents with appropriate margin
- [ ] Verify short-circuit protection (SCP) response time is fast enough to prevent damage

### Secondary Protection
- [ ] If present, verify secondary OVP IC thresholds are coordinated with primary protection for redundancy
- [ ] Confirm eFuse/chemical fuse (if used) is selected to clear before catastrophic failure

### Protection FETs
- [ ] Verify charge and discharge FETs (back-to-back N-MOSFETs) have adequate R_DS_ON for the current and are rated for the battery voltage
- [ ] Confirm FET gate drive voltage from the protector/gauge IC is sufficient to fully enhance the FETs
- [ ] Check FET package and PCB copper area are adequate for power dissipation

## 5. Communication Interface

- [ ] Confirm I2C/SMBus bus voltage and pull-up resistors are compatible with both the gauge IC and the host controller
- [ ] Verify SMBus timeouts and protocol features match the implementation
- [ ] Check that the required SMBus commands (remaining capacity, voltage, current, temperature, SoC) are supported and correctly mapped

## 6. Configuration

- [ ] Confirm NTC parameters (B value, R0) are configured to match the actual thermistor

## 7. Thermal Verification

- [ ] Verify power dissipation in the protection FETs and sense resistor at maximum continuous current — confirm junction temperature stays within ratings
