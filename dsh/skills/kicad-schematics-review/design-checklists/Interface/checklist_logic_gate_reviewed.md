# Logic Gate / Bus Driver / Buffer Design Checklist

## 1. Device Selection

### Logic Family
- [ ] Verify logic family (LVC, AHC, HC, HCT, AXC, LVx) meets voltage and speed requirements per datasheet
- [ ] Verify supply voltage range matches available system rails

### Gate Function
- [ ] Verify gate function (buffer/inverter/AND/OR/XOR/Schmitt trigger/flip-flop/multiplexer) matches application requirements

### Number of Channels
- [ ] Verify number of gates per package meets design requirements
- [ ] Verify package size fits PCB layout constraints

### Bus Driver / Buffer Specifics
- [ ] Verify driver type (line driver, bus transceiver, registered transceiver, open-drain) meets application requirements

## 2. Electrical Characteristics

### Input Thresholds
- [ ] Verify VIH/VIL thresholds are compatible with driving device at operating VCC per datasheet
- [ ] Check if inputs require higher voltage tolerant (if running at lower VCC)
- [ ] For Schmitt trigger: verify hysteresis voltage (VT+ − VT−) per datasheet

### Output Drive
- [ ] Verify IOH/IOL meets load requirements per datasheet
- [ ] Verify total package current limit is not exceeded when all outputs are active
- [ ] For bus drivers: verify drive strength is adequate for trace length and fan-out

### Propagation Delay
- [ ] Verify tPD meets timing budget per datasheet
- [ ] For clock distribution: verify matched-delay buffers are used

### Power Consumption
- [ ] Verify quiescent current (ICC) meets system power budget per datasheet
- [ ] Verify dynamic power dissipation is within limits at operating frequency
- [ ] If power-down / disable mode is required, verify device supports it

### Input Pull-up / Pull-down
- [ ] Verify if internal pull-up/pull-down resistors are present and of appropriate value per datasheet
- [ ] For unused inputs, verify they are tied to VCC or GND (CMOS inputs must not float)

## 3. Pin Configuration

### Output Enable (OE) — Bus Drivers
- [ ] Verify OE pin polarity and connection (always enabled via supply, or GPIO-controlled)
- [ ] For multi-bank drivers: verify each bank's OE is configured correctly

### Direction Control (DIR) — Transceivers
- [ ] Verify DIR pin is driven to correct logic level for desired data flow direction
- [ ] Verify DIR is stable during data transmission per datasheet

### Unused Inputs
- [ ] Verify unused inputs are tied to VCC or GND (not floating)

### Unused Outputs
- [ ] Verify unused outputs are left unconnected (no pull-up/down needed)
- [ ] Verify unused outputs are not shorted together (avoid contention)

## 4. Special Functions

### Schmitt Trigger Inputs
- [ ] Verify hysteresis voltage is adequate for noise environment per datasheet
- [ ] Verify Schmitt trigger is appropriate for application (noisy inputs, slow edges)

### Open-Drain Outputs
- [ ] Verify external pull-up resistor value is calculated for target speed and bus capacitance
- [ ] Verify pull-up voltage is within open-drain output voltage rating

### Three-State Outputs
- [ ] Verify enable/disable sequencing prevents contention between multiple drivers on shared bus
- [ ] Verify turn-around time (OE active to output valid) meets timing requirements per datasheet

## 5. Cascading / Fan-Out

- [ ] Verify fan-out capability: driver IOH/IOL vs. load IIH/IIL per datasheet
- [ ] For high fan-out or long traces: verify line driver or buffer is used

## 6. Power Supply

- [ ] Verify supply voltage matches logic family requirement per datasheet
- [ ] Verify decoupling capacitor (100 nF) is placed near each VCC pin
- [ ] For multiple gates in one package: verify one decoupling cap per package
- [ ] If device has IOFF protection, verify power-up/down sequencing per datasheet
