# Analog-to-Digital Converter (ADC) Design Checklist

## 1. Architecture

- [ ] Confirm the ADC architecture (SAR, ΔΣ, pipeline, flash, dual-slope) is appropriate for the required resolution, sampling rate, and application
- [ ] Verify that the ADC resolution and sampling rate meet the Nyquist requirement for the highest input frequency of interest
- [ ] Check that the ADC's ENOB (Effective Number of Bits) at the target input frequency is sufficient for the required dynamic range
- [ ] If oversampling is used, confirm that the decimation filter and output rate meet system requirements

## 2. Power Supply

- [ ] Verify analog (AVDD) and digital (DVDD) supply voltages and tolerances match the datasheet; confirm AVDD uses a low-noise source (LDO or filtered supply)
- [ ] Check that AVDD and DVDD are adequately separated (ferrite bead or supply split) to prevent digital noise from coupling into the analog section
- [ ] Confirm decoupling capacitor type, value, and placement per datasheet recommendations
- [ ] If power sequencing is required between AVDD and DVDD, verify the sequence is implemented correctly

## 3. Analog Input

- [ ] Confirm input configuration (single-ended or differential) matches the signal source
- [ ] For differential inputs: verify the full-scale range (±VREF or 2 × VREF) and the required common-mode voltage (VCM) are compatible with the driver output
- [ ] For single-ended inputs: verify the input voltage range (0 to VREF) is never exceeded
- [ ] Check that the ADC's input impedance is compatible with the signal source — for SAR ADCs with switched-capacitor inputs, verify the charge kickback filter (RC) is properly designed to settle within the acquisition time
- [ ] Verify the input driver op-amp has sufficient bandwidth, settling time, and noise performance (output noise below the ADC's LSB) for the application
- [ ] Confirm that the anti-aliasing filter cutoff frequency is appropriate for the sampling rate and signal bandwidth

## 4. Input Protection

- [ ] Verify absolute maximum input voltage ratings are never exceeded under any fault condition
- [ ] If the input can exceed the supply rails, confirm external clamp diodes and series current-limiting resistors are present
- [ ] Check that ESD protection on the input path is adequate for the connector/exposure level

## 5. Voltage Reference (VREF)

- [ ] Confirm the reference voltage (internal or external) sets the correct full-scale range and meets accuracy, drift, and noise requirements for the target ENOB
- [ ] If using an external reference, verify the reference IC's noise and drift are compatible with the ADC's performance; confirm the reference buffer (if needed) can drive the VREF pin's dynamic load
- [ ] Check that the VREF trace is isolated from noisy digital signals and uses a Kelvin (sense) connection if the ADC supports it

## 6. Clock

- [ ] Confirm the clock frequency, type, and amplitude are compatible with the ADC clock input requirements
- [ ] Verify the clock jitter is low enough to achieve the target SNR at the maximum input frequency — if the application requires a high SNR at high input frequencies, confirm a low-jitter clock source is used
- [ ] If AC coupling is required on the clock input, verify it is implemented correctly

## 7. Digital Interface

- [ ] Confirm the digital interface type (parallel, SPI, LVDS, JESD204B) is compatible with the host controller and the data rate
- [ ] Verify output logic levels match the host controller's input voltage (1.8V, 2.5V, 3.3V)
- [ ] If using a serial interface, check that SPI mode (CPOL/CPHA) and maximum clock frequency are correctly configured
- [ ] For JESD204B: verify lane rate, number of lanes, subclass selection, and SYSREF distribution

## 8. Conversion Timing

- [ ] Confirm the conversion time, acquisition time, and throughput rate meet the application's sampling requirements
- [ ] For SAR ADCs: verify the acquisition time is sufficient for the input RC filter to settle to the required accuracy
- [ ] If the ADC has pipeline delay (latency), confirm it is acceptable for control loop or real-time applications
- [ ] Verify the data-ready / end-of-conversion (EOC) signal is connected to the host controller

## 9. Performance

- [ ] Confirm ADC static specifications (DNL, INL, offset error, gain error) are within the application's accuracy budget
- [ ] Verify that PSRR (power supply rejection) is adequate given the supply noise present in the system
- [ ] Check that self-heating does not cause unacceptable offset or gain drift at the operating sampling rate
