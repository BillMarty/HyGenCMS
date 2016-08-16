# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

"""
This file provides a key to pins using the official V3 CMS Schematic.
It should be kept synchronized with the SBC_IO.xlsx spreadsheet in the
``docs`` folder.

Last updated: 2016-08-16
"""

modes = {
    # Pin   Mode	CPU Name	Function		P9	Mode	CPU Name	Function
    # Unmodifiable
    # P8_01		DGND
    # P8_02		DGND

    # Defaults
    # P8_03	1	mmc1_dat6	Reserved for internal EMMC
    # P8_04	1	mmc1_dat7	Reserved for internal EMMC
    # P8_05	1	mmc1_dat2	Reserved for internal EMMC
    # P8_06	1	mmc1_dat3	Reserved for internal EMMC

    # P8_07	7	gpio2[2]	Spare switch
    'P8_07': 'in',

    # P8_08	7	gpio2[3]	Disk Activity LED
    'P8_08': 'lo',

    # P8_09	7	gpio2[5]	USB switch
    'P8_09': 'in',

    # P8_10	7	gpio2[4]	Safe to remove LED
    'P8_10': 'lo',

    # P8_11	7	gpio1[13]	Hold 12V (keep powered on after losing 24V)
    'P8_11': 'lo',

    # P8_12	7	gpio1[12]	PID LED
    'P8_12': 'lo',

    # P8_13	7	gpio0[23]	Switch: move logs to USB
    'P8_13': 'in',

    # P8_14	7	gpio0[26]	Spare LED
    'P8_14': 'lo',

    # P8_15	7	gpio1[15]	Aux START (signal to the DeepSea to stop the motor)
    'P8_15': 'lo',

    # P8_16	7	gpio1[14]	CMS Warn
    'P8_16': 'lo',

    # P8_17	7	gpio0[27]	Aux STOP
    'P8_17': 'lo',

    # P8_18	7	gpio2[1]	CMS Fault
    'P8_18': 'lo',

    # P8_19	7	gpio0[22]	OFF Switch
    'P8_19': 'in',

    # DEFAULTS
    # P8_20	2	mmc1_cmd	Reserved for internal EMMC
    # P8_21	2	mmc1_clk	Reserved for internal EMMC
    # P8_22	1	mmc1_dat5	Reserved for internal EMMC
    # P8_23	1	mmc1_dat4	Reserved for internal EMMC
    # P8_24	1	mmc1_dat1	Reserved for internal EMMC
    # P8_25	1	mmc1_dat0	Reserved for internal EMMC
    # P8_26
    # P8_27	0	lcd_vsync	Reserved for HDMI output
    # P8_28	0	lcd_pclk	Reserved for HDMI output
    # P8_29	0	lcd_hsync	Reserved for HDMI output
    # P8_30	0	lcd_ac_bias_en	Reserved for HDMI output
    # P8_31	0	lcd_data14	Reserved for HDMI output
    # P8_32	0	lcd_data15	Reserved for HDMI output
    # P8_33	0	lcd_data13	Reserved for HDMI output
    # P8_34	0	lcd_data11	Reserved for HDMI output
    # P8_35	0	lcd_data12	Reserved for HDMI output
    # P8_36	0	lcd_data10	Reserved for HDMI output
    # P8_37	0	lcd_data8	Reserved for HDMI output
    # P8_38	0	lcd_data9	Reserved for HDMI output
    # P8_39	0	lcd_data6	Reserved for HDMI output
    # P8_40	0	lcd_data7	Reserved for HDMI output
    # P8_41	0	lcd_data4	Reserved for HDMI output
    # P8_42	0	lcd_data5	Reserved for HDMI output
    # P8_43	0	lcd_data2	Reserved for HDMI output
    # P8_44	0	lcd_data3	Reserved for HDMI output
    # P8_45	0	lcd_data0	Reserved for HDMI output
    # P8_46	0	lcd_data1	Reserved for HDMI output

    # Unmodifiable
    # P9_01		GND
    # P9_02		GND
    # P9_03		DC_3.3V
    # P9_04		DC_3.3V
    # P9_05		VDD_5V
    # P9_06		VDD_5V
    # P9_07		SYS_5V
    # P9_08		SYS_5V
    # P9_09		PWR_BUT
    # P9_10		SYS_RESETn

    # P9_11	6	uart4_rxd_mux2	BMS serial rx line
    'P9_11': 'uart',

    # P9_12	7	gpio1[28]	Battery gauge clk signal
    'P9_12': 'lo',

    # P9_13	6	uart4_txd_mux2	BMS serial tx line
    'P9_13': 'uart',

    # P9_14
    # default

    # P9_15	7	gpio1[16]	Battery gauge data signal
    'P9_15': 'out',

    # P9_16
    # default

    # P9_17	0	spi0_cs0	Arduino SPI chip select
    'P9_17': 'spi',

    # P9_18	0	spi0_d1	Arduino SPI data in
    'P9_18': 'spi',

    # Defaults
    # P9_19
    # P9_20

    # P9_21	0	spi0_d0	Arduino SPI data out
    'P9_21': 'spi',

    # P9_22	0	spi0_sclk	Arduino SPI clock
    'P9_22': 'spi',

    # P9_23	7	gpio1[17]	Fuel gauge clk signal
    'P9_23': 'lo',

    # P9_24	0	uart1_txd	DeepSea serial tx line
    'P9_24': 'uart',

    # P9_25	7	gpio3[21]	Fuel gauge data signal
    'P9_25': 'lo',

    # P9_26	0	uart1_rxd	DeepSea serial rx line
    'P9_26': 'uart',

    # Defaults
    # P9_27
    # P9_28

    # P9_29	1	ehrpwm0B    Woodward RPM setpoint
    'P9_29': 'pwm',

    # P9_30
    # default

    # P9_31	1	ehrpwm0A    State of Charge analog
    'P9_31': 'pwm',

    # Not modifiable via pinmux
    # P9_32 VADC
    # P9_33 AIN4
    # P9_34 AGND
    # P9_35 AIN6
    # P9_36 AIN5
    # P9_37 AIN2
    # P9_38	n/a	AIN3	Generator current
    # P9_39	n/a	AIN0	High bus voltage
    # P9_40	n/a	AIN1	?

    # Defaults
    # P9_41
    # P9_42

    # Unmodifiable
    # P9_43		GND
    # P9_44		GND
    # P9_45		GND
    # P9_46		GND
}

# List of pin names
# DGND = P8_01
# DGND = P8_02
# P8_03
# P8_04
# P8_05
# P8_06
SPARE_SW = "P8_07"
DISK_ACT_LED = "P8_08"
USB_SW = "P8_09"
USB_LED = "P8_10"
HOLD_12V = "P8_11"
PID_LED = "P8_12"
ARCHIVE_SW = "P8_13"
SPARE_LED = "P8_14"
AUX_START = "P8_15"
CMS_WARN = "P8_16"
AUX_STOP = "P8_17"
CMS_FAULT = "P8_18"
OFF_SWITCH = "P8_19"
# P8_20
# P8_21
# P8_22
# P8_23
# P8_24
# P8_25
# P8_26
# P8_27
# P8_28
# P8_29
# P8_30
# P8_31
# P8_32
# P8_33
# P8_34
# P8_35
# P8_36
# P8_37
# P8_38
# P8_39
# P8_40
# P8_41
# P8_42
# P8_43
# P8_44
# P8_45
# P8_46
# DGND = P9_01
# DGND = P9_02
# DC_3.3V = P9_03
# DC_3.3V = P9_04
# +5V = P9_05
# +5V = P9_06
# P9_07
# P9_08
# P9_09
# P9_10
UART4_RX = "P9_11"
BAT_GG_CLK = "P9_12"
UART4_TX = "P9_13"
# P9_14
BAT_GG_DATA = "P9_15"
# P9_16
SPI0_CS0 = "P9_17"
SPI0_DI = "P9_18"
# P9_19
# P9_20
SPI0_DO = "P9_21"
SPI0_SCLK = "P9_22"
FUEL_CLK = "P9_23"
UART1_TX = "P9_24"
FUEL_DATA = "P9_25"
UART1_RX = "P9_26"
# P9_27
# P9_28
WW_PWM = "P9_29"
# P9_30
SOC_PWM = "P9_31"
# P9_32
# P9_33
# P9_34
# P9_35
PULSE_A2D = "P9_36"
# P9_37
GEN_CUR = "P9_38"
SIG_300V = "P9_39"  # Note: on V3 CMS Schematic, this is 300V_SIG
# P9_40
# P9_41
# P9_42
# DGND = P9_43
# DGND = P9_44
# DGND = P9_45
# DGND = P9_46
