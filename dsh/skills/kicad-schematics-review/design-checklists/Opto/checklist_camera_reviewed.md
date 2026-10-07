# Camera Module / Image Sensor Design Checklist

## 1. Sensor Type Selection

- [ ] Verify resolution (VGA, 1MP, 2MP, 5MP+, 8MP+) meets application requirements
- [ ] Verify sensor type (CMOS, CCD) is appropriate for application
- [ ] Verify color filter type (Bayer, monochrome, RCCB) meets application requirements
- [ ] Verify shutter type (global shutter vs. rolling shutter) is appropriate for motion in scene
- [ ] Verify interface (DVP, MIPI CSI-2, USB, Ethernet) is compatible with host processor
- [ ] Verify form factor (integrated module vs. bare sensor) matches assembly capability

### Key Specifications
- [ ] Verify pixel size meets low-light and resolution requirements per datasheet
- [ ] Verify frame rate at full resolution meets application requirements per datasheet
- [ ] Verify dynamic range meets scene contrast requirements per datasheet
- [ ] Verify SNR meets image quality requirements per datasheet
- [ ] Verify sensitivity meets low-light requirements per datasheet
- [ ] Verify dark noise meets image quality requirements per datasheet
- [ ] Verify power consumption meets system power budget per datasheet

## 2. Interface / Connectivity

### MIPI CSI-2
- [ ] Verify number of differential data lanes (1-4 lanes) is compatible with host
- [ ] Verify differential impedance (100 Ω) per interface specification
- [ ] Verify AC coupling capacitor values on each differential signal per MIPI specification
- [ ] Verify ESD protection on lanes if routed through FPC connector
- [ ] Verify I2C control bus for sensor configuration (check address configuration)
- [ ] Verify MCLK (master clock) source (external or internal oscillator)

### DVP (Parallel)
- [ ] Verify data bus width (8-10 bits) is compatible with host
- [ ] Verify signal routing: PCLK, HREF, VSYNC, D[0:9] with matched length per datasheet guidelines
- [ ] Verify I/O voltage (3.3V or 1.8V) matches host interface per datasheet

### USB Camera (UVC)
- [ ] Verify USB speed (2.0 or 3.0) meets bandwidth requirements
- [ ] Verify UVC compliance for plug-and-play driver support

## 3. Lighting / Illumination

- [ ] Verify minimum illumination rating meets operating environment requirements per datasheet
- [ ] If night vision required: verify IR LED wavelength (850 nm, 940 nm) is compatible with sensor
- [ ] If flash required: verify LED flash driver can deliver required current pulse
- [ ] If diffuser used: verify even illumination across field of view
- [ ] For machine vision: verify strobe sync capability

## 4. Power

- [ ] Verify analog supply (AVDD) voltage per datasheet — check noise requirements
- [ ] Verify digital core supply (DVDD) voltage per datasheet
- [ ] Verify I/O supply (IOVDD) voltage matches host interface per datasheet
- [ ] Verify power sequencing (AVDD → DVDD → IOVDD) per datasheet
- [ ] Verify reset timing: wait for power-good before releasing reset per datasheet
- [ ] Verify active, standby, and sleep mode currents meet system power budget
