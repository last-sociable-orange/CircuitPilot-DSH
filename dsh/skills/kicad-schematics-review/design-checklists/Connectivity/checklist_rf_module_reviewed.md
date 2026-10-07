# RF Transceiver Module Design Checklist

*Note: RF modules integrate the RF IC, matching network, antenna (or antenna connector), and often a crystal. Use this checklist alongside the RF Transceiver IC checklist.*

## 1. Module Selection

- [ ] Verify module has pre-certification (FCC/CE/IC pre-approved) to reduce compliance effort
- [ ] Verify antenna type (PCB trace, U.FL/IPEX connector, chip antenna) meets application requirements
- [ ] Verify shielding (integrated shield can) for emissions control
- [ ] Verify module includes required external flash, PSRAM if needed per application
- [ ] Verify pin compatibility for second-source alternatives

### Module Advantages over Discrete IC
- [ ] Verify pre-matched antenna circuitry eliminates external RF matching tuning
- [ ] Verify pre-certification (FCC/CE) allows use with minimal additional testing
- [ ] Verify integrated crystal eliminates crystal layout and selection effort
- [ ] Verify known-good RF performance per datasheet

## 2. Antenna Considerations

- [ ] If external antenna (U.FL): verify 50 Ω coax cable routing from module connector to antenna, kept away from noise sources
- [ ] Verify antenna connector mating type and cable compatibility
- [ ] Verify antenna placement is at edge of product, away from metal (battery, speaker, shield cans)

## 3. Power

- [ ] Verify module supply voltage per datasheet (typically 3.3V, check tolerance)
- [ ] Verify peak current during TX burst per datasheet — verify supply can deliver peak current
- [ ] Verify average current meets system power budget based on duty cycle
- [ ] Verify module power-up inrush current — supply must handle it
- [ ] Verify VDD decoupling per datasheet (low ESR, close to module pin)
- [ ] Verify supply type (LDO for clean supply, DC-DC for efficiency) per application requirements

## 5. Integration

- [ ] Verify interface (UART for AT-command modules, SPI for host-controlled) is compatible with host
- [ ] Verify UART baud rate and flow control per module datasheet
- [ ] For SPI: verify throughput is adequate for application per datasheet
- [ ] Verify GPIO default states — check pull-ups/pull-downs per datasheet
- [ ] If reset pin: verify RC delay for proper power-up timing per datasheet
- [ ] If boot mode/chip enable: verify pull-up/down for programming mode entry per datasheet

## 6. Module Certifications

- [ ] Verify FCC modular approval covers the intended antenna per module filing
- [ ] Verify IC (Canada) listing
- [ ] Verify CE (Europe) declaration
- [ ] Follow module manufacturer's integration guide for maintaining certification
- [ ] Verify only approved antenna types/gains listed in module's filing are used
- [ ] Verify label requirements — module FCC ID display on product

## 7. Thermal

- [ ] Verify module self-heating (during continuous TX) is within temperature rating per datasheet
- [ ] Verify module temperature rating vs. enclosure ambient temperature
- [ ] Verify adequate ventilation around module
