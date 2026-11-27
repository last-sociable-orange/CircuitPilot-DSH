# Real-Time Clock (RTC) Design Checklist

## 1. Power

### Main Supply (VDD)
- [ ] Verify operating voltage range (typically 1.8V–5.5V)
- [ ] Ensure supply is clean (verify decoupling requirements per datasheet)
- [ ] Check supply current during normal operation (typically < 1 µA to a few µA)

### Backup / Battery Supply (VBAT)
- [ ] Provide backup battery input for timekeeping when main power is off
- [ ] Verify VBAT voltage range (typically 1.3V–3.6V for coin cells)
- [ ] Check battery switch-over threshold voltage (when VDD < VBAT - V_threshold)
- [ ] Verify reverse charging protection — RTC should not charge the battery
- [ ] Add series resistor (typically 1-10 kΩ) or diode for protection if not built-in

### Coin Cell / Backup Battery
- [ ] Select battery type: CR2032 (primary lithium), Supercapacitor, or rechargeable Li-Ion
- [ ] CR2032: capacity ~225 mAh, lifespan = capacity / (timekeeping current + self-discharge)
- [ ] Supercapacitor: 10+ year lifespan but higher leakage
- [ ] Verify battery holder footprint and retention mechanism
- [ ] Add battery isolation in shipping (Kapton tab, or removable jumper)
- [ ] Include a test point for battery voltage monitoring
- [ ] Verify RTC battery circuit complies with applicable UL safety standards:
  - UL 1642 (Lithium Battery Cells) — verify cell-level certification
  - UL 2054 (Household/Commercial Batteries) — verify pack-level certification if multiple cells
  - UL 62368-1 / UL 60950-1 — verify battery compartment and user-access requirements
  - UL 991 (Enclosure for Battery Compartments) — verify if applicable
- [ ] Verify series current-limiting resistor (10-100 Ω) is present between battery and RTC VBAT pin to limit short-circuit current per UL requirements
- [ ] Verify reverse polarity protection: battery holder keying or PCB layout prevents reverse insertion per UL 62368-1
- [ ] Verify battery holder has positive retention mechanism (no dislodging on drop/vibration) per UL requirements
- [ ] If battery is user-replaceable: verify battery compartment requires tool or two independent actions to open (e.g., screw + cover) per UL 62368-1
- [ ] If battery is user-replaceable: verify caution marking near battery compartment (battery type, polarity, warning) per UL requirements
- [ ] If battery is soldered (non-replaceable): verify reflow profile does not exceed battery manufacturer's maximum temperature rating
- [ ] Verify PCB trace width from battery to RTC VBAT pin is adequate for fuse action (narrow trace acts as fuse under short circuit) — or verify dedicated PTC/fuse is in series
- [ ] Verify no risk of battery short circuit from exposed solder pads or vias under battery holder per UL clearance requirements
- [ ] Verify battery voltage monitoring test point does not create a short-circuit path per UL spacing requirements

### Power Consumption Budget
- [ ] Review typical timekeeping current (I_BAT) — usually 300 nA to 1 µA
- [ ] Review I2C/SPI communication current (brief spikes during reads/writes)
- [ ] Account for temperature effects: battery self-discharge increases at high temperature
- [ ] Calculate expected battery life:
  - Battery Life = Battery Capacity / (Timekeeping Current + Self-Discharge)
  - Typical CR2032: ~5-10 years at 1 µA total draw

## 2. Crystal / Oscillator

### 32.768 kHz Crystal Selection
- [ ] Verify crystal frequency: 32.768 kHz (2^15 Hz) — standard RTC frequency
- [ ] Select load capacitance (CL): 6 pF, 9 pF, 12.5 pF are common
- [ ] Verify ESR: typically < 70 kΩ for low-power RTCs (lower ESR = better startup)
- [ ] Check shunt capacitance (C0): typically 1-2 pF
- [ ] Verify drive level: RTCs have very limited drive capability (typically < 1 µW)
- [ ] Check frequency tolerance: ±20 ppm (~0.5 min/month error), ±5 ppm (~0.13 min/month)
- [ ] Temperature coefficient: parabolically curve at ~ -0.035 ppm/°C² from turnover point

### External Capacitors
- [ ] Calculate external load capacitors: CL_ext = 2 × (CL - C_stray)
- [ ] C_stray is typically 1-3 pF (PCB parasitic)
- [ ] For CL = 12.5 pF, C_stray = 2 pF: CL_ext = 2 × (12.5 - 2) = 21 pF
- [ ] Use NPO/C0G capacitors for temperature stability (avoid X5R/X7R for this application)
- [ ] Some RTCs have internal load capacitors (programmable) — verify configuration

### PCB Layout for 32.768 kHz Crystal
- [ ] Do not place ground plane directly under the crystal (increases stray capacitance)
- [ ] Keep the area around the crystal clear on all layers
- [ ] Clean crystal pins thoroughly (no flux residue — can cause leakage)
- [ ] Consider shielding can for noisy environments

