# Woodward configuration - pulled out from config.py to make PID tuning updates easier.
{
    #The 'pin' value is set at boot and has no need to change later, so no reason for it to live in this file.
    #'pin': pins.WW_PWM,
    'Kp': 0.2,
    'Ki': 0.4,
    'Kd': 0.0,
    'slew': 25,  # In percent per second max change
    'setpoint': 25.0,  # Amps
    'period': 1.0
}
