# Microprocessor (MPU) Design Checklist

## 1. Power

### Power Rails
- [ ] Identify all voltage rails: core (VDD_CORE), I/O (VDDIO), DDR, PLL, analog, RTC, etc.
- [ ] Verify voltage tolerances — core rails typically ±3%, I/O rails ±5%
- [ ] Confirm current requirements per rail (peak, average, sleep) — can exceed several amps for high-performance MPUs
- [ ] Check for dedicated DDR termination voltage (VTT) and reference voltage (VREF)
- [ ] Verify if any rails need low-noise requirements (PLL, analog, transceiver)
- [ ] Check if any rails have a specific power-up sequence requirement
- [ ] Verify BOR (Brown-Out Reset) threshold if MPU has internal BOR, or determine if external supervisor is needed

### Power Management IC (PMIC) / DC-DC
- [ ] Select PMIC or discrete regulators that meet all voltage/current/sequencing requirements
- [ ] Verify power-up and power-down sequencing order per datasheet
- [ ] Check if PMIC has configurable sequencing (GPIO-controlled enable, power-good signals)
- [ ] Ensure each rail has adequate output capacitance for transient response
- [ ] Verify PMIC supports all sleep/standby states of the MPU

### Power Consumption & Budget
- [ ] Calculate worst-case power consumption (thermal design power — TDP)
- [ ] Review active, idle, sleep, and deep-sleep mode currents
- [ ] Account for DDR memory power consumption
- [ ] Consider peripheral power (USB, Ethernet, GPU, PCIe, display, camera, etc.)
- [ ] Account for on-chip peripheral power consumption (ADC, DAC, CAN, I2C, SPI, etc.)
- [ ] Design thermal solution based on TDP

### Power-Up/Down Sequencing
- [ ] Verify exact voltage rail sequencing (timing diagrams in datasheet)
- [ ] Check if core rail must come up before I/O rails (or vice versa)
- [ ] Verify reset timing with respect to supply stabilization
- [ ] Check for any required delay between rail assertions
- [ ] Ensure all rails reach their operating voltage before releasing reset
- [ ] Review Power-On Reset (POR) timing specifications
- [ ] Check for any supply brown-out detection requirements
- [ ] Determine if an external voltage supervisor is needed

### Decoupling
- [ ] Verify bulk capacitance values per datasheet; distribute around the board
- [ ] Verify capacitor type per datasheet (e.g., low-ESR MLCCs) for high-frequency decoupling
- [ ] Verify capacitor voltage derating requirements per datasheet and application (DC bias reduces capacitance)
- [ ] Add decoupling specific to each power domain per datasheet (core, I/O, PLL, DDR, analog)
- [ ] Verify filtering recommendations for analog supplies (VDDA, VCCA, PLL) per datasheet
- [ ] Review datasheet grounding guidance; separate analog and digital planes where recommended
- [ ] Follow manufacturer's recommended decoupling capacitor layout
- [ ] Consider using power integrity simulation for complex designs

### Unused Power Pins
- [ ] Review datasheet requirements for all power/ground pin connections — some may be optional
- [ ] Verify datasheet guidance for PLL and analog supply pins when unused
- [ ] Verify VREF+/- pin connection requirements per datasheet
- [ ] Check if any power pins need specific filtering or external components per datasheet
- [ ] Verify proper termination of unused DDR power pins per datasheet

## 2. Clocking

### Main Oscillator / Crystal
- [ ] Verify crystal frequency and load capacitance (CL); select external load capacitors accordingly
- [ ] Check ESR (Equivalent Series Resistance) compatibility with MPU oscillator driver
- [ ] Confirm drive level does not exceed crystal rating; add series resistor if needed for drive level limiting
- [ ] Select appropriate oscillator output type (LVCMOS, sine wave, differential)
- [ ] Verify PLL input frequency range is compatible with oscillator output
- [ ] Add termination resistors for high-frequency clock signals

