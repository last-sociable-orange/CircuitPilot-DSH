# Bus Bridge / Interface Controller (USB-UART, USB-I2C, USB-SPI) Design Checklist

## 1. Device Selection

### Interface Type
- [ ] Verify bridge interface type (USB-to-UART, USB-to-I2C/SPI, USB-to-JTAG/GPIO, multi-protocol, USB-to-parallel) meets application requirements
- [ ] Verify both interface speeds are adequate for the application per datasheet

### USB Compliance
- [ ] Verify USB specification (USB 1.1, USB 2.0, USB 3.0) is compatible with host
- [ ] Verify USB-IF certification if required for the product
- [ ] Check if integrated USB termination and pull-up resistors are present or need external components per datasheet
- [ ] Verify ESD protection — check if integrated or external required per datasheet

## 2. Power

### USB Bus Power
- [ ] Verify device is bus-powered vs. self-powered per application
- [ ] For bus-powered: verify current draw meets USB specification per power negotiation (100 mA unconfigured, up to configured maximum)
- [ ] Check USB suspend current compliance per USB specification
- [ ] Verify VBUS filtering and decoupling per datasheet at USB connector
- [ ] Verify device can negotiate current requirements with USB host per datasheet

### Self-Powered Design
- [ ] If self-powered: verify local regulator for bridge IC voltage per datasheet
- [ ] If isolation needed: verify USB isolator (medical/industrial) is used
- [ ] Verify VBUS sense pin connection if required per datasheet

### Voltage Regulator
- [ ] If bridge has integrated LDO: verify output voltage and current capability meet system requirements per datasheet
- [ ] Verify decoupling capacitors per datasheet recommendations

### Power Sequencing
- [ ] Verify bridge IC reset/power-on timing is compatible with USB enumeration per datasheet
- [ ] Check if external reset circuit is needed per datasheet
- [ ] Verify power-up default states of bridge pins per datasheet

## 3. USB Connection

### Differential Pair (DP/DM)
- [ ] Verify DP/DM differential impedance (90 Ω) per USB specification
- [ ] Verify stub lengths on DP/DM traces are minimized
- [ ] Verify no 90° corners — use 45° chamfers or arcs

### USB Connector
- [ ] Verify connector type (USB-A, USB-B, Micro-B, USB-C) meets mechanical and application requirements
- [ ] Verify connector is placed at board edge for accessibility
- [ ] Verify ESD protection (TVS diodes) near connector on DP/DM lines
- [ ] Verify VBUS filtering (series ferrite bead + bulk capacitor) per datasheet
- [ ] Verify VBUS overcurrent protection (PTC resettable fuse) per USB specification
- [ ] Verify solid GND return path from connector to board ground

### USB-C Specific
- [ ] If USB-C: verify CC pin detection and configuration per USB-C specification
- [ ] Verify CC logic (MCU or dedicated CC controller) for role detection
- [ ] Verify Rp/Rd resistor termination per USB-C specification
- [ ] Verify DFP/UFP/DRP role detection handling

## 4. Target Interface (UART, I2C, SPI)

### UART Side
- [ ] Verify UART signal voltage levels (1.8V, 3.3V, 5V) are compatible with target device
- [ ] Verify TX/RX, RTS/CTS, DTR/DSR signal routing per application requirements
- [ ] If series resistors used on TX/RX: verify values are appropriate for ringing suppression per signal integrity
- [ ] Verify baud rate accuracy — bridge internal oscillator must meet baud rate error budget per datasheet
- [ ] For RS-232 levels: verify level translator (e.g., MAX3232) is used per RS-232 standard
- [ ] For RS-485: verify RS-485 transceiver with direction control is used per TIA/EIA-485-A
- [ ] Check flow control support (hardware RTS/CTS vs. software XON/XOFF) meets application needs

### I2C Side
- [ ] Verify bus voltage (1.8V, 3.3V, 5V) is compatible with target I2C devices
- [ ] Verify pull-up resistor values are correct for target bus speed and bus capacitance
- [ ] Check if bridge has integrated pull-ups or external are needed per datasheet
- [ ] Verify maximum bus capacitance is within I2C specification (typically 400 pF)
- [ ] If bridge acts as I2C master: verify clock stretching support per datasheet
- [ ] If bridge acts as I2C slave: verify address configuration per datasheet

### SPI Side
- [ ] Verify SPI mode (CPOL/CPHA) matches target device per datasheet
- [ ] Check maximum SPI clock frequency is adequate per datasheet
- [ ] Verify CS, SCK, MOSI, MISO signal routing with signal integrity
- [ ] If series termination on SCK used: verify value per signal integrity requirements
- [ ] Verify 3-wire or 4-wire SPI configuration per datasheet
- [ ] For Quad-SPI: verify all data lines are properly routed

## 5. EEPROM / Configuration

- [ ] Check if bridge IC needs external EEPROM for configuration (VID, PID, serial number, descriptors) per datasheet
- [ ] Verify EEPROM I2C address and bus pull-ups if external EEPROM used
- [ ] Program EEPROM with: Vendor ID (VID), Product ID (PID), serial number, product description string, power configuration per application requirements

## 6. Clock Source

- [ ] Check if bridge needs external crystal/oscillator or has internal oscillator per datasheet
- [ ] If external crystal: verify crystal frequency per datasheet
- [ ] Verify load capacitors match crystal specification per crystal datasheet
- [ ] Verify crystal traces are short per layout
- [ ] Verify clock accuracy meets UART baud rate generation requirements per datasheet

## 7. Signal Isolation (if needed)

- [ ] For medical, industrial, or high-voltage applications: verify USB isolator on DP/DM lines or isolated UART is used
- [ ] Verify isolation voltage rating meets safety requirements per datasheet
