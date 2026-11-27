# Isolation (Digital Isolator / Optocoupler) Design Checklist

## 1. Isolation Technology

### Type Selection
- [ ] Verify isolation technology (capacitive coupling, magnetic coupling, optocoupler, GMR) meets speed, power, and CMTI requirements per datasheet

### Isolation Voltage
- [ ] Verify VISO (RMS) rating meets application safety requirements per datasheet
- [ ] Verify working voltage (continuous) rating exceeds maximum operating voltage
- [ ] Verify transient overvoltage rating (surge capability) meets application requirements per datasheet
- [ ] Verify creepage/clearance distance meets safety standard requirements (IEC 60950-1 / IEC 62368-1) based on working voltage and pollution degree

### Safety Certification
- [ ] Verify UL 1577 certification per component datasheet
- [ ] Verify IEC 60747-17 (capacitive isolators) or IEC 60747-5-5 (optocouplers) certification as required
- [ ] Verify CSA, VDE, CQC certifications match end-equipment requirements
- [ ] Verify maximum working voltage and isolation class (basic vs. reinforced) per safety standard

## 2. Channel Configuration

- [ ] Verify number of channels matches interface requirements (1-6 channels)
- [ ] Verify forward/reverse direction configuration matches signal flow
- [ ] Verify unidirectional vs. bidirectional (I2C) per interface requirements
- [ ] If isolated power integrated: verify isolated output current capability meets load requirements
- [ ] For SPI isolation: verify channel configuration (3+1: CS, MOSI, SCK forward, MISO reverse)
- [ ] For I2C isolation: verify bidirectional data (SDA) and clock (SCL) per isolator datasheet
- [ ] For CAN isolation: verify isolated CAN transceiver is used per bus requirements

## 3. Electrical Characteristics

### Data Rate
- [ ] Verify maximum data rate exceeds communication speed (with margin) per datasheet
- [ ] For SPI: verify data rate is compatible with SPI clock frequency including isolator delay

### Propagation Delay
- [ ] Verify propagation delay meets system timing budget per datasheet
- [ ] Verify pulse width distortion (PWD) is within limits per datasheet
- [ ] Verify channel-to-channel skew is within limits for parallel interfaces (SPI) per datasheet
- [ ] For SPI isolator: verify round-trip delay is compatible with SPI clock period

### Common-Mode Transient Immunity (CMTI)
- [ ] Verify CMTI meets application requirements per datasheet
- [ ] For motor drives, inverters, and industrial environments: verify high CMTI rating per datasheet

### Power Consumption
- [ ] Verify quiescent current per side meets system power budget per datasheet
- [ ] Verify dynamic current at operating data rate meets power budget per datasheet
- [ ] For optocouplers: verify LED drive current (IF) is within system power budget
- [ ] For battery-powered designs: verify low-power operation or duty-cycling is adequate

## 4. Power Supply (Isolated)

### Separate Supplies
- [ ] Verify each side's supply voltage (VDD1, VDD2) is within operating range per datasheet
- [ ] Verify both sides are powered before data transmission per datasheet sequencing requirements
- [ ] Verify decoupling capacitors (100 nF) are placed close to each side's supply pins

### Integrated Isolated Power (isoPower)
- [ ] Verify output power budget (50-500 mW typical) meets isolated side load requirements per datasheet
- [ ] Verify output ripple is acceptable or add external LDO per datasheet recommendation
- [ ] Verify external decoupling and filtering follows datasheet recommendations

### External Isolated DC-DC
- [ ] Verify isolated DC-DC module meets power demand of the isolated side per datasheet
- [ ] If discrete flyback/push-pull with transformer: verify component ratings meet requirements

## 5. Application-Specific Considerations

### I2C Isolation
- [ ] Verify I2C-specific isolator with bidirectional data channel is used per datasheet
- [ ] Verify supported I2C speed meets application requirements per datasheet
- [ ] Verify open-drain output behavior on isolated side per datasheet
- [ ] Verify pull-up resistors are present on both isolated buses — values per bus capacitance
- [ ] Verify bus capacitance including isolator is within I2C specification

### SPI Isolation
- [ ] Verify isolator delay is compatible with SPI clock period per datasheet
- [ ] For high-speed SPI (>20 MHz): verify low-latency isolator is used per datasheet
- [ ] Verify channel configuration matches SPI signals (3+1 or 4+0)

### UART Isolation
- [ ] Verify 2-channel isolator (TX → RX, RX → TX) per application
- [ ] Verify baud rate is supported by isolator per datasheet
- [ ] Verify start bit timing with isolator propagation delay is within tolerance

### CAN Isolation
- [ ] Verify CAN-specific isolated transceiver is used per datasheet
- [ ] Verify CMTI rating is adequate for motor-drive applications per datasheet