### PLLs (Multiple)
- [ ] Verify each PLL's input frequency range, output frequency, and jitter specifications
- [ ] Check PLL loop filter component values (internal or external)
- [ ] Confirm PLL lock time and reset behavior
- [ ] Ensure PLL supplies have adequate filtering (ferrite bead + capacitor)
- [ ] Verify clock tree timing for all subsystems (DDR, PCIe, USB, Ethernet, display)

### DDR Memory Clock
- [ ] Match DDR clock trace length to within spec (typically ±0.5 mm of other DDR signals)
- [ ] Terminate DDR clock with appropriate resistor network (if required)
- [ ] Verify DDR clock frequency and jitter compliance

## 3. DDR Memory Interface

- [ ] Verify DDR type: DDR3, DDR4, LPDDR4, DDR5, etc. — MPU compatibility
- [ ] Match DQ, DQS, and clock trace lengths across all byte lanes
- [ ] Implement fly-by topology for address/command/control signals
- [ ] Place VTT termination resistors at the end of address/command lines
- [ ] Separate VDD, VDDQ, VTT, and VREF planes properly
- [ ] Add series termination for clock and strobe signals as needed
- [ ] Verify ODT (On-Die Termination) settings based on topology
- [ ] Follow layout guidelines from MPU and DDR vendor application notes

## 4. High-Speed Interfaces

### Gigabit Ethernet
- [ ] Verify RGMII/ RMII timing and voltage levels with PHY
- [ ] Route differential TX/RX pairs with 100 Ω differential impedance
- [ ] Add magnetics: transformer + common-mode choke in Ethernet path
- [ ] Separate Ethernet ground (chassis ground) from digital ground
- [ ] Add 25 MHz crystal/oscillator for PHY (or use MPU-provided clock)

### PCI Express
- [ ] Route differential TX/RX pairs with 85 Ω or 100 Ω differential impedance
- [ ] Match TX and RX trace lengths within each lane
- [ ] Keep AC coupling capacitors (100 nF typical) on TX lines near transmitter
- [ ] Follow PCIe lane polarity swapping rules if needed
- [ ] Check PCIe reference clock routing requirements (100 MHz differential)
- [ ] Verify link training and lane reversal configuration

### USB (USB 2.0 / USB 3.0)
- [ ] Verify internal USB PHY compatibility (full-speed, high-speed, or super-speed)
- [ ] Verify VBUS detection and overcurrent protection
- [ ] Route USB 2.0 DP/DM as 90 Ω differential pair
- [ ] Route USB 3.0 SSTX/SSRX as 90 Ω differential pairs
- [ ] Add ESD protection near USB connector
- [ ] Place series termination resistors (if required by MPU)
- [ ] Check for external oscillator accuracy requirements (USB FS: ±0.25%, HS: ±0.05%)

### Display Interfaces (HDMI, MIPI DSI, LVDS, eDP)
- [ ] Add ESD protection near display connector
- [ ] Verify signal swing and common-mode voltage compatibility
- [ ] Check for required AC coupling capacitors (PCIe, MIPI DSI)
- [ ] Follow cable length and skew limitations

### Camera Interface (MIPI CSI)
- [ ] Route differential data and clock lanes with 100 Ω impedance
- [ ] Match skew between clock and data lanes
- [ ] Add ESD protection near camera connector
- [ ] Verify MIPI D-PHY voltage levels and termination

## 5. GPIO

### Pin Multiplexing (Pin Mux)
- [ ] Assign functional peripherals in groups — function pins must be in the same I/O bank/port
- [ ] Verify no pin is assigned to more than one function (check entire pin mux table)
- [ ] Review the full pin mux table in the datasheet/reference manual against all enabled peripherals
- [ ] Create a complete pin mux table in the schematic documenting every pin's selected function
- [ ] Verify special function pins (JTAG/SWD, boot pins, Ethernet, USB, DDR, etc.) are not reassigned to other peripherals
- [ ] Check if certain peripherals require fixed pins (e.g., USB DP/DM, DDR interface, Ethernet RGMII)
- [ ] Account for pin mux conflicts with high-speed interface signal groups (e.g., CSI, DSI, PCIe)

