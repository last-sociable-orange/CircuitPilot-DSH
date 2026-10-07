# RF Transceiver IC / Module Design Checklist

## 1. Radio Protocol & Frequency Band

### Protocol Selection
- [ ] Verify radio protocol (Bluetooth Classic, BLE, Wi-Fi, Zigbee/Thread, LoRa, NB-IoT/LTE-M, proprietary 2.4 GHz, proprietary sub-GHz, UWB, NFC/RFID) meets application requirements
- [ ] Verify protocol stack support (on-chip or host-based) per datasheet

### Frequency Band
- [ ] Verify frequency band (2.4 GHz ISM, sub-GHz, 5 GHz) is appropriate for region and application
- [ ] Verify regional regulatory compliance (FCC, ETSI, ISED, etc.) per target markets

## 2. RF Performance

### Key RF Parameters
- [ ] Verify transmitter output power meets link budget requirements per datasheet
- [ ] Verify receiver sensitivity meets link budget requirements per datasheet
- [ ] Verify link budget: Tx power + Rx sensitivity + antenna gains – path loss is adequate
- [ ] Verify data rate (goodput) meets application throughput requirements per datasheet
- [ ] Verify modulation scheme is appropriate for the application
- [ ] Verify channel bandwidth and channel count meet application needs per datasheet

### Range Estimation
- [ ] Verify range requirement vs. path loss at operating frequency and environment per application
- [ ] Verify range is achievable with selected radio and antenna per datasheet

## 3. Antenna Design

### Antenna Type
- [ ] Verify antenna type (PCB trace, chip antenna, whip/rod, ceramic patch, external connector, MIMO) meets performance and cost requirements
- [ ] Verify antenna is appropriate for the enclosure and mechanical constraints

### Antenna Matching
- [ ] Verify impedance matching network (50 Ω single-ended or differential per datasheet)
- [ ] Verify matching network topology follows IC reference design
- [ ] Verify S11 < -10 dB at operating frequency (VSWR < 2:1) per measurement
- [ ] Verify populated and unpopulated matching component positions are included for tuning per reference design

### Antenna Placement
- [ ] Verify antenna is at edge of board with keep-out zone per datasheet
- [ ] Verify antenna clearance from enclosure (plastic OK, metal needs cutouts)
- [ ] For external antenna: verify coaxial cable routing with adequate clearance

## 4. RF Front-End

### RF Interface
- [ ] Verify whether IC has integrated PA/LNA or requires external components per datasheet
- [ ] If external PA: verify gain and linearity meet requirements per datasheet
- [ ] If external LNA: verify noise figure and gain meet requirements per datasheet
- [ ] If RF switch needed: verify TX/RX sharing (half-duplex) per datasheet
- [ ] If SAW/BAW filter used: verify harmonic and interference suppression per datasheet
- [ ] Verify TX/RX port impedance matches antenna and matching network per datasheet

### RF Matching Network
- [ ] Follow IC reference design exactly for matching network topology

### Balun (if needed)
- [ ] If differential RF output to single-ended 50 Ω antenna: verify balun (integrated or external) per datasheet
- [ ] Verify insertion loss and phase balance per datasheet

## 5. Crystal / Clock

- [ ] Verify crystal frequency per datasheet
- [ ] Verify crystal accuracy per radio requirements (±10 ppm for BLE, ±20 ppm for Wi-Fi)
- [ ] Verify crystal load capacitance matches external capacitors per crystal and transceiver datasheet
- [ ] Verify startup time meets radio initialization requirements per datasheet
- [ ] For BLE: verify internal RC oscillator is only for sleep, not active connection
- [ ] For high-speed Wi-Fi (802.11): verify TCXO or temperature-compensated oscillator is used

## 6. Power Supply

### Supply Rails
- [ ] Verify analog supply (VDDA) filtering requirements per datasheet
- [ ] Verify digital core supply (VDDC), I/O supply, and PA supply voltages per datasheet
- [ ] Verify supply rails are within operating range

### Power Management
- [ ] Verify active mode current (Tx peak, Rx peak) meets system power budget per datasheet
- [ ] Verify idle and sleep mode currents meet system power budget per datasheet
- [ ] Verify LDO is used for analog supply (not directly from battery)

### Power Sequencing
- [ ] If specific sequencing of supply rails required: verify per datasheet
- [ ] Verify reset timing requirements per datasheet
- [ ] Verify PA enable/disable sequence to prevent damage per datasheet

## 8. Regulatory Compliance

### FCC (USA)
- [ ] Verify compliance with FCC Part 15.247 (2.4 GHz), Part 15.249, or Part 15.407 (5 GHz) as applicable
- [ ] If pre-certified module: verify module certification covers intended antenna and power level
- [ ] Verify conducted and radiated emissions limits are met
- [ ] Verify maximum TX power and harmonics/spurious emissions per applicable standard

### ETSI (Europe)
- [ ] Verify compliance with EN 300 328 (2.4 GHz) or EN 301 893 (5 GHz) as applicable
- [ ] If 5 GHz: verify Dynamic Frequency Selection (DFS) support per standard

### Other Regions
- [ ] Verify compliance with applicable standards for target markets (ISED Canada, MIC Japan, SRRC China, KC Korea, etc.)

### Pre-Certified Modules
- [ ] Using pre-certified module significantly reduces compliance effort
- [ ] Verify module certification covers the intended antenna, power level, and enclosure
