# Voltage Supervisor / Reset IC Design Checklist

## 1. Device Selection

### Monitoring Type

- [ ] **Single voltage monitor:** monitors one rail, asserts reset when below threshold
- [ ] **Multi-voltage monitor:** monitors 2-4 voltage rails in one package
- [ ] **Sequencer:** monitors/enables multiple rails in a sequence
- [ ] **Window watchdog:** monitors for both under- and over-voltage
- [ ] **Integrated watchdog timer:** adds watchdog monitoring to voltage supervisor

### Reset Threshold

- [ ] Verify threshold voltage matches the monitored rail voltage (fixed threshold supervisors) or is correctly set by the resistor divider (adjustable supervisors)
- [ ] Confirm threshold accuracy (tolerance) is sufficient for the application
- [ ] Check threshold hysteresis (difference between assert and release) is adequate to prevent oscillation near the threshold
- [ ] For adjustable supervisors: verify resistor divider values produce the correct threshold per the supervisory IC's V_ref

### Reset Output Type

- [ ] **Active-low, open-drain (most common):** requires pull-up resistor
- [ ] **Active-low, push-pull:** drives low on reset, no pull-up needed
- [ ] **Active-high, push-pull:** drives high on reset
- [ ] Verify output voltage tolerance meets MCU/MPU reset input requirements

## 2. Timing

### Reset Delay (t_RP)

- [ ] Verify reset assertion and release delays are appropriate for the system — assertion should be fast enough to catch glitches, release long enough for supply stabilization
- [ ] Check if the supervisor has pin-programmable delay and whether it is configured correctly
- [ ] Confirm watchdog timeout period is compatible with the system watchdog service interval

### Manual Reset (MR)

- [ ] Verify MR pin connection (push-button or MCU GPIO) and any required pull-up resistor
- [ ] Confirm debounce time (internal or external) is adequate for the switch type
- [ ] Check edge-triggered vs. level-triggered behavior matches the intended use

## 3. Voltage Monitoring

### Primary Monitored Rail

- [ ] Connect VDD to the rail being monitored
- [ ] For supervisor with fixed threshold: connect directly
- [ ] For supervisor with adjustable threshold: use resistor divider
- [ ] Verify supply decoupling per datasheet (noisy supply can cause false resets)

### Secondary Rails (Multi-Voltage Supervisors)

- [ ] Monitor additional rails (e.g., 1.2V core, 1.8V, 2.5V, 3.3V)
- [ ] Each input has fixed or adjustable threshold
- [ ] All monitored rails must be valid for reset to release
- [ ] Verify sequencing requirements (if any rail order matters)

### Power-Fail Input (PFI)

- [ ] Verify PFI threshold is set (via resistor divider) to trigger before the main supply drops below the regulator dropout voltage
- [ ] Confirm PFO output is connected to an MCU interrupt or other early-warning logic
- [ ] Check that the PFI resistor divider is connected to the appropriate supply (unregulated input or battery voltage)

## 4. Watchdog Timer (if applicable)

### Watchdog Input (WDI)

- [ ] Connect to MCU/MPU GPIO toggled by firmware
- [ ] Watchdog timeout: t_WD (100 ms to 10 seconds typical)
- [ ] WDI toggling: must occur within t_WD window
- [ ] Watchdog output: separate or combined with reset output

### Watchdog Behavior

- [ ] Normal: WDI toggled before timeout → timer resets
- [ ] Timeout: watchdog asserts reset or NMI
- [ ] Disable: some supervisors allow watchdog disable via pin or during startup
- [ ] Open window: WDI must not toggle too fast (prevents stuck-low failure)

## 5. Power Sequencing (if applicable)

### Enable Outputs

- [ ] Some supervisors provide enable outputs (EN_OUT) for sequencing
- [ ] EN_OUT goes high after monitored input reaches threshold + t_delay
- [ ] Daisy-chain enable outputs for sequential rail startup
- [ ] Verify EN_OUT voltage and drive capability (often open-drain)

## 6. Applications

### MCU/MPU Reset

- [ ] Verify reset output is connected to the MCU reset pin and the output type (open-drain with pull-up vs. push-pull) is compatible
- [ ] Confirm supervisor and MCU supply voltages are compatible (same rail or level-shifted)

### Power-Fail Detection

- [ ] Verify PFI threshold voltage (set by resistor divider from the appropriate supply) triggers before the main regulator drops out
- [ ] Confirm PFO output is connected to an MCU interrupt or logic input for early-warning handling

## 8. Noise Immunity

- [ ] Verify the supervisor's glitch rejection (inherent delay + hysteresis) is sufficient to prevent false resets from supply noise at the operating frequency
- [ ] If a noise filter capacitor pin is available, verify the capacitor value is set appropriately per datasheet
