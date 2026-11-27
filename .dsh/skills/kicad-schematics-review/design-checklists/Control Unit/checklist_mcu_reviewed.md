# Microcontroller (MCU) Design Checklist

## 1. Power

### Power Rails
- [ ] Identify all required voltage rails (core, I/O, analog, PLL, RTC, USB, etc.)
- [ ] Verify voltage tolerance for each rail (±5%, ±3%, ±1% as required)
- [ ] Confirm current requirements for each rail (peak, average, sleep)
- [ ] Check if any rails have a specific power-up sequence requirement
- [ ] Verify BOR (Brown-Out Reset) threshold matches supply voltage tolerances

### Power Consumption & Budget
- [ ] Calculate total system power budget for all MCU rails
- [ ] Review active-mode current consumption at target clock speed
- [ ] Review sleep/standby/deep-sleep mode currents
- [ ] Account for peripheral power consumption (ADC, DAC, comparators, USB, etc.)
- [ ] Consider power during flash programming/erase cycles (often higher)

### Power-Up/Down Sequencing
- [ ] Check if core and I/O rails require specific sequencing (e.g., core before I/O)
- [ ] Verify reset pin timing relative to supply voltage rise time
- [ ] Check for any supply brown-out detection requirements
- [ ] Review POR (Power-On Reset) timing specifications
- [ ] Determine if an external voltage supervisor is needed

### Decoupling
- [ ] Verify bulk capacitance values per datasheet for each power domain (core, I/O, analog, etc.)
- [ ] Verify capacitor type (e.g., low-ESL/ESR) per datasheet for high-frequency decoupling
- [ ] Verify capacitor voltage derating requirements per datasheet and application
- [ ] Verify filtering recommendations for analog supply (AVDD, VDDA) per datasheet
- [ ] Review datasheet grounding guidance; separate analog and digital planes where recommended

### Unused Power Pins
- [ ] Review datasheet requirements for all VDD/VSS pin connections — some may be optional
- [ ] Check datasheet for proper termination of analog supply pins (AVDD, VDDA)
- [ ] Verify VREF+/- pin connection requirements per datasheet
- [ ] Check if any power pins need specific filtering or external components per datasheet

## 2. Clocking

### External Oscillator / Crystal
- [ ] Verify load capacitance (CL) and select external capacitors accordingly
- [ ] Check ESR (Equivalent Series Resistance) compatibility with MCU oscillator driver
- [ ] Confirm drive level does not exceed crystal rating
- [ ] Add series resistor if needed for drive level limiting

### Internal Oscillator
- [ ] Verify accuracy requirements vs. internal RC oscillator tolerance
- [ ] Check temperature drift specifications
- [ ] Confirm calibration procedure if required

## 3. GPIO

### Pin Multiplexing (Pin Mux)
- [ ] Assign functional peripherals in groups — function pins must be in the same port/group
- [ ] Verify no pin is assigned to more than one function
- [ ] Check alternate function mapping tables in datasheet carefully
- [ ] Create a pin mux table for all pin mux settings in the schematic
- [ ] Verify special function pins (e.g., SWD/JTAG, boot pins) are not used by other peripherals
- [ ] Check if certain peripherals require specific pins (e.g., USB DP/DM are fixed)

### Unused Pin Handling
- [ ] Configure unused GPIOs as inputs with pull-up/pull-down (or analog, floating disabled)
- [ ] Do not leave unused inputs floating — they can oscillate and increase power consumption
- [ ] For outputs that are unused, either leave them high-impedance or drive to a known state
- [ ] Check datasheet recommendations for unused pin termination

### Reset and Power-Up Default States
- [ ] Review default pin state after reset (input floating, pull-up/down, alternate function)
- [ ] Ensure default states do not cause unintended activation of external circuitry
- [ ] Check if any pins have a "weak" default state that could cause issues during power-up
- [ ] Add external pull-up/pull-down if default state conflicts with system requirements

### GPIO Voltage Level Matching
- [ ] Verify VDDIO voltage matches external device logic levels (1.8V, 3.3V, 5V)
- [ ] Check if level shifters are used when voltage levels don't match
- [ ] Verify VIH/VIL thresholds are compatible with driving device
- [ ] Check output VOL/VOH levels meet receiving device requirements
- [ ] Consider open-drain configuration with external pull-up for mixed-voltage buses (I2C)

### GPIO Current Drive
- [ ] Verify total current sink/source across all GPIOs does not exceed maximum per port/package
- [ ] Check individual pin output current capability (typically 4-20 mA)
- [ ] Add series resistors for LED driving or high-current loads
- [ ] Review total package power dissipation from GPIO currents

## 4. Special Functions

