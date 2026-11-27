# DDR / SDRAM / DRAM Design Checklist

## 1. Device Selection

- [ ] Verify DDR generation (DDR2/3/4/5, LPDDR2/3/4/5, SDRAM) meets system performance requirements
- [ ] Verify density, bus width, and rank configuration match controller requirements
- [ ] Verify memory clock speed is supported by controller
- [ ] Verify voltage tolerances per datasheet (typically ±3-5%)

## 2. Power Supply

### Voltage Rails

- [ ] Verify VDD (core supply) voltage per datasheet
- [ ] Verify VDDQ (I/O supply) voltage per datasheet
- [ ] Verify VPP (programming voltage, if applicable) per datasheet
- [ ] Verify VTT (termination voltage) = VDDQ/2 per datasheet
- [ ] Verify VREF (reference voltage) = VDDQ/2 per datasheet

### Power Sequencing

- [ ] Verify power-up sequencing: VDD → VDDQ → VTT/VREF per datasheet
- [ ] Verify VTT tracks VDDQ/2 during operation
- [ ] If DDR5: verify VDD, VDDQ, VPP sequencing requirements per datasheet
- [ ] Verify reset timing after power-up per datasheet

### Decoupling

- [ ] Verify bulk capacitor values per datasheet
- [ ] Verify VTT decoupling uses low-ESR capacitors for termination noise
- [ ] Verify VREF filter uses RC network (e.g., 1-10 Ω + 0.1-1 µF) for low noise
- [ ] Verify VDD/VDDQ use power plane (not just traces)

### Power Consumption

- [ ] Verify active current (read/write/refresh) meets system power budget
- [ ] Verify standby and power-down currents meet system power budget
- [ ] Verify self-refresh current meets low-power requirements
- [ ] Verify thermal dissipation is within limits at maximum activity

## 3. Address / Command / Data Bus

### DDR Routing

- [ ] Verify DQ, DQS, DM within each byte lane are length matched per datasheet guidelines
- [ ] Verify clock pair (CK/CK#) is routed as differential pair, length matched within pair
- [ ] Verify address/command/control use fly-by topology with T-branch length matching
- [ ] Verify VTT termination at end of address/command lines per datasheet

### ODT and Impedance

- [ ] Verify ODT (On-Die Termination) settings are configured per datasheet
- [ ] Verify DQ/DQS impedance: target 40-60 Ω single-ended per datasheet
- [ ] Verify CK impedance: target 80-100 Ω differential per datasheet

## 4. Signal Integrity

### Termination

- [ ] Verify VTT termination resistors for address/command lines per datasheet
- [ ] Verify ODT enabled for DQ/DQS lines per datasheet
- [ ] Verify series termination for clock and strobe signals per datasheet

### Impedance Control

- [ ] Verify target impedance defined with PCB manufacturer (40-60 Ω single-ended, 80-100 Ω differential)
- [ ] Verify ZQ calibration resistor (240 Ω ±1%) is implemented for DDR3+

## 5. Memory Controller

- [ ] Verify memory controller is compatible with memory type and generation
- [ ] Check controller supports memory density, width, and rank configuration
- [ ] Verify memory clock speed is supported by controller
- [ ] Configure memory timing parameters (CAS latency, tRCD, tRP, tRAS, etc.) per datasheet
- [ ] Enable ECC if controller supports it and application requires it
- [ ] Configure refresh rate (temperature-dependent self-refresh if applicable)

## 6. Configuration / Initialization

- [ ] Implement DDR initialization sequence per JEDEC:
  - Apply power → wait for PLL lock → apply CKE → NOP → MRS
- [ ] Configure CAS latency, burst length, burst type per datasheet
- [ ] Configure ODT values per datasheet
- [ ] Configure drive strength per datasheet
- [ ] Perform ZQ calibration

## 7. Thermal

- [ ] Verify power dissipation (active vs. standby) is within limits
- [ ] Verify self-refresh power at expected operating temperature
- [ ] Verify refresh rate is increased at high temperatures (> 85°C) per datasheet
- [ ] Verify junction temperature range covers application environment

## 8. Reliability

- [ ] Enable ECC if controller supports it
- [ ] Implement software CRC check on critical stored data
- [ ] Verify brown-out: ensure write operations complete before power loss
