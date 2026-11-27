# Surge Protection (MOV / GDT / TVS for Power) Design Checklist

## 1. Surge Protection Device Type

### Metal Oxide Varistor (MOV)
- [ ] Verify MOV application (AC mains, DC power input, lightning surge) per datasheet ratings
- [ ] Verify clamping voltage is below the withstand voltage of downstream components
- [ ] Verify energy rating (Joules) meets expected surge energy per datasheet
- [ ] Verify peak current rating (8/20 µs) exceeds maximum expected surge current per datasheet
- [ ] Verify response time is adequate for the transient speed per datasheet
- [ ] Verify MOV end-of-life behavior (short circuit) is accounted for — series fuse required
- [ ] Verify package type (disc, chip, block) fits PCB and mounting requirements

### Gas Discharge Tube (GDT)
- [ ] Verify DC breakdown voltage per datasheet
- [ ] Verify impulse breakdown voltage at expected transient rate-of-rise per datasheet
- [ ] Verify surge current capability exceeds maximum expected surge per datasheet
- [ ] Verify capacitance is low enough for the signal or power line frequency per datasheet
- [ ] Verify response time is adequate for the transient speed (slower than TVS/MOV)
- [ ] If GDT may conduct follow current after firing: verify series fuse or current-limiting element is present
- [ ] Verify package type (SMD, through-hole, 3-electrode) meets application requirements

### TVS Diode (for Power Rails)
- [ ] Verify unidirectional (for positive DC rails) or bidirectional (for AC/bipolar) type per application
- [ ] Verify peak pulse power (PPP) rating meets expected surge energy per datasheet
- [ ] Verify clamping voltage is below the protected circuit's absolute maximum rating per datasheet

### TVS for ESD vs. Surge
- [ ] Verify surge-rated TVS is used for IEC 61000-4-5 compliance (not just ESD-rated TVS)
- [ ] Verify TVS datasheet specifies surge rating (IEC 61000-4-5, 8/20 µs waveform)

## 2. Multi-Stage Protection Topology

### Three-Stage Design (AC Mains)
- [ ] Verify Stage 1 (GDT at enclosure entry) diverts large surge current per datasheet
- [ ] Verify Stage 2 (MOV or high-power TVS) clamps residual voltage per datasheet
- [ ] Verify Stage 3 (low-power TVS) clamps to safe level for ICs per datasheet
- [ ] Verify decoupling impedance between stages (inductor, ferrite bead, or resistor) ensures progressive activation

### Two-Stage Design (DC Power Input)
- [ ] Verify Stage 1 (MOV or high-power TVS) at input connector — check energy rating per datasheet
- [ ] Verify Stage 2 (lower-clamp TVS) near sensitive IC — check clamping voltage per datasheet
- [ ] Verify decoupling (series ferrite bead or resistor) between stages per datasheet recommendation

## 3. Selection by Application

### AC Mains Input (100-240 VAC)
- [ ] Verify MOV rated voltage is appropriate for the AC line voltage per datasheet
- [ ] Verify energy rating meets application surge environment requirements per datasheet
- [ ] If GDT used in parallel with MOV: verify breakdown voltage per datasheet
- [ ] Verify series fuse is present — MOV may fail short, causing line current to flow

### DC Power Input (12V / 24V / 48V)
- [ ] Verify TVS VRWM exceeds maximum normal operating voltage (including tolerances) per datasheet
- [ ] Verify peak pulse power (PPP) rating is adequate for expected surge per datasheet
- [ ] For automotive: verify AEC-Q101 qualified TVS is used per application
- [ ] Verify series PTC or fuse is present between supply and TVS for overcurrent protection

### Telecom / RS-485 / CAN
- [ ] Verify GDT + TVS combination provides both high-current and fast-clamping protection per datasheet
- [ ] Verify decoupling resistor between GDT and TVS per application note
- [ ] Verify protection meets applicable telecommunication surge standards (ITU-T K.20/K.21, GR-1089)

### Antenna / RF Input
- [ ] Verify GDT or low-capacitance TVS (<0.5 pF) is used — check insertion loss at operating frequency
- [ ] If quarter-wave stub used: verify stub length is correct for operating frequency
- [ ] Verify insertion loss at operating frequency with protection in-circuit is acceptable

## 4. IEC 61000-4-5 (Surge) Compliance

- [ ] Verify surge protection level meets product target per IEC 61000-4-5 (Level 1-4)
- [ ] Verify protection device rating exceeds required surge level per datasheet
- [ ] Verify test waveform: 1.2/50 µs (voltage), 8/20 µs (current)