### Oscillator Startup
- [ ] Verify oscillator startup time (typically 1-3 seconds for 32.768 kHz)
- [ ] Check RTC status register for oscillator stop flag (OSF)
- [ ] Ensure software checks OSF and reinitializes time after power loss
- [ ] Test startup at minimum temperature and minimum supply voltage

## 3. Communication Interface

### I2C Interface
- [ ] Verify bus voltage level (often 1.8V or 3.3V — may differ from VBAT)
- [ ] Calculate I2C pull-up resistors based on bus capacitance and speed
- [ ] Check I2C slave address (often 0x68, 0x6F, or configurable via address pin)
- [ ] Verify maximum bus speed (standard 100 kHz, fast 400 kHz)
- [ ] Check if RTC supports clock stretching

### SPI Interface
- [ ] Verify SPI mode (CPOL/CPHA) matching between RTC and MCU
- [ ] Check maximum SPI clock frequency
- [ ] Route chip select line cleanly (no glitches)

## 4. Timekeeping Functions

### Clock/Calendar
- [ ] Verify supported registers: seconds, minutes, hours, day, date, month, year
- [ ] Check hour format: 12-hour vs. 24-hour mode
- [ ] Verify century handling (some RTCs have only 2-digit year)
- [ ] Validate leap year calculation support
- [ ] Verify BCD vs. binary register format

### Alarm Functions
- [ ] Verify number of alarms (1 or 2 typical)
- [ ] Check alarm match modes: seconds/minutes/hours/day/date, or any combination
- [ ] Verify alarm output pin (INT or ALARM) — open-drain or push-pull
- [ ] Ensure alarm output is pulled up appropriately (if open-drain)

### Timestamp / Time Capture
- [ ] Verify input pin for time-stamping external events
- [ ] Check timestamp resolution (seconds or sub-seconds)
- [ ] Verify multiple event storage (FIFO) if needed

### Watchdog Timer (if integrated)
- [ ] Verify watchdog time-out range
- [ ] Configure watchdog reset or interrupt output
- [ ] Ensure watchdog is properly initialized and serviced

## 5. Output Signals

### Square Wave Output (SQW / CLKOUT)
- [ ] Verify frequency options (1 Hz, 4.096 kHz, 8.192 kHz, 32.768 kHz)
- [ ] Check if output is enabled by default (some RTCs enable SQW on power-up)
- [ ] Configure output drive type (push-pull vs. open-drain)
- [ ] If not used, disable SQW or leave output floating (if it doesn't cause issues)

### Interrupt Output (INT)
- [ ] Verify output type: open-drain (requires pull-up) or push-pull
- [ ] Configure polarity: active-low or active-high
- [ ] Check interrupt source selection (alarm, timer, timestamp, watchdog)
- [ ] Ensure interrupt is properly connected to MCU/MPU

## 6. Calibration / Accuracy Compensation

### Digital Trimming (if supported)
- [ ] Use digital calibration registers to adjust for crystal inaccuracy
- [ ] Calculate required correction: Correction = Actual Frequency - Target Frequency
- [ ] Typical adjustment range: ±100 ppm in steps of ~1-5 ppm
- [ ] Measure initial frequency error during production and store calibration value in EEPROM/NVM

### Temperature Compensation (if available — TCXO RTC)
- [ ] Verify if RTC has integrated temperature sensor for compensation
- [ ] Check compensation range and step size
- [ ] Account for higher power consumption during temperature measurements

## 7. Initialization and Configuration

- [ ] Check if RTC registers have defined power-on default values (usually not)
- [ ] Implement software routine to detect "first power-on" vs. battery-backed operation:
  - Check Oscillator Stop Flag (OSF) — set after VDD and VBAT both lost
  - Check Power-On Reset (POR) flag
  - Initialize time/date if flags indicate first boot
- [ ] Enable oscillator (some RTCs have separate oscillator enable bit)
- [ ] Configure time format (24h vs 12h, BCD vs binary)
- [ ] Initialize alarms as disabled (if not needed)
- [ ] Configure output pins (SQW, INT) as needed
- [ ] Set initial time/date (from GPS, NTP, or user input)

## 9. Reliability & Environmental

- [ ] Verify operating temperature range matches application
- [ ] Check crystal frequency variation over temperature (parabolic curve)
- [ ] Account for battery life vs. temperature (self-discharge doubles every 10°C)
- [ ] Verify that backup battery is not subject to soldering temperatures (install battery after wave/reflow)
- [ ] Add ESD protection on RTC I/O lines if they go to external connectors
- [ ] Verify RTC meets target accuracy under worst-case temperature variation
  - ~ ±1 minute/month at room temperature is typical for uncompensated ±20 ppm crystal
  - ~ ±5-10 minute/month with temperature extremes
