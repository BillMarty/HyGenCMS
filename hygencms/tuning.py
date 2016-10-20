# Woodward configuration - pulled out from config.py to make PID tuning updates easier.
{
    'pin': pins.WW_PWM,
    'Kp': 0.0,
    'Ki': 0.5,
    'Kd': 0.0,
    'slew': 25,  # In percent per second max change
    'setpoint': 25.0,  # Amps
    'period': 1.0
}