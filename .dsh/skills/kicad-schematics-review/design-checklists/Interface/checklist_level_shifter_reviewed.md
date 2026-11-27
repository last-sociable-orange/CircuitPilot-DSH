# Level Shifter / Voltage Translator Design Checklist

## 1. Device Selection

### Direction
- [ ] Verify direction type: unidirectional, bidirectional (auto-direction sensing), or direction-controlled (DIR pin)
- [ ] Verify number of channels meets bus width requirements

### Voltage Levels
- [ ] Verify VCCA (low-side) voltage range covers the low-voltage domain per datasheet
- [ ] Verify VCCB (high-side) voltage range covers the high-voltage domain per datasheet
- [ ] Check minimum voltage gap requirement (e.g., VCCB > VCCA + Vth) per datasheet

## 2. Power Supply

- [ ] Verify VCCA and VCCB voltage levels against datasheet requirements
- [ ] Verify supply sequencing requirements per datasheet (e.g., VCCA before VCCB)
- [ ] Verify decoupling capacitor values and placement per datasheet recommendations
- [ ] Check quiescent current meets system power budget (especially for battery-powered designs)
- [ ] Verify VCCA and VCCB voltages are stable before enabling translation per datasheet

## 3. Electrical Characteristics

### Output Drive
- [ ] Verify output drive strength on each side meets load requirements per datasheet
- [ ] For direction-controlled: verify VOH/VOL at expected load current per datasheet
- [ ] For auto-direction: verify output impedance and drive capability per datasheet

### Input Thresholds
- [ ] Verify VIH/VIL on A-side are compatible with low-voltage driver
- [ ] Verify VIH/VIL on B-side are compatible with high-voltage driver
- [ ] For auto-direction: verify input threshold tracking per datasheet

### Propagation Delay
- [ ] Verify propagation delay meets system timing budget per datasheet
- [ ] For auto-direction: verify propagation delay includes edge-rate acceleration time

### Edge Rate / Slew Rate
- [ ] Verify maximum data rate meets system requirements per datasheet
- [ ] For open-drain (I2C): verify pull-up resistor values provide adequate edge rates on both sides

## 4. Pin Configuration

### Direction Control (if applicable)
- [ ] Verify DIR pin is driven to valid logic level (not floating)
- [ ] Verify DIR setup time: DIR must be stable before data changes per datasheet

### Output Enable (OE)
- [ ] Verify OE pin polarity (active-high or active-low) per datasheet
- [ ] Verify OE connection (tied to supply for always-enabled, or GPIO-controlled)
- [ ] Verify OE pull-up/down requirements per datasheet

### I2C-Specific (auto-direction)
- [ ] Verify external pull-up resistors are present on both A and B sides
- [ ] Verify pull-up resistor values are calculated for bus capacitance and speed on each side
- [ ] Verify pull-up voltage source: A-side to VCCA, B-side to VCCB
- [ ] If using TXS series, verify internal pull-ups are adequate or add external pull-ups

## 5. Application-Specific Considerations

### I2C Bus Translation
- [ ] Verify translator supports I2C speed (standard, fast, fast+) per datasheet
- [ ] Verify pull-up resistors are sized for target speed on each side

### SPI Translation
- [ ] Verify direction configuration for each SPI signal (MOSI, MISO, SCK, CS)
- [ ] Verify maximum SPI frequency vs. translator propagation delay per datasheet

### UART Translation
- [ ] Verify direction configuration for TX and RX signals
- [ ] For RS-232: verify level shifter (e.g., MAX3232) is rated for RS-232 voltage levels

### SD Card / SDIO Translation
- [ ] Verify translator supports bidirectional 4-bit data bus, command, and clock
- [ ] Verify propagation delay allows SDIO timing at target speed per datasheet

### Parallel Bus Translation
- [ ] Verify bus width matches controller and peripheral
- [ ] Verify DIR pins are configured correctly for data flow direction
- [ ] Verify setup/hold times across voltage domains per datasheet

## 6. Unused Pins

- [ ] Verify unused channels are handled per datasheet recommendations (leave floating, tie to GND/VCC, or disable via OE)

## 7. Thermal

- [ ] Verify power dissipation is within device limits
- [ ] Check if device has thermal shutdown feature (if required by application)
