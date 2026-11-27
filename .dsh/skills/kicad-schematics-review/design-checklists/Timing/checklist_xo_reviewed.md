# Oscillator (XO / Crystal Oscillator) Design Checklist

## 1. Type Selection

- [ ] Choose appropriate type:
  - Crystal + load caps + inverter (requires external components)
  - Full can oscillator (XO) — self-contained, no external parts
  - TCXO (Temperature Compensated) — for better temperature stability
  - VCXO (Voltage Controlled) — for frequency pulling/tuning
  - OCXO (Oven Controlled) — for best stability (laboratory/high-end)
  - MEMS oscillator — alternative to quartz, more robust to shock/vibration
- [ ] Verify output type: LVCMOS, LVDS, LVPECL, HCSL, sine wave
- [ ] Verify output frequency range
- [ ] Verify supply voltage compatibility (1.8V, 2.5V, 3.3V)

## 2. Frequency Accuracy & Stability

- [ ] Initial tolerance at 25°C (±10 ppm, ±20 ppm, ±50 ppm, etc.)
- [ ] Temperature stability over operating range (±2 ppm TCXO, ±25 ppm XO)
- [ ] Aging stability (first year, lifetime — typically ±1 to ±5 ppm/year)
- [ ] Supply voltage sensitivity (pulling)
- [ ] Load sensitivity (pulling)
- [ ] Total frequency error budget: initial tolerance + temperature + aging + pulling
- [ ] For USB: total error must be within ±0.25% (2500 ppm) for full-speed, ±0.05% (500 ppm) for high-speed
- [ ] For Ethernet: typically ±50 ppm or better

## 3. Crystal Oscillator Circuit (Discrete Crystal + IC)

### Crystal Selection
- [ ] Verify fundamental or overtone mode operation
- [ ] Check load capacitance (CL) — determines external load capacitor values
- [ ] Verify ESR (Equivalent Series Resistance) — lower is better for startup
- [ ] Check shunt capacitance (C0) — typically 5-7 pF
- [ ] Verify drive level rating — do not exceed maximum drive level (μW)
- [ ] Check motional parameters (Lm, Cm, Rm) if available

### External Component Selection
- [ ] Calculate load capacitors: CL_ext = (C1 × C2) / (C1 + C2) + C_stray
- [ ] Typical load cap values: 12 pF, 18 pF, 22 pF, 33 pF
- [ ] Use ±5% NPO/C0G capacitors for better stability
- [ ] Add series resistor R_s (typically 0-100 Ω) if drive level is too high
- [ ] Add feedback resistor R_f (typically 1 MΩ, often internal to IC) for biasing

### Startup Time
- [ ] Check oscillator startup time (typically 1-10 ms for crystals)
- [ ] Verify this meets system power-up requirements
- [ ] Ensure PLL lock time is added after oscillator is stable

## 5. Output Signal Integrity

- [ ] Verify output swing meets receiver requirements
- [ ] Add series termination resistor (typically 22-33 Ω) near the oscillator output
- [ ] For long traces, consider proper controlled-impedance routing
- [ ] Check rise/fall time compatibility with receiver
- [ ] Verify duty cycle specification (typically 45-55%)

## 6. Power Supply

- [ ] Verify oscillator supply voltage (1.8V, 2.5V, 3.3V) and tolerance
- [ ] Verify bulk capacitor per datasheet nearby
- [ ] Verify power supply filtering per datasheet (e.g., ferrite bead for clean supply)
- [ ] Verify supply current (standby vs. active)

## 7. Enable / Disable (if feature exists)

- [ ] Verify enable pin logic level and voltage tolerance
- [ ] If oscillator has tri-state enable, verify output impedance in disabled state
- [ ] Use enable pin for power saving when oscillator is not needed

## 8. Environmental

- [ ] Verify operating temperature range (-20°C to +70°C, -40°C to +85°C, etc.)
- [ ] Verify shock and vibration rating if applicable
- [ ] Check RoHS / REACH compliance
- [ ] Verify package type (SMD, through-hole) and footprint compatibility

## 9. EMI / EMC

- [ ] For high-frequency oscillators (>100 MHz), consider a metal shield can
- [ ] Verify FCC/CE harmonic emissions limits
- [ ] If using spread-spectrum clocking, verify maximum frequency deviation
