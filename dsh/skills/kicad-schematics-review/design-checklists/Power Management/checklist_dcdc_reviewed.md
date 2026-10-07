# Voltage Regulator — DC-DC Switching Regulator Design Checklist

## 1. Topology Verification

- [ ] Confirm selected topology matches the application requirements (buck/boost/buck-boost/SEPIC/flyback etc.)
- [ ] Verify topology is appropriate for required power level and isolation needs
- [ ] Check that no simpler topology could suffice (e.g., LDO instead of buck for low current / low V_in−V_out)

## 2. Operating Conditions

### Input
- [ ] Verify input voltage range covers all operating conditions (including supply tolerances, battery discharge curve, brown-out)
- [ ] Confirm minimum startup voltage is achievable from the input source in worst-case conditions
- [ ] Verify absolute maximum V_in is never exceeded during any transient (load dump, hot-plug)
- [ ] Check input ripple current against input capacitor RMS rating

### Output
- [ ] Confirm output voltage and tolerance meet load requirements
- [ ] Verify maximum output current with adequate margin for peak/transient loads
- [ ] Check output voltage ripple specification meets the requirements of all downstream loads
- [ ] Verify line regulation and load regulation specs are sufficient
- [ ] Confirm transient response (voltage droop/overshoot) is acceptable for the load step magnitude

### Efficiency
- [ ] Verify efficiency at full load, typical load, and light load meets system power budget
- [ ] Check quiescent current (I_q) is acceptable for battery-powered or always-on applications
- [ ] Confirm light-load efficiency mode (PFM / pulse-skip / forced CCM) is configured appropriately

## 3. Switching Frequency & Duty Cycle

### Switching Frequency
- [ ] Verify f_sw is within the controller's supported range
- [ ] Confirm f_sw choice balances efficiency, component size, and EMI constraints
- [ ] If spread-spectrum is enabled, verify it does not interfere with noise-sensitive circuits (PLL, ADC, audio)
- [ ] Check if external clock synchronization is needed and properly configured
- [ ] Verify frequency foldback behavior at light load or fault conditions

### Duty Cycle
- [ ] Calculate D at V_in_min and V_in_max for the selected topology; verify both fall within the controller's operating range
- [ ] Confirm minimum on-time (t_ON_min) does not limit achievable V_out at highest V_in and f_sw
- [ ] Confirm maximum duty cycle (D_max) leaves adequate headroom for dropout at V_in_min; verify bootstrap capacitor can refresh for synchronous bucks near 100% duty
- [ ] For wide V_in range designs: verify D_min constraint is not violated — if it is, confirm f_sw reduction or post-regulation is acceptable
- [ ] Verify duty cycle behavior in light-load / DCM mode — confirm skip-mode or PFM transitions are stable
- [ ] Check that worst-case duty cycle (V_in_min, full load) still leaves margin for a load transient without hitting dropout

## 4. Inductor

- [ ] Verify inductance value against controller datasheet recommendations for the selected f_sw and topology
- [ ] Confirm peak inductor current (I_L_peak) does not exceed the inductor's saturation current (I_sat) at maximum load and highest ambient temperature
- [ ] Check saturation current derating at maximum operating temperature (ferrite cores lose I_sat as temperature rises)
- [ ] Verify inductor RMS current rating exceeds I_L_RMS at full load
- [ ] Confirm DCR is low enough that I²R losses are acceptable for efficiency and thermal budget
- [ ] Verify self-resonant frequency (SRF) is well above f_sw — at least 5-10× f_sw
- [ ] Check inductor core material and construction are appropriate for f_sw (ferrite for >500 kHz, powder for lower frequencies)
- [ ] Check if using shielded inductor. Always use shielded inductor when possible

## 5. Output Capacitor

- [ ] Confirm output capacitance value meets stability requirements per controller datasheet (min/max C_out)
- [ ] Verify actual capacitance after DC bias derating still meets minimum requirement at the operating output voltage
- [ ] Check capacitor type and temperature coefficient (X5R, X7R) are adequate for the operating temperature range
- [ ] Verify ESR is within the range required for loop stability — too low can reduce phase margin; too high increases ripple
- [ ] Confirm output ripple voltage (capacitive + ESR components) meets the target specification
- [ ] For electrolytic capacitors: verify ripple current rating and lifetime at operating temperature

## 6. Input Capacitor

- [ ] Verify input capacitance value meets controller datasheet minimum requirement
- [ ] Confirm input capacitor RMS ripple current rating exceeds calculated I_CIN_RMS
- [ ] Check voltage rating with adequate margin above V_in_max (including transients)
- [ ] Verify actual capacitance after DC bias derating at V_in_max

## 7. Feedback & Compensation

### Feedback Divider
- [ ] Verify feedback resistor values produce the correct V_out per the controller's V_ref
- [ ] Confirm resistor tolerance (typically 0.1% or 1%) provides adequate output accuracy
- [ ] Check that feedback divider current is within the recommended range per datasheet

### Loop Compensation (for externally compensated converters)
- [ ] Verify compensation network type (Type I/II/III) and component values per controller datasheet recommendations for the chosen L and C_out
- [ ] Confirm phase margin ≥ 45° (preferably ≥ 60°) via simulation or measurement
- [ ] Verify gain margin ≥ 10 dB
- [ ] Check stability at all operating conditions: V_in_min/V_in_max, no load/full load, and after load transients
- [ ] For internally compensated converters: verify the output LC combination is within the controller's stable region per datasheet charts

## 8. Enable, Soft-Start & Sequencing

- [ ] Verify EN pin threshold voltages (V_EN_H, V_EN_L) are compatible with the driving logic level
- [ ] If EN is driven by a voltage divider from V_in, confirm the thresholds trip at the intended V_in level
- [ ] Confirm soft-start time is appropriate — long enough to limit inrush, short enough for system startup requirements
- [ ] If multiple rails are sequenced: verify soft-start timing and EN/PG pin connections produce the correct power-up/down order
- [ ] Check behavior when EN is de-asserted (immediate shutdown vs. controlled ramp-down)

## 9. Protection Features

- [ ] Verify overcurrent protection (OCP) threshold is above max load current and below inductor I_sat
- [ ] Confirm OCP behavior (hiccup vs. latch-off vs. cycle-by-cycle) is appropriate for the application
- [ ] Check overvoltage protection (OVP) threshold — ensure it triggers before any downstream component's abs-max rating
- [ ] Verify undervoltage lockout (UVLO) thresholds prevent operation below V_in_min
- [ ] Confirm thermal shutdown (TSD) threshold and hysteresis; verify recovery behavior is safe for the system
- [ ] For boost/buck-boost: verify reverse current protection prevents back-feeding from output to input
- [ ] Check that protection fault responses (auto-recovery vs. latch-off) are documented and consistent with system requirements

## 10. Thermal

- [ ] Verify power dissipation at full load and worst-case V_in does not exceed the controller's package thermal limit
- [ ] Confirm junction temperature (T_j) at max ambient + self-heating stays within the IC's rated range, with margin
- [ ] Check if thermal derating (frequency reduction, current foldback) engages at expected temperatures
- [ ] Verify exposed pad is soldered to PCB ground plane with adequate thermal vias for heat dissipation
- [ ] Confirm PCB copper area is sufficient for the calculated power dissipation

## 11. EMI & Noise

- [ ] Verify switching node (SW/LX) ringing is within acceptable limits; add RC snubber if excessive
- [ ] Confirm input filtering (capacitor + optional ferrite bead) is present and adequate
- [ ] Check that spread-spectrum mode (if used) does not introduce unacceptable low-frequency ripple for downstream loads
