# EMI Filter (Ferrite Bead / Common-Mode Choke) Design Checklist

## 1. Ferrite Bead

### Selection Parameters
- [ ] Verify impedance at 100 MHz (Z@100MHz) meets noise attenuation requirements per datasheet
- [ ] Verify DC resistance (DCR) is acceptable for voltage drop and power dissipation at operating current
- [ ] Verify rated current exceeds worst-case load current (check derating at operating temperature per datasheet)
- [ ] Verify package size fits PCB layout and current requirement

### Application — Power Supply Filtering
- [ ] Verify ferrite bead impedance is appropriate for the noise frequency spectrum per datasheet
- [ ] Verify post-bead capacitor(s) provide adequate filtering for the supply rail
- [ ] For PLL/VCO/analog supplies: verify bead selection per supply noise sensitivity requirements

### Application — Signal Filtering
- [ ] Verify bead impedance does not degrade signal integrity at operating frequency per datasheet
- [ ] Verify bead is placed close to the noise source or the receptor per layout
- [ ] For high-speed data lines (USB, HDMI, MIPI): verify ferrite bead is not used — use common-mode choke instead
- [ ] For bidirectional lines: verify bead filters in both directions as expected

### Application — Board-Level Noise Isolation
- [ ] Verify noisy sections (DC-DC, motor driver) are isolated from sensitive sections per layout
- [ ] If ground plane bead used: verify current rating is adequate for return current
- [ ] Verify bead impedance is appropriate for the noise frequency band per datasheet

## 2. Common-Mode Choke (CMC)

### Selection Parameters
- [ ] Verify common-mode impedance meets suppression requirements at target frequency per datasheet
- [ ] Verify differential-mode inductance is low enough to not affect signal integrity
- [ ] Verify DCR per channel is acceptable for signal swing at receiver per datasheet
- [ ] Verify rated current exceeds worst-case signal current
- [ ] Verify cutoff frequency is below the noise frequency band

### Application — USB 2.0
- [ ] Verify CMC is used on D+/D− pair per USB specification
- [ ] Verify impedance and bandwidth are compatible with USB 2.0 signaling per datasheet
- [ ] Verify USB eye diagram passes with CMC in-circuit

### Application — USB 3.0
- [ ] Verify CMC is used on each differential pair (SSTX, SSRX) individually
- [ ] Verify differential capacitance is within USB 3.0 requirements per datasheet
- [ ] Verify impedance and bandwidth are compatible with USB 3.0 signaling per datasheet

### Application — HDMI
- [ ] Verify CMC is used on each TMDS differential pair (3 data + 1 clock)
- [ ] Verify placement is within 10 mm of connector per layout
- [ ] Verify impedance and bandwidth are compatible with HDMI signaling per datasheet

### Application — Ethernet
- [ ] If external CMC used between magnetics and RJ45: verify impedance per datasheet
- [ ] Verify common-mode inductance of integrated magnetics meets Ethernet requirements

### Application — CAN / RS-485
- [ ] Verify CMC impedance is appropriate for bus frequency per datasheet
- [ ] Verify CMC rated voltage exceeds common-mode voltage range of the bus per datasheet

### Application — LVDS / MIPI
- [ ] Verify CMC capacitance is low enough (<1 pF line-to-line) per interface specification
- [ ] Verify impedance is compatible with differential impedance requirements per datasheet

## 3. Feedthrough Capacitor

- [ ] Verify capacitance is appropriate for the noise frequency band per datasheet
- [ ] Verify rated voltage exceeds signal voltage
- [ ] Verify feedthrough capacitor is suitable for the frequency range (up to 1 GHz) per datasheet