### Analog-to-Digital Converter (ADC)
- [ ] Verify ADC resolution, sampling rate, and conversion time requirements
- [ ] Check input impedance — may require an external buffer amplifier
- [ ] Confirm full-scale voltage range (internal VREF, external VREF, or supply)
- [ ] Add anti-aliasing filter (RC low-pass) on each analog input
- [ ] Verify ADC input voltage must not exceed VREF+ or go below VREF-

### Digital-to-Analog Converter (DAC)
- [ ] Verify resolution, settling time, and output drive capability
- [ ] Check output impedance — may require an external buffer
- [ ] Add output filtering (RC or active filter) if needed
- [ ] Confirm output voltage range and reference selection
- [ ] Verify capacitive load drive capability

### Pulse Width Modulation (PWM)
- [ ] Verify timer resolution, frequency range, and duty cycle capability
- [ ] Add dead-time insertion if driving half/full bridges
- [ ] Verify complementary PWM output availability and programmable dead-time
- [ ] Check fault/trip input functionality for emergency shutdown
- [ ] Consider adding RC filters if using PWM as a crude DAC

### USB
- [ ] Verify internal USB PHY compatibility (full-speed vs. high-speed)
- [ ] Route DP/DM as 90 Ω differential pair
- [ ] Verify VBUS detection pin and overcurrent protection
- [ ] Check for external oscillator accuracy requirements (USB FS: ±0.25%, HS: ±0.05%)

### I2C
- [ ] Verify bus voltage level (determines pull-up resistor value)
- [ ] Calculate pull-up resistor value based on bus capacitance and speed (standard/fast/fast+)
- [ ] Check if internal pull-ups are sufficient or external ones are needed (usually external)
- [ ] Confirm address uniqueness on the bus (7-bit or 10-bit)
- [ ] Add series resistors (optional, for slew rate limiting and ESD protection)
- [ ] Check voltage level compatibility — use level translator if voltages differ

### SPI
- [ ] Check maximum SPI clock frequency vs. slave device
- [ ] Consider series termination resistors (22-33 Ω) for clock line
- [ ] Verify chip select (CS/SS) signal control polarity and default pull-up/pull-down
- [ ] Check if Quad-SPI or dual-SPI is needed for higher throughput

### UART
- [ ] Verify UART TX/RX, RTS/CTS direction between two devices
- [ ] Verify RS-232 level translation if required (use MAX3232 or similar)

### CAN / CAN-FD
- [ ] Verify CAN transceiver compatibility (3.3V or 5V)
- [ ] Add common-mode choke on CANH/CANL lines
- [ ] Place termination resistor (120 Ω) at both ends of the bus
- [ ] Add ESD protection on CAN bus lines

### Comparator
- [ ] Verify input voltage range and reference voltage
- [ ] Check hysteresis settings (internal or external)

### External Interrupts
- [ ] Verify interrupt trigger type (rising, falling, both edges, level)
- [ ] Check interrupt priority and nested interrupt support
- [ ] Add external debounce circuitry if needed (RC filter or Schmitt trigger)
- [ ] Confirm no floating interrupt pins

## 5. Debug / Programming

### Debug Interface (SWD/JTAG)
- [ ] Route SWCLK/SWDIO or JTAG signals to a header
- [ ] Verify if there is mode selection for different debug interfaces, e.g., JTAG mode, SWD mode, or proprietary mode
- [ ] Verify external pull-up/pull-down on SWDIO/SWCLK as per MCU requirements
- [ ] Consider VTREF pin connection for voltage reference matching
- [ ] Ensure debug interface is accessible in the final product (or disable for production)

### Boot Configuration
- [ ] Verify boot pin strapping (BOOT0, BOOT1, etc.) for desired boot mode
- [ ] Verify boot option pin strapping (e.g. boot option pins to override fuse settings) 
- [ ] Check if boot pins have internal pull-up/down and if external resistors are needed
- [ ] Document boot mode selection in schematic

## 6. Thermal

- [ ] Calculate total power dissipation (P = I × V) for worst-case conditions
- [ ] Verify junction temperature (Tj) stays within spec (-40°C to +85°C or +125°C)
- [ ] Check thermal resistance (θJA, θJC) for the package
- [ ] Ensure adequate airflow or heatsinking for high-power applications

## 7. Regulatory & Reliability

- [ ] Add ESD protection on all external connections (I/O, USB, communication lines)
- [ ] Add EMI filters on all external high speed buses and digital IOs
- [ ] Verify latch-up immunity (check datasheet latch-up test levels)
- [ ] Consider external watchdog timer (or use internal WDT with proper configuration)
- [ ] Add RC filter on reset pin to prevent noise-induced resets
- [ ] Verify FCC/CE emissions requirements — may need shielding or ferrite beads
- [ ] Review safety-critical features (e.g., clock security system, memory ECC, BIST)
