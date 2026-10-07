# Voltage Regulator — LDO (Low Drop-Out) Design Checklist

## 1. Selection Verification

- [ ] Confirm LDO (vs. Switching Power Supply) is appropriate for the application requirements
- [ ] Verify input voltage range covers all operating conditions, including tolerances and transients
- [ ] Confirm output voltage (fixed or adjustable via resistor divider) meets load requirements with acceptable accuracy
- [ ] Verify dropout voltage is less than available headroom (V_in_min − V_out) at full load current
- [ ] Confirm output current rating exceeds the maximum load current, with margin
- [ ] Check quiescent current (I_q) is acceptable for the battery life or standby power budget
- [ ] Verify shutdown current when EN/SHDN is de-asserted — important for low-power designs

## 2. Thermal

- [ ] Calculate power dissipation at worst-case V_in and I_out; verify junction temperature stays within the IC's rated range with margin
- [ ] Confirm the package and PCB copper area are adequate for the calculated power dissipation
- [ ] If junction temperature is marginal, verify that the design uses appropriate mitigations (lower dropout, reduced load, improved heatsinking, larger package)
- [ ] Check that adjacent heat-sensitive components are not adversely affected by the LDO's self-heating

## 3. Input & Output Capacitors

- [ ] Verify input capacitor type, value, and voltage rating meet datasheet minimum requirements
- [ ] Confirm output capacitor type, value, and ESR are within the range specified for stability — pay special attention to ESR requirements for older NPN/PNP LDOs vs. modern CMOS types
- [ ] Check that actual capacitance after DC bias derating (for MLCCs) still meets the minimum requirement at the operating voltage
- [ ] Verify capacitor temperature coefficient (X5R, X7R, etc.) is adequate for the operating temperature range
- [ ] Confirm output capacitance is sufficient for the required transient response (voltage droop during load steps)
- [ ] For adjustable LDOs: verify feedback resistor placement and routing per datasheet recommendations

## 4. Noise & PSRR

- [ ] Verify LDO PSRR is adequate at the frequencies of interest for downstream noise-sensitive loads (ADC, PLL, audio, RF)
- [ ] Confirm output noise density (nV/√Hz) or total RMS noise meets the load's requirements
- [ ] If a noise-reduction (NR/SS) pin is available, verify the bypass capacitor is present and correctly sized per datasheet
- [ ] For RF/analog supplies: check if additional input filtering (ferrite bead + capacitor) is needed to improve PSRR at high frequencies

## 5. Enable / Shutdown

- [ ] Verify enable threshold voltages (V_EN_H, V_EN_L) are compatible with the driving logic level
- [ ] Confirm enable polarity (active-high or active-low) matches the control signal
- [ ] Check output state when disabled — verify high-impedance vs. pull-down-to-GND behavior is correct for the application
- [ ] If EN is used for sequencing, verify timing relationships with other power rails

## 6. Protection Features

- [ ] Verify current limit threshold exceeds maximum load current with adequate margin
- [ ] Confirm over-temperature protection (OTP) threshold and hysteresis; verify recovery behavior is acceptable
- [ ] Check if reverse current protection is needed — does the LDO prevent current flow from V_out to V_in when V_in is removed?
- [ ] For automotive/industrial designs: verify reverse polarity protection if V_in can be reversed
- [ ] Confirm undervoltage lockout (UVLO) threshold (if present) prevents operation below V_in_min

## 7. Soft-Start

- [ ] Verify soft-start behavior (internal or external capacitor) prevents excessive inrush current at startup
- [ ] Confirm soft-start time is consistent with system power-up timing requirements
- [ ] Check that the output ramps monotonically without overshoot during startup
- [ ] If sequencing multiple rails, verify soft-start times and enable delays produce the correct order

## 8. Stability

- [ ] Confirm the chosen output capacitor (type, value, ESR) keeps the LDO stable across the full load range (0 to I_max)
- [ ] If the LDO requires a minimum output current for stability, verify the no-load condition still meets this requirement (or use a dummy load resistor)
- [ ] Check stability with worst-case output capacitance (lowest tolerance, highest temperature, highest DC bias derating)
- [ ] Verify the LDO does not oscillate during load transient events (step up and step down)
