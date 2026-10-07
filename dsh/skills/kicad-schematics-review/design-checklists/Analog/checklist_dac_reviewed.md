# Digital-to-Analog Converter (DAC) Design Checklist

## 1. Architecture

- [ ] Confirm the DAC architecture (R-2R, string, ΔΣ, current-steering, multiplying, PWM+filter) is appropriate for the required resolution, update rate, and application
- [ ] Verify the DAC resolution and update rate meet the signal bandwidth and precision requirements
- [ ] Check that the output type (voltage output or current output) matches the load — if current output, confirm an external I-to-V converter is correctly designed

## 2. Power Supply

- [ ] Verify analog (AVDD) and digital (DVDD) supply voltages and tolerances; confirm AVDD is supplied from a low-noise source (LDO or well-filtered supply)
- [ ] Check that AVDD and DVDD are adequately separated (ferrite bead) to prevent digital noise coupling into the analog output
- [ ] Confirm decoupling capacitor type, value, and placement per datasheet recommendations
- [ ] For bipolar output DACs: verify positive and negative supplies are present and within tolerance

## 3. Output Stage

- [ ] Confirm the output voltage swing (rail-to-rail or limited) covers the required signal range with margin
- [ ] Verify the output drive capability (current and capacitive load) is adequate for the load
- [ ] If an external output buffer op-amp is used, confirm its offset voltage, bandwidth, and drive capability are compatible with the DAC and load
- [ ] Check that the reconstruction filter (low-pass) cutoff frequency is appropriate for the update rate — verify it adequately removes sampling images without attenuating the signal
- [ ] For high-speed DACs: verify that deglitching or sample-and-hold output configurations are used if needed

## 4. Voltage Reference

- [ ] Confirm the reference source (internal or external) provides the correct full-scale voltage with adequate accuracy, drift, and noise for the required resolution
- [ ] If using an external reference, verify the reference IC's noise and drift are compatible with the DAC's resolution
- [ ] Check that the VREF input is properly decoupled (capacitor at the reference pin); if the DAC has a switched-capacitor VREF input, verify a buffer is present if the reference cannot supply the dynamic current

## 5. Digital Interface

- [ ] Confirm the digital interface type (SPI, I2C, parallel, LVDS, JESD204B) is compatible with the host controller and the required update rate
- [ ] For SPI: verify CPOL/CPHA and maximum clock frequency are correctly configured
- [ ] For I2C: verify bus address, pull-up resistors, and speed mode
- [ ] For parallel interfaces: verify setup/hold times and data bus width
- [ ] Verify the data format (straight binary, offset binary, two's complement) matches the application

## 6. Timing

- [ ] Confirm the maximum update rate and settling time (to the required accuracy) meet the signal bandwidth requirements
- [ ] If glitch impulse is a concern for the application, check the DAC's mid-scale glitch specification
- [ ] If the DAC has a LDAC pin for synchronized update of multiple channels, verify the routing and control logic are correct
- [ ] For multiple DACs requiring simultaneous output update, confirm LDAC is connected to all devices

## 7. AC Performance

- [ ] Verify the DAC's SFDR (Spurious-Free Dynamic Range) and THD at the target output frequency are adequate
- [ ] For communication applications: confirm ACLR and EVM meet the system requirements
- [ ] If the application requires low output noise, check the DAC's noise spectral density and verify it is compatible with the load's sensitivity

## 8. Static Performance

- [ ] Confirm DNL (Differential Non-Linearity) is within acceptable limits — DNL < 1 LSB ensures monotonicity (no missing codes) if required
- [ ] Check INL (Integral Non-Linearity) and gain/offset errors against the application's accuracy budget
- [ ] Verify that the DAC's linearity is sufficient over the required output voltage range

## 9. Reset and Power-Up Behavior

- [ ] Verify the DAC's output state at power-up (zero-scale, mid-scale, or high-impedance) is safe for the connected load — confirm it will not drive external circuitry into an unexpected state
- [ ] If the DAC has a CLR (clear) pin, verify it is connected and can be asserted to force the output to a known safe state
- [ ] Check the output configuration after power-loss/recovery to ensure consistent behavior
