# Instrumentation Amplifier (IA) Design Checklist

## 1. Topology

- [ ] Confirm the IA topology (three-op-amp, two-op-amp, integrated, or difference amplifier with external resistors) is appropriate for the application
- [ ] Verify the IA provides adequate CMRR (Common-Mode Rejection Ratio) for the expected common-mode voltage range and frequency
- [ ] Check that CMRR is specified at the relevant gain setting — CMRR typically improves with higher gain

## 2. Gain Configuration

- [ ] Confirm the gain (set by R_G or pin-selected) produces the required output swing for the expected input signal range
- [ ] Verify the gain-bandwidth relationship — confirm the IA's bandwidth at the selected gain is sufficient for the signal frequency
- [ ] For programmable gain IAs: verify the gain selection method (SPI, I2C, pin-strapping) is correctly implemented

## 3. Input Characteristics

- [ ] Confirm the differential input impedance is compatible with the signal source — for high-impedance sensors (e.g., pH probe, ECG electrode), FET-input IAs with high impedance are required
- [ ] Verify the common-mode input impedance — an imbalance between the two inputs can degrade CMRR
- [ ] Check the input bias current — for high-source-impedance sensors, bias current flowing through the source impedance creates offset error
- [ ] Verify that source impedances on both inputs are balanced to minimize offset from bias current

## 4. Input Common-Mode and Output Swing

- [ ] Confirm the input common-mode voltage range covers the expected sensor output — verify using the IA's diamond plot (input common-mode vs. output voltage) for single-supply designs
- [ ] Verify the output voltage swing can reach the required level for the downstream ADC or circuit
- [ ] For single-supply designs: confirm the output can swing to 0V (or use a rail-to-rail output IA) if ground-referenced output is needed
- [ ] Check that the REF pin voltage is set correctly — for single-supply, verify the output is referenced to mid-supply or the appropriate DC level

## 5. Noise

- [ ] Verify the IA's input-referred noise (nV/√Hz or µVpp) is acceptable for the signal amplitude and required SNR
- [ ] For high-gain configurations: confirm the output noise (gain × input noise) does not saturate the output or the downstream ADC
- [ ] Check IA noise against sensor noise — the IA noise should be well below the sensor's own noise floor
- [ ] If the IA is used near RF sources, verify the IA's EMIRR (Electromagnetic Interference Rejection Ratio) is adequate; add RFI filtering at inputs if needed

## 6. Input Protection

- [ ] Verify absolute maximum input voltage ratings — confirm inputs can survive expected fault conditions (ESD, overvoltage, sensor short)
- [ ] If input voltages can exceed the supply rails, verify external protection (clamp diodes with series resistors) is present
- [ ] For high-impedance applications: verify that protection leakage current does not corrupt the signal

## 7. Filtering

- [ ] Confirm that an input differential RC filter (AC-coupled if necessary) is present before the IA to reduce high-frequency common-mode noise and prevent RF rectification
- [ ] Verify the filter's corner frequency is appropriate for the signal bandwidth
- [ ] If a common-mode filter (capacitor from each input to ground) is used, verify the capacitor values are matched (mismatched capacitors degrade CMRR at the filter cutoff)
- [ ] Confirm an output low-pass filter (RC) is present after the IA if needed for noise reduction

## 8. Power Supply

- [ ] Verify the supply voltage range (single or dual) is adequate for the input signal and required output swing
- [ ] Confirm supply decoupling capacitor placement and values per datasheet
- [ ] For dual-supply designs: verify the REF pin is connected to GND for bipolar output centered at 0V

## 9. Application-Specific

- [ ] Bridge / strain gauge: confirm the IA can measure the small differential signal (mV/V) in the presence of a large common-mode voltage (half-bridge excitation)
- [ ] Thermocouple: verify the IA gain is compatible with the thermocouple sensitivity (µV/°C) and cold-junction compensation
- [ ] ECG / biopotential: confirm the IA meets medical safety standards (patient leakage current, defibrillation protection) and has sufficient CMRR at 50/60 Hz
- [ ] Current sensing (high-side): verify the IA's common-mode voltage range covers the supply rail — use a high-common-mode IA or difference amplifier