### Unused Pin Handling
- [ ] Configure unused GPIOs as inputs with pull-up/pull-down (or analog input with disabled digital path)
- [ ] Do not leave unused inputs floating — they can oscillate and increase power consumption
- [ ] For unused output-capable pins, either leave them high-impedance or drive to a known state
- [ ] Check datasheet recommendations for unused pin termination (including any special-function pins not used)
- [ ] Verify no unused pins have weak internal pull states that could cause issues during power-up

### Reset and Power-Up Default States
- [ ] Review default pin state after reset (input floating, pull-up/down, alternate function, or high-Z)
- [ ] Ensure default states do not cause unintended activation of external circuitry during power-up/boot
- [ ] Check if any pins have a "weak" default pull that could conflict with external devices (e.g., pull-down on a bus that floats high)
- [ ] Add external pull-up/pull-down resistors if default state conflicts with system requirements
- [ ] Verify that critical control pins (enable, reset, power-good) are in a safe default state until software takes over

### GPIO Voltage Level Matching
- [ ] Verify VDDIO voltage for each I/O bank matches the external device logic levels (1.8 V, 2.5 V, 3.3 V)
- [ ] Check if level shifters are required when interfacing between different voltage domains
- [ ] Verify VIH/VIL thresholds are compatible with the driving device on inputs
- [ ] Check output VOL/VOH levels meet receiving device requirements under specified load
- [ ] Consider open-drain configuration with external pull-up for mixed-voltage buses (I2C, interrupt lines)
- [ ] Verify that multi-voltage bank interfaces (e.g., 1.8 V to 3.3 V) use appropriate level translation or open-drain signaling

### GPIO Drive Strength and Slew Rate
- [ ] Verify drive strength settings (typically 2-16 mA) match the load and signal integrity requirements
- [ ] Select slew rate control (slow/fast) as needed to reduce EMI while meeting timing
- [ ] Adjust drive strength for high-speed output signals to maintain clean edges
- [ ] Check that drive strength settings are compatible with external device input thresholds and bus loading

### GPIO Current Drive and Package Limits
- [ ] Verify total current sink/source across all GPIOs does not exceed maximum per I/O bank or package
- [ ] Check individual pin output current capability (typically 4-16 mA per pin)
- [ ] Add series resistors for LED driving, high-current loads, or to limit inrush on capacitive loads
- [ ] Review total package power dissipation contributed by GPIO currents across all active pins

## 6. On-Chip Peripherals

### I2C
- [ ] Verify bus voltage level (determines pull-up resistor value)
- [ ] Calculate pull-up resistor value based on bus capacitance and speed (standard/fast/fast+)
- [ ] Check if internal pull-ups are sufficient or external ones are needed (usually external for multi-master)
- [ ] Confirm address uniqueness on the bus (7-bit or 10-bit)
- [ ] Add series resistors (optional, for slew rate limiting and ESD protection)
- [ ] Check voltage level compatibility — use level translator if voltages differ

### SPI / QSPI
- [ ] Check maximum SPI clock frequency vs. slave device
- [ ] Consider series termination resistors (22-33 Ω) on clock line
- [ ] Verify chip select (CS/SS) signal control polarity and default pull-up/pull-down
- [ ] Check if Quad-SPI or Octal-SPI is needed for higher throughput (boot flash, display)
- [ ] Verify SPI voltage levels match connected peripherals

### UART
- [ ] Verify UART TX/RX, RTS/CTS direction between MPU and external device
- [ ] Verify RS-232 level translation if required (use MAX3232 or similar)
- [ ] Check baud rate accuracy vs. clock source tolerance
- [ ] Verify flow control pin connections (RTS/CTS) if needed

