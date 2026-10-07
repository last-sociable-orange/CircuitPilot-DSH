# Fuse / PTC / Circuit Protection Design Checklist

## 1. Protection Device Type

### Fuse Selection
- [ ] Verify fuse speed (fast-blow, slow-blow/time-delay, very fast-acting) is appropriate for the load characteristics per datasheet
- [ ] Verify package type (SMD, through-hole cartridge) fits PCB assembly and serviceability requirements
- [ ] If SMD: verify package size (0402, 0603, 1206) meets current and voltage requirements

### PTC Resettable Fuse (Polyfuse)
- [ ] Verify PTC type (SMD, radial leaded, strap) fits PCB and mechanical constraints
- [ ] Verify self-resetting behavior is acceptable for the application (slower trip than fuse)
- [ ] Verify PTC can be used instead of one-time fuse (for overcurrent events that may be temporary)

### Other Protection Devices
- [ ] If circuit breaker used: verify panel-mount or high-power rating per datasheet
- [ ] If eFuse IC used: verify adjustable current limit, OVP, and reverse protection features meet requirements per datasheet
- [ ] If current sense + cutoff used: verify sense resistor + comparator + MOSFET ratings per datasheet

## 2. Electrical Specifications

### Fuse Ratings
- [ ] Verify rated current (I_rated) — normal operating current must be below rated current per derating guidelines applicable to the safety standard (UL, IEC)
- [ ] Verify rated voltage exceeds maximum system voltage (check DC vs. AC rating separately)
- [ ] Verify interrupting rating (breaking capacity) exceeds maximum possible short-circuit current from the supply
- [ ] Verify I²t (melting integral) is below the I²t rating of downstream components (traces, ICs) per datasheet

### PTC Ratings
- [ ] Verify hold current (I_hold) at maximum operating temperature is adequate — check derating per datasheet
- [ ] Verify trip current (I_trip) is appropriate for overcurrent threshold per datasheet
- [ ] Verify maximum voltage (V_max) exceeds the maximum system voltage — PTC may be damaged if tripped at higher voltage
- [ ] Verify tripped power dissipation is acceptable for enclosure thermal budget per datasheet
- [ ] Verify trip time at expected fault current per datasheet curve
- [ ] Verify series resistance (R_min, R_typ, R_max) during normal operation is acceptable

## 3. Selection by Application

### Power Input (DC Jack / Terminal Block)
- [ ] Verify fuse is in series with input power line (after reverse polarity protection)
- [ ] Verify speed type (fast-blow vs. slow-blow) matches load characteristics per datasheet
- [ ] Verify rated voltage exceeds maximum input voltage (including transients)

### USB Power (VBUS)
- [ ] Verify PTC or fuse meets USB specification current rating per USB standard
- [ ] Verify SMD PTC package fits PCB layout
- [ ] Verify USB overcurrent protection requirement is satisfied

### Battery Output
- [ ] Verify primary protection (fuse/PTC) at battery output per battery safety requirements
- [ ] Verify secondary protection inside battery pack per battery specification
- [ ] Verify PTC hold current exceeds max load current with margin per datasheet derating

### Motor / Actuator
- [ ] Verify slow-blow fuse is used (high inrush current during start) per motor datasheet
- [ ] If eFuse used: verify adjustable current limit is set correctly per motor stall current

### PCB Trace Protection
- [ ] Verify fuse I²t is lower than trace I²t per PCB copper weight and cross-section
- [ ] Verify trace width is adequate for fuse-rated current per PCB design guidelines

## 4. Environmental Considerations

### Temperature Derating
- [ ] Verify fuse current rating at maximum ambient temperature per derating curve in datasheet
- [ ] Verify PTC hold current at maximum ambient temperature per derating curve in datasheet
- [ ] If operating at high temperature: verify selected rating accounts for derating per datasheet

### Humidity / Moisture
- [ ] If open cartridge fuses used in high-humidity environment: verify hermetically sealed fuses are used

