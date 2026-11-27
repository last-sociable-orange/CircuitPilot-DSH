# Power Distribution Switch / Load Driver Design Checklist

## 1. Selection Verification

- [ ] Confirm switch type (high-side, low-side, load switch, power distribution switch, USB power switch, hot-swap controller, eFuse, ideal ORing controller) is appropriate for the application
- [ ] Verify input voltage range covers all operating conditions, including transients
- [ ] Confirm continuous current rating exceeds the maximum load current with margin
- [ ] Check on-resistance (R_DS_ON) — verify the voltage drop at full load (I_load × R_DS_ON) is acceptable for the downstream circuit
- [ ] Verify quiescent current and shutdown current meet the system power budget

## 2. Protection Features

- [ ] Verify overcurrent protection (OCP) threshold is above the maximum load current but low enough to protect the wiring and load
- [ ] Confirm the current limit response mode (auto-retry vs. latch-off) is appropriate for the application
- [ ] If the switch has a fault flag output, verify it is connected to the system controller and handled correctly
- [ ] Check thermal shutdown threshold — verify the switch turns off before exceeding its thermal limits, and that recovery behavior (hysteresis) is acceptable
- [ ] If thermal regulation (current foldback) is supported, verify the behavior is compatible with the load
- [ ] Confirm reverse current blocking is present if back-feeding from output to input is possible
- [ ] For automotive/industrial designs: verify undervoltage lockout (UVLO) threshold prevents operation below V_in_min
- [ ] If output discharge is present, confirm the discharge behavior (pull output to GND when disabled) is appropriate for the load

## 3. Inrush Current

- [ ] Verify the switch's slew-rate controlled turn-on produces an inrush current that does not trigger OCP and stays within the input supply's capability
- [ ] If the switch has a programmable soft-start, confirm the capacitor or configuration produces the correct turn-on time
- [ ] Check that the load capacitance does not cause excessive inrush that could sag the input supply

## 4. Thermal Verification

- [ ] Calculate conduction loss at maximum load current (I_load² × R_DS_ON); verify junction temperature stays within the rated range at maximum ambient
- [ ] Account for R_DS_ON increase at operating temperature (MOSFET R_DS_ON rises ~0.4-0.5%/°C)
- [ ] Confirm PCB copper area and any heatsinking are adequate for the calculated power dissipation

## 5. Enable Control

- [ ] Verify enable threshold voltages are compatible with the control signal (MCU GPIO, voltage supervisor, etc.)
- [ ] Confirm enable polarity (active-high vs. active-low) matches the driving signal
- [ ] Check that the enable pin is not left floating (pull-up or pull-down as needed)

## 6. Transient / Inductive Load Handling

- [ ] If the load is inductive (relay, solenoid, motor), verify a flyback diode is placed across the load
- [ ] Check output voltage overshoot during fast turn-off — confirm it does not exceed the switch's abs-max rating
- [ ] Verify input capacitance is sufficient to prevent supply sag during turn-on inrush

## 7. Hot-Swap Controller (if applicable)

- [ ] Verify the external FET's Safe Operating Area (SOA) is adequate during startup (the highest stress point)
- [ ] Confirm the programmable current limit and power-good output are configured correctly
- [ ] Check that the circuit breaker functionality (latch-off vs. auto-retry) is appropriate

## 8. eFuse (if applicable)

- [ ] Confirm the adjustable current limit threshold is set above the maximum load current with margin, and that its accuracy (±%) is acceptable
- [ ] Verify the input voltage range and overvoltage protection (OVP) clamp/ cutoff voltage are compatible with the power source — confirm the eFuse protects downstream circuitry from overvoltage events
- [ ] Check reverse current blocking and reverse voltage protection — verify the eFuse prevents back-feed from output to input and handles reversed input polarity
- [ ] Confirm fast-trip (short-circuit) response time is fast enough to protect the wiring and load; verify the response mode (latch-off vs. auto-retry) is appropriate
- [ ] Verify the power-good and fault flag outputs (if present) are connected to the system controller
- [ ] If the eFuse has a programmable slew rate, confirm the turn-on time is set to limit inrush current without tripping the current limit
- [ ] Verify the eFuse's thermal shutdown threshold and recovery behavior are compatible with the operating environment
- [ ] For hot-plug applications: verify the eFuse's output discharge behavior (pull-down when disabled) is appropriate for the load

## 9. Ideal ORing Controller (if applicable)

- [ ] Confirm the controller topology (N-channel MOSFET + charge pump vs. P-channel MOSFET) matches the input voltage range and forward current requirements
- [ ] Verify the forward voltage drop across the MOSFET in the ON state is acceptably low (typically < 1-10 mV at rated current) to minimize conduction loss
- [ ] Check reverse current blocking — confirm the controller turns off the FET fast enough when V_out > V_in to prevent back-feeding between redundant power sources
- [ ] Verify the controller handles cross-conduction between paralleled inputs — confirm it can transition between sources without momentary shoot-through
- [ ] For dual-supply ORing (e.g., adapter + battery, PoE + auxiliary): confirm the priority logic (if any) selects the correct source per system requirements
- [ ] Verify the controller can survive and protect against an input short-circuit on one rail without disrupting the other rail
- [ ] Check the gate drive voltage (charge pump output) is sufficient to fully enhance the external N-MOSFET at minimum V_in
- [ ] If the ORing controller has a status/fault output, verify it is connected to the system controller
- [ ] For high-current ORing: verify the external MOSFET's R_DS_ON and package are adequate for the conduction loss, and that the MOSFET SOA covers startup and fault conditions
- [ ] If the ORing controller supports active balancing (current sharing) between paralleled inputs, verify the sharing accuracy is adequate for the total load