### CAN / CAN-FD
- [ ] Verify CAN transceiver compatibility (3.3V or 5V)
- [ ] Add common-mode choke on CANH/CANL lines
- [ ] Place termination resistor (120 Ω) at both ends of the bus
- [ ] Add ESD protection on CAN bus lines

### Analog-to-Digital Converter (ADC) — if integrated
- [ ] Verify ADC resolution, sampling rate, and number of channels
- [ ] Check input impedance — may require an external buffer amplifier for high-impedance sources
- [ ] Confirm full-scale voltage range (internal VREF, external VREF, or supply)
- [ ] Add anti-aliasing filter (RC low-pass) on each analog input
- [ ] Verify ADC input voltage must not exceed VREF+ or go below VREF-
- [ ] Check if dedicated analog supply (VDDA) and ground (VSSA) are required

### Digital-to-Analog Converter (DAC) — if integrated
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

### External Interrupts
- [ ] Verify interrupt trigger type (rising, falling, both edges, level)
- [ ] Check interrupt priority and nested interrupt support
- [ ] Add external debounce circuitry if needed (RC filter or Schmitt trigger)
- [ ] Confirm no floating interrupt pins — use internal pull-up/pull-down

### Comparator — if integrated
- [ ] Verify input voltage range and reference voltage
- [ ] Check hysteresis settings (internal or external)

## 7. Boot Configuration

- [ ] Verify boot mode selection pins (eMMC, SD, SPI NOR/NAND, USB, serial)
- [ ] Check boot device voltage levels and interface compatibility
- [ ] Ensure boot device is correctly populated and configured
- [ ] Verify boot speed/strapping resistor values
- [ ] Check if boot pins have internal pull-up/pull-down and if external resistors are needed
- [ ] Verify boot option pin strapping (e.g., boot option pins to override fuse settings)
- [ ] Document boot configuration in schematic

## 8. Debug Interface

### Debug Interface (JTAG / SWD)
- [ ] Route JTAG (TCK, TMS, TDI, TDO) or SWD (SWCLK, SWDIO) signals to a debug header
- [ ] Verify if there is mode selection for different debug interfaces (JTAG mode, SWD mode, or proprietary mode)
- [ ] Add series termination resistors (0-10 Ω) on JTAG lines for signal integrity
- [ ] Verify external pull-up/pull-down on SWDIO/SWCLK as per MPU requirements
- [ ] Consider VTREF pin connection for voltage reference matching with debugger
- [ ] Verify JTAG/SWD signal voltage levels before connecting to debugger
- [ ] Keep debug interface accessible in the final product (or disable for production)
- [ ] Consider trace buffer/ETM for complex debugging

## 9. Thermal Management

- [ ] Calculate TDP and design appropriate heatsink/fan solution
- [ ] Verify junction temperature (Tj) under worst-case ambient conditions
- [ ] Check thermal resistance (θJA, θJC, θJB) for the package
- [ ] Ensure adequate airflow in enclosure
- [ ] Consider using thermal interface material (TIM) between MPU and heatsink
- [ ] Design for proper heat dissipation path to ambient

## 10. Regulatory & Reliability

- [ ] Add ESD protection on all external connections (I/O, USB, Ethernet, communication lines)
- [ ] Add EMI filters on all external high-speed buses and digital I/O lines
- [ ] Verify EMI/EMC compliance requirements (FCC, CE)
- [ ] Add external watchdog timer for system reliability (or verify internal WDT is sufficient)
- [ ] Consider voltage monitoring / power-fail detection
- [ ] Add RC filter on reset pin to prevent noise-induced resets
- [ ] Verify latch-up immunity (check datasheet latch-up test levels)
- [ ] Check for safety-critical features (ECC, lockstep cores, clock security system, memory BIST) if applicable
