# ESD Protection (TVS Diode) Design Checklist

## 1. Device Selection

### TVS Diode vs. TVS Array
- [ ] Verify single TVS or TVS array is appropriate for number of protected lines
- [ ] If USB LC/EMI filter + ESD combo used: verify integrated solution meets both filtering and ESD requirements per datasheet
- [ ] If differential pair protection: verify directionally paired array is used (e.g., RailClamp)

### Working Voltage (VRWM)
- [ ] Verify VRWM ≥ maximum normal operating voltage of the protected line (including tolerances)
- [ ] Verify VRWM provides adequate margin above nominal operating voltage per datasheet recommendation

### Clamping Voltage (VC)
- [ ] Verify VC at peak pulse current (IPP) is below the absolute maximum rating of the protected IC per datasheet
- [ ] Verify clamping voltage at the applicable ESD test level (IEC 61000-4-2, 8 kV contact)

### Breakdown Voltage (VBR)
- [ ] Verify VBR tolerance (±5%) is acceptable for the application
- [ ] Verify VBR is below the protected IC's absolute maximum rating

### Capacitance (Cj / Cline)
- [ ] For high-speed data (USB 2.0, HDMI, Ethernet): verify capacitance per line is within interface requirements per datasheet
- [ ] For USB 3.0 / DisplayPort / PCIe: verify capacitance per line is within interface requirements per datasheet
- [ ] For GPIO / I2C / SPI / buttons: verify capacitance is acceptable for signal speed
- [ ] For antenna / RF: verify capacitance is low enough to avoid signal attenuation per datasheet
- [ ] For differential pairs: verify differential capacitance is within specification

### IEC 61000-4-2 Rating
- [ ] Verify contact discharge rating meets product ESD target per datasheet
- [ ] Verify air discharge rating meets product ESD target per datasheet
- [ ] Verify TVS is certified to the ESD standard required by the product
- [ ] If surge protection also required: verify TVS is certified to IEC 61000-4-5

## 2. Application-Specific Selection

### USB 2.0
- [ ] Verify capacitance per line is within USB 2.0 signal integrity requirements per datasheet
- [ ] Verify 2-channel TVS array in single package (D+, D−)

### USB 3.0 / USB-C
- [ ] Verify capacitance per line is within USB 3.0 signal integrity requirements per datasheet
- [ ] Verify all required channels are protected: SSTX+/−, SSRX+/−, D+/−, CC, SBU
- [ ] For USB-C: verify multi-channel array has sufficient channel count

### HDMI
- [ ] Verify capacitance per line is within HDMI signal integrity requirements per datasheet
- [ ] Verify all required lines are protected: 4 TMDS pairs + DDC + HPD + CEC

### Ethernet (10/100/1000)
- [ ] Verify capacitance per line is acceptable (transformers provide isolation)
- [ ] Verify TVS is placed between connector and magnetics (not between magnetics and PHY)

### GPIO / Buttons / Switches
- [ ] Verify TVS capacitance is acceptable (not speed-critical) per datasheet
- [ ] If RC filter used (R + C to GND): verify values provide adequate ESD protection per application

### Audio Lines
- [ ] Verify capacitance per line is acceptable for audio frequencies per datasheet
- [ ] For speaker outputs: verify bidirectional or anti-series TVS configuration per datasheet
- [ ] For microphone inputs: verify leakage current is low enough to avoid noise per datasheet

### Antenna / RF
- [ ] Verify capacitance is low enough to avoid signal attenuation and frequency shift per datasheet
- [ ] If quarter-wave stub with TVS used: verify protection bandwidth is adequate per application

## 3. Power Rail Protection

- [ ] Verify VRWM exceeds nominal rail voltage (including tolerances and transients)
- [ ] Verify peak pulse power (PPP) rating is adequate for expected surge events per datasheet
- [ ] For DC power input: verify higher-power TVS package (SMC/SMB) is used
- [ ] For battery: verify TVS on VBAT line close to battery connector
- [ ] For positive voltage rails: verify unidirectional TVS (better clamping) is used per datasheet
