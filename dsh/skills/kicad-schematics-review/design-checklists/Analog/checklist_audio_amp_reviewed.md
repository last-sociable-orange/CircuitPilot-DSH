# Audio Amplifier Design Checklist

## 1. Amplifier Class

- [ ] Confirm the amplifier class (A, AB, D, G, H, etc.) is appropriate for the application considering efficiency, output power, and audio quality requirements
- [ ] Verify the amplifier can deliver the required output power into the target load impedance (4 Ω, 8 Ω, 16 Ω, 32 Ω)
- [ ] Ensure the amplifier's minimum load impedance specification is not exceeded

## 2. Power Supply

- [ ] Verify the supply voltage range covers the required output swing — confirm the supply is adequate for the peak output voltage plus headroom
- [ ] For split-supply designs: verify positive and negative rails are balanced and within tolerance
- [ ] Confirm supply decoupling capacitor placement and values per datasheet — inadequate decoupling causes oscillation or distortion at high output levels
- [ ] For Class-D amplifiers: verify the power supply can deliver the peak current demand (which can be 2-3× the average current)

## 3. Input Stage

- [ ] Confirm the input configuration (single-ended or differential) matches the signal source
- [ ] Verify input impedance is compatible with the source (line inputs: typically ≥10 kΩ; instrument/mic inputs: as required by the source)
- [ ] If the amplifier has a differential input, verify the input common-mode range is respected
- [ ] If AC-coupled, verify the input high-pass filter cutoff frequencies are appropriate — check that the coupling capacitor value produces the correct corner frequency for the channel

## 4. Gain

- [ ] Confirm the gain setting (fixed or adjustable via resistor) produces the required output level for the expected input voltage
- [ ] For adjustable gain: verify the gain control method (potentiometer, resistor network, I2C) is correctly implemented and does not introduce noise or instability
- [ ] Check that the amplifier bandwidth is sufficient for the audio frequency range

## 5. Output Stage

- [ ] Verify the amplifier can drive the target load impedance without exceeding its output current limit
- [ ] Confirm the output voltage swing can deliver the required power into the load — account for headroom and load impedance
- [ ] For Class-D amplifiers: verify the LC output filter (inductor + capacitor) values are correct for the switching frequency and load impedance
- [ ] Check that the output filter cutoff frequency is above the audio band but adequately suppresses the switching frequency
- [ ] For Class-AB amplifiers: verify the output transistor bias (quiescent current) is set correctly to minimize crossover distortion

## 6. Protection Features

- [ ] Verify overcurrent protection (OCP) threshold is above the peak output current with margin
- [ ] Confirm thermal shutdown threshold and hysteresis — verify the amplifier can operate at maximum ambient temperature without triggering
- [ ] Check DC offset protection — if the amplifier detects DC at the output, confirm it mutes or shuts down to protect the speaker
- [ ] For Class-D amplifiers: verify short-circuit protection on the output (speaker terminals)
- [ ] Confirm that mute/shutdown control is used during power-up/down to prevent pop/click transients

## 7. Noise and Distortion

- [ ] Verify THD+N (total harmonic distortion + noise) at the target output power and frequency meets the application's audio quality requirements
- [ ] Confirm SNR (signal-to-noise ratio) is adequate — check that the noise floor is not audible at typical listening levels
- [ ] Verify channel separation (crosstalk) is sufficient for stereo applications
- [ ] For Class-D amplifiers: verify that switching noise and its harmonics are adequately filtered and do not couple into sensitive circuits

## 8. Thermal

- [ ] Calculate worst-case power dissipation (maximum at moderate output power for Class-AB; maximum at full output for Class-D) and confirm junction temperature stays within the rated range at maximum ambient
- [ ] Verify the heatsink or PCB copper area is adequate for the dissipation
- [ ] Confirm thermal pad / thermal vias are correctly implemented for the amplifier package
- [ ] For high-power applications: verify forced airflow or active cooling if required

## 9. Filter Design (Class-D Specific)

- [ ] Verify the LC low-pass filter corner frequency is appropriate for the amplifier's switching frequency and the audio bandwidth
- [ ] Confirm the inductor saturation current exceeds the peak output current — verify the inductor core material is suitable for the switching frequency
- [ ] Check that the output filter capacitors have adequate voltage rating and are of a suitable type (film or C0G for low distortion)
- [ ] Verify the filter does not introduce significant phase shift within the audio band that could affect feedback loop stability
