# Operational Amplifier (Op-Amp) Design Checklist

## 1. Selection & Topology

- [ ] Confirm the op-amp type (general-purpose, precision, low-noise, low-power, high-speed, rail-to-rail input and/or output) is appropriate for the application requirements
- [ ] Verify the supply voltage range (single or dual) is compatible with the available rails and the required output swing
- [ ] Confirm the circuit topology (inverting, non-inverting, differential, summing, integrator, differentiator, transimpedance, active filter) is correct and produces the intended transfer function
- [ ] Verify the gain-setting resistor values produce the correct closed-loop gain; confirm their tolerance is adequate for accuracy and their values are within practical limits — very high ratios or very high resistances may cause stability or noise issues
- [ ] Check that the feedback network does not present an excessive load to the op-amp output (total R_f + R_g should be >> the minimum load resistance)

## 2. Biasing and Coupling

### DC-Coupled Circuits
- [ ] Verify the input signal's DC level falls within the op-amp's input common-mode range at all operating conditions
- [ ] Confirm that the op-amp's input bias current has a DC return path to ground (or mid-supply) on both the inverting and non-inverting inputs — every op-amp input must have a DC path; a series capacitor without a resistor to a reference voltage leaves the input floating
- [ ] Check that the output DC offset (from V_os × gain + I_b × R_source × gain) does not cause the output to saturate or exceed the downstream circuit's input range

### AC-Coupled Circuits
- [ ] Verify the AC coupling capacitor value produces the correct high-pass corner frequency for the signal bandwidth — confirm the capacitor's reactance at the lowest signal frequency is negligible compared to the input impedance
- [ ] Check the coupling capacitor's voltage rating and polarity (if electrolytic) — for single-supply circuits, the capacitor's DC bias may reverse if the signal swings below the bias point
- [ ] Confirm the bias network (resistive divider to mid-supply or ground) sets the correct DC operating point at the op-amp input; verify the Thevenin equivalent resistance of the bias divider contributes to input impedance and input-referred noise
- [ ] For the non-inverting AC-coupled amplifier: verify the bias resistor (from +input to mid-supply/ground) provides the bias current return path; confirm its value sets the input impedance and that the coupling capacitor corner frequency uses this resistance
- [ ] Check that the bias network's noise contribution (4kTR) is acceptable at the lowest signal frequency — high-value bias resistors (≥ 100 kΩ) can dominate the noise floor in low-noise designs

## 3. Source Impedance & Input Impedance

- [ ] Verify the amplifier's input impedance is compatible with the signal source:
  - Inverting topology: input impedance = R_in (the input resistor); if R_in is low (< 10 kΩ), confirm a buffer or higher R_in is used if the source cannot drive a low-impedance load
  - Non-inverting topology: input impedance ≈ the op-amp's common-mode input impedance (very high for FET/CMOS, lower for BJT input op-amps); confirm the bias resistors in parallel with the input do not reduce the effective input impedance below the source's requirement
- [ ] Check that the source impedance does not interact with the op-amp's input capacitance to create an unintended low-pass filter — for high-source-impedance sensors, verify the resulting RC corner frequency is well above the signal bandwidth
- [ ] For BJT-input op-amps: verify that mismatched source resistances at the inverting and non-inverting inputs do not create excessive offset voltage — V_os_from_Ib = I_b × |R_eq(+) − R_eq(−)|, where R_eq is the Thevenin equivalent resistance seen by each input
- [ ] Confirm that the source impedance's thermal noise (e_n = √(4kTR_source) per √Hz) is accounted for in the total noise budget and does not dominate the op-amp's own input noise

## 4. Offset Voltage & Multistage Considerations

### Single-Stage Offset
- [ ] Verify the op-amp's input offset voltage (V_os) and its drift over temperature are acceptable for the signal amplitude — the output offset is V_os × closed-loop gain, plus I_b × R_eq × gain
- [ ] If the offset is significant relative to the signal, confirm either a precision/low-offset op-amp is used, an offset nulling/trimming circuit is implemented, or AC coupling between stages removes the offset
- [ ] For rail-to-rail input op-amps: verify that input crossover distortion (transition between NPN and PNP input pairs at mid-supply) does not produce an unacceptable offset step that varies with common-mode voltage

### Multistage Amplifiers
- [ ] In multistage designs: verify the first stage's offset is the most critical — it is amplified by all subsequent stages. The total output offset = V_os1 × G1 × G2... + V_os2 × G2 × G3... + ... + V_osN × G_N. Confirm the accumulated offset does not saturate any stage or exceed the downstream circuit's input range.
- [ ] If AC coupling is used between stages, verify the coupling capacitor value and the following stage's input impedance set a high-pass corner frequency below the signal bandwidth
- [ ] Check that each AC-coupled stage's bias network is independent — a shared bias divider between stages can create unintended signal paths or crosstalk
- [ ] For high-gain multistage amplifiers: consider implementing a DC servo loop (integrator in feedback) to cancel accumulated DC offset without AC coupling capacitors
- [ ] If using dual or quad op-amp packages for multiple stages, verify that channel-to-channel offset matching is adequate — mismatched offsets between channels sharing the same package affect tracking applications

## 5. Single vs. Dual Supply Design

