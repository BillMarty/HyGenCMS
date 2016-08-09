#include <stdio.h>

/* Read in constantly from ADC pin _ and output result on PWM pin _ */

void setup_pwm(void);
short read_adc(void);
void set_pwm_frequency(void);

int main(void) {
	short count;

	setup_pwm();
	while (1) {

        
	}
	return 0;
}

short read_adc(void) {
	return 0;
}

void setup_pwm(void) {
	char export_path[] = "/sys/devices/platform/ocp/4830200.epwmss/"
						 "48302200.ehrpwm/pwm/pwmchip2/export";
	char enable_path[] = "/sys/devices/platform/ocp/4830200.epwmss/"
						 "48302200.ehrpwm/pwm/pwmchip2/export";
}


void set_pwm_frequency(void) {
	return;
}