#!/bin/bash
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
config-pin P8_07 in

# P8_08	7	gpio2[3]	Disk Activity LED
config-pin P8_08 out

# P8_09	7	gpio2[5]	USB switch
config-pin P8_09 in

# P8_10	7	gpio2[4]	Safe to remove LED
config-pin P8_10 out

# P8_11	7	gpio1[13]	Hold 12V (keep powered on after losing 24V)
config-pin P8_11 out

# P8_12	7	gpio1[12]	PID LED
config-pin P8_12 out

# P8_13	7	gpio0[23]	Switch: move logs to USB
config-pin P8_13 in

# P8_14	7	gpio0[26]	Spare LED
config-pin P8_14 out

# P8_15	7	gpio1[15]	Aux START (signal to the DeepSea to stop the motor)
config-pin P8_15 out

# P8_16	7	gpio1[14]	CMS Warn
config-pin P8_16 out

# P8_17	7	gpio0[27]	Aux STOP
config-pin P8_17 out

# P8_18	7	gpio2[1]	CMS Fault
config-pin P8_18 out

# DEFAULTS
# P8_19
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
config-pin P9_11 uart

# P9_12	7	gpio1[28]	Battery gauge clk signal
config-pin P9_12 out

# P9_13	6	uart4_txd_mux2	BMS serial tx line
config-pin P9_13 out

# P9_14
# default

# P9_15	7	gpio1[16]	Battery gauge data signal
config-pin P9_15 out

# P9_16
# default

# P9_17	0	spi0_cs0	Arduino SPI chip select
config-pin P9_17 spi

# P9_18	0	spi0_d1	Arduino SPI data in
config-pin P9_18 spi

# Defaults
# P9_19
# P9_20

# P9_21	0	spi0_d0	Arduino SPI data out
config-pin P9_21 spi

# P9_22	0	spi0_sclk	Arduino SPI clock
config-pin P9_22 spi

# P9_23	7	gpio1[17]	Fuel gauge clk signal
config-pin P9_23 out

# P9_24	0	uart1_txd	DeepSea serial tx line
config-pin P9_24 uart

# P9_25	7	gpio3[21]	Fuel gauge data signal
config-pin P9_25 out

# P9_26	0	uart1_rxd	DeepSea serial rx line
config-pin P9_26 uart

# Defaults
# P9_27
# P9_28

# P9_29	1	ehrpwm0B    Woodward RPM setpoint
config-pin P9_29 pwm

# P9_30
# default

# P9_31	1	ehrpwm0A    State of Charge analog
config-pin P9_31 pwm

# Not modifiable via pinmux
# P9_32 VADC
# P9_33 AIN4
# P9_34 AGND
# P9_35 AIN6
# P9_36 AIN5
# P9_37 AIN2
# P9_38	n/a	AIN3	High bus voltage
# P9_39	n/a	AIN0	Generator Amps (current shunt)
# P9_40	n/a	AIN1	?

# Defaults
# P9_41
# P9_42

# Unmodifiable
# P9_43		GND
# P9_44		GND
# P9_45		GND
# P9_46		GND