### Single-Supply Design
- [ ] Verify the op-amp's input common-mode range includes ground (or the negative rail) if ground-referenced signals are used; if not, confirm the signal is level-shifted or the op-amp is rail-to-rail input
- [ ] For AC-coupled single-supply circuits: verify a mid-supply reference (VCC/2) is generated by a resistor divider and bypassed to ground with a capacitor to provide an AC ground — confirm the bypass capacitor's value is low-impedance at the lowest signal frequency
- [ ] If the mid-supply reference drives multiple stages, verify the reference is buffered with an op-amp (voltage follower) to prevent loading and crosstalk between stages via the shared reference
- [ ] Confirm the op-amp's output can swing close enough to ground (or the negative rail) for the application — if true zero-volt output is needed, verify the op-amp is rail-to-rail output and that VOL is below the downstream threshold

### Dual-Supply Design
- [ ] Verify the positive and negative supply rails are symmetric and within the op-amp's rated range; confirm the ground reference (0V) is the return path for both supplies and the signal
- [ ] Check power-on sequencing — if one supply rail comes up before the other, verify the op-amp does not latch up or suffer damage; confirm that both rails reach their nominal voltage before the input signal is applied
- [ ] If a negative supply is generated from a positive supply (charge pump or inverting DC-DC), verify the generated rail's ripple and switching noise are adequately filtered before reaching the op-amp supply pins

### Design Robustness
- [ ] Verify the op-amp's PSRR (Power Supply Rejection Ratio) is adequate across frequency — supply noise couples to the output as V_out_noise = V_supply_ripple / PSRR; confirm that supply ripple does not degrade the signal below the noise floor
- [ ] For split-supply designs that must operate if one rail fails: verify the circuit fails safely (output goes to a known state, no damage to downstream circuits)

## 6. Bandwidth & Stability

- [ ] Confirm the gain-bandwidth product (GBW) is sufficient for the required closed-loop gain and signal frequency — verify the closed-loop bandwidth is at least 5-10× the maximum signal frequency
- [ ] Check phase margin — confirm the op-amp is stable with the feedback network and the load; if driving a capacitive load, verify an isolation resistor (R_iso, typically 10-100 Ω) is added between the output and the capacitor
- [ ] Verify the slew rate is adequate to reproduce the maximum output voltage swing at the highest signal frequency without distortion
- [ ] For active filters: confirm the op-amp's GBW is well above the filter cutoff frequency to avoid additional phase shift and gain error at the cutoff
- [ ] For high-speed applications: verify the op-amp's settling time to the required accuracy is within the sampling or decision window

## 7. Noise

- [ ] Verify the op-amp's input voltage noise density (nV/√Hz) and input current noise density (fA/√Hz or pA/√Hz) are acceptable for the signal amplitude and required SNR
- [ ] Confirm that the total output noise (RMS sum of op-amp voltage noise × noise gain, current noise × source impedance, and resistor thermal noise from feedback and source) is below the application's noise budget
- [ ] For low-frequency applications: check the 1/f noise corner frequency — if the signal bandwidth extends below the corner, verify the integrated noise is acceptable
- [ ] For high-source-impedance applications: verify that current noise × source impedance does not dominate the voltage noise contribution

## 8. Power Supply & Decoupling

- [ ] Confirm supply decoupling capacitors are present close to each supply pin (typically 100 nF ceramic per pin + 1-10 µF bulk per package)
- [ ] For dual-supply designs: verify both positive and negative rails are decoupled
- [ ] For battery-powered designs: verify the op-amp's quiescent current is acceptable for the power budget; confirm shutdown mode (if available) is used when the amplifier is idle

## 9. Input Protection

- [ ] Verify the absolute maximum differential input voltage is not exceeded — for op-amps with integrated back-to-back input protection diodes, the differential voltage is limited to ~0.7V; if higher differential voltage is possible, confirm external series resistors (1-10 kΩ) are added to limit current through the diodes
- [ ] If the input can exceed the supply rails, verify external clamp diodes (Schottky recommended for lower forward voltage) and series resistors are present to limit fault current
- [ ] Confirm ESD protection on inputs is adequate if the inputs are accessible from a connector or exposed to handling

## 10. Output Drive

- [ ] Verify the op-amp can drive the expected load resistance and capacitance within its output current limit — check both peak and continuous current
- [ ] If the load is capacitive (> 100 pF), confirm an isolation resistor (10-100 Ω) is added in series with the output to maintain phase margin
- [ ] Check the short-circuit current limit — confirm the op-amp's internal output protection prevents damage if the output is accidentally shorted

## 11. Special Topology

- [ ] **Transimpedance amplifier (photodiode):** verify the feedback capacitor (C_f) is selected to compensate for the input capacitance (C_in = C_photodiode + C_opamp_input) and maintain stability; confirm the op-amp has sufficiently low input bias current and voltage noise for the photodiode signal level
- [ ] **Integrator:** verify the reset mechanism (FET switch across the feedback capacitor) is correctly implemented; confirm the integrator drift from input bias current and offset voltage is acceptable over the integration period
- [ ] **Active filter:** verify the component values produce the correct cutoff frequency, Q, and filter response; confirm the op-amp's GBW is at least 10× the filter cutoff for minimal phase error at cutoff; verify the op-amp's slew rate is adequate to reproduce the maximum output swing at the cutoff frequency
- [ ] **Comparator (op-amp used as):** verify that the op-amp's slew rate and output saturation recovery time are adequate — dedicated comparators are faster and include hysteresis; if using an op-amp, confirm positive feedback is added for hysteresis to prevent oscillation during transitions
