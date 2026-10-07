# I/O Expander Design Checklist

## 1. Device Selection

- [ ] Verify interface type (I2C or SPI) is compatible with host controller
- [ ] Verify number of GPIO pins (4, 8, 16, 24, 32, 40) meets application requirements
- [ ] For I2C: verify I2C address configuration — check available addresses for bus topology
- [ ] For SPI: if multiple devices, verify daisy-chain or separate CS line configuration
- [ ] Verify port configuration (push-pull vs. open-drain outputs; input only vs. bidirectional) meets application requirements

## 2. Power Supply

### Supply Voltage
- [ ] Verify VDD operating range matches available supply rail per datasheet
- [ ] If supply voltage differs from MCU/MPU I/O voltage: verify level compatibility per datasheet

### Decoupling
- [ ] Verify bulk capacitor values per datasheet

### Supply Current
- [ ] Verify quiescent current (standby vs. active) meets system power budget per datasheet
- [ ] Verify total package current limit is not exceeded when all pins are active
- [ ] For battery-powered designs: verify low-power or standby mode current per datasheet

## 3. I/O Pins

### Pin Configuration
- [ ] Verify each pin can be configured as input or output per datasheet
- [ ] Check if input pins can generate interrupts (edge-triggered, level-triggered) per application needs
- [ ] Check if outputs are push-pull or open-drain (configurable) per datasheet

### Pin Voltage
- [ ] Verify VDD determines output HIGH voltage (VOH ≈ VDD) per datasheet
- [ ] If level translation needed: verify I/O expander supports different voltages on each side per datasheet
- [ ] Check if pins are 5V-tolerant if interfacing with 5V logic while running at lower voltage per datasheet

### Output Current
- [ ] Verify per-pin sink/source current rating meets load requirements per datasheet
- [ ] Verify total package current limit is not exceeded per datasheet
- [ ] For driving LEDs: verify series resistors are present per LED current requirements

### Input Features
- [ ] Verify pull-up/pull-down resistors: internal (programmable) or external per application
- [ ] Verify interrupt capability: route INT output to MCU interrupt pin per datasheet
- [ ] If open-drain INT output: verify external pull-up resistor value per datasheet
- [ ] Check input polarity inversion support if needed per datasheet
- [ ] Check debounce filter support if needed per datasheet

### Output Features
- [ ] Verify output latch read-modify-write safety per datasheet
- [ ] Check output polarity inversion support if needed per datasheet

## 4. Communication Interface

### I2C
- [ ] Verify slave address configuration via address pins (A0, A1, A2) — tied to VDD/GND
- [ ] Verify pull-up resistor values are correct for target bus speed and bus capacitance
- [ ] Check maximum bus speed (standard, fast, fast+) per datasheet
- [ ] Verify I2C protocol support (clock stretching, repeated START) per datasheet
- [ ] If 1.8V I2C bus: verify level translation or device compatibility per datasheet

### SPI
- [ ] Verify SPI mode (CPOL/CPHA) matches host controller per datasheet
- [ ] Check maximum SPI clock frequency per datasheet
- [ ] Verify CS, SCK, MOSI, MISO signal routing with signal integrity
- [ ] If series termination on SCK used: verify value per signal integrity requirements
- [ ] For multiple SPI devices: verify separate CS lines or daisy-chain configuration

## 5. Interrupt Handling

- [ ] Verify INT output is connected to MCU GPIO with interrupt capability
- [ ] For open-drain INT: verify pull-up resistor value per datasheet
- [ ] Verify interrupt polarity configuration (active-low, active-high) per datasheet

## 6. Reset / Power-On Defaults

- [ ] Verify default pin state after power-up per datasheet
- [ ] Check if internal pull-ups are enabled by default per datasheet
- [ ] If default state is problematic: verify external pull-up/down resistors are used
- [ ] Verify pins are configured immediately after power-up in initialization code

## 7. Daisy-Chaining (SPI)

- [ ] For daisy-chain capable expanders: verify chain length per datasheet
- [ ] Verify data propagation delay is acceptable for application
- [ ] Verify no contention on MISO line per datasheet
