# Photodiode / Phototransistor Design Checklist

## 1. Device Selection

- [ ] Verify device type (photodiode, PIN photodiode, avalanche photodiode, phototransistor, Darlington phototransistor, integrated ambient light sensor) is appropriate for application
- [ ] Verify spectral response covers operating wavelength per datasheet
- [ ] Verify responsivity (A/W) at peak wavelength meets signal level requirements per datasheet
- [ ] Verify dark current at operating temperature is acceptable per datasheet
- [ ] Verify rise/fall time meets speed requirements per datasheet
- [ ] Verify active area is appropriate for sensitivity and speed requirements per datasheet

## 2. Circuit Design

### Photodiode Amplifier (Transimpedance)

- [ ] Verify transimpedance gain (R_f) provides required output voltage range for expected photocurrent
- [ ] Verify feedback capacitor (C_f) is selected for stability per op-amp datasheet
- [ ] Verify photodiode capacitance (C_j) is within amplifier capability per datasheet
- [ ] Verify op-amp selection: sufficient GBW, low input capacitance (FET input for fast response), low noise for sensitive measurements
- [ ] Verify op-amp input bias current is negligible compared to expected photocurrent

### Phototransistor Circuit

- [ ] Verify collector resistor value provides required output swing per datasheet
- [ ] Verify output type (switching or analog) matches application requirements
- [ ] If open-collector output: verify pull-up resistor value

### Comparator-based (Light threshold)

- [ ] If using comparator: verify reference voltage is appropriate for light threshold
- [ ] Verify hysteresis (Schmitt trigger) to prevent oscillation at threshold

# 
