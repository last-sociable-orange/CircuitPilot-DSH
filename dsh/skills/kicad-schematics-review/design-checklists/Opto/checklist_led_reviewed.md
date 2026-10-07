# LED (Optoelectronics — Discrete LED) Design Checklist

## 1. LED Type Selection

- [ ] Verify LED color (red, green, blue, white, UV, IR) meets application requirements per datasheet
- [ ] Verify white LED type (phosphor-converted vs. RGB mixing) is appropriate
- [ ] Verify power category (high-power 1-5W, mid-power 0.1-1W, low-power 2-20 mA) meets application requirements
- [ ] Verify package type (SMD, through-hole, Star PCB, addressable RGB) fits PCB and assembly constraints

### Key Specifications
- [ ] Verify forward voltage (V_f) at operating current per datasheet
- [ ] Verify forward current rating: test current and maximum current per datasheet
- [ ] Verify thermal resistance (R_θJS) per datasheet

## 2. Current Limiting

### Series Resistor
- [ ] Verify resistor value calculated for target forward current per LED datasheet: (V_supply − V_f − V_drop) / I_f
- [ ] Verify resistor power rating is adequate: P = I_f² × R — check derating at operating temperature
- [ ] For multiple LEDs in series: verify resistor value accounts for sum of forward voltages
- [ ] Verify resistor tolerance (±1% or ±5%) is adequate for current accuracy

### Constant Current Source
- [ ] For high-power LEDs: verify constant current driver (buck/boost LED driver) is used
- [ ] For indicator LEDs: verify constant current configuration is adequate
- [ ] For arrays or high-current (> 100 mA): verify dedicated LED driver IC is used

## 3. LED Arrays

- [ ] For series connection: verify total forward voltage is within driver compliance range
- [ ] For parallel connection: verify each branch has its own current limit (resistor/driver)
- [ ] For parallel connection: verify V_f mismatch is acceptable or use matched LEDs
- [ ] For series-parallel: verify each series string has its own current regulation

## 4. Thermal Management

- [ ] Verify junction temperature (T_j) is within maximum rating per datasheet at worst-case ambient
- [ ] For high-power LEDs (1W+): verify heatsink or MCPCB (Metal Core PCB) is used
- [ ] Verify derating: reduce I_f at high ambient temperature per datasheet curves
- [ ] Verify maximum T_j is not exceeded at worst-case operating conditions per datasheet

## 6. PWM / Dimming

- [ ] Verify PWM frequency > 200 Hz to avoid visible flicker
- [ ] Verify minimum pulse width allows LED to fully turn on/off per datasheet

## 7. Protection

- [ ] Verify reverse voltage protection: add reverse parallel diode if LED may see reverse bias
- [ ] If LED connects to external connector: verify ESD protection (TVS diode) on traces
- [ ] Verify inrush current: check that cold-start forward voltage characteristics do not cause overcurrent per datasheet
