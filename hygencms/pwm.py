import glob
import os.path as path
import time


class PwmPin:
    def __init__(self,
                 chip, addr, index, name, description,
                 period_path=None,
                 duty_path=None,
                 polarity_path=None,
                 duty=50.0,
                 freq=100000):
        self.chip = chip
        self.addr = addr
        self.index = index
        self.name = name
        self.description = description
        self.period_path = period_path
        self.duty_path = duty_path
        self.polarity_path = polarity_path
        self.period_ns = 0
        self.duty = duty
        self.freq = freq
        self.enabled = False


pins = {
    'P9_29': PwmPin(chip="48300000",
                    addr='48300200',
                    index=1,
                    name='WW_PWM',
                    description='PWM signal to Woodward RPM setpoint'),
    'P9_31': PwmPin(chip='48300000',
                    addr='48300200',
                    index=0,
                    name='SOC_PWM',
                    description='State of Charge analog signal'),
}

ocp_path = '/sys/devices/platform/ocp'


def start(key, duty_cycle=50.0, frequency=100000):
    """
    Start a PWM pin (export it)
    :param key: The pin ('P9_29' or 'P9_31')
    :param duty_cycle: Starting duty cycle
    :param frequency: Starting frequency
    :return: None
    """
    try:
        pin = pins[key]
    except KeyError:
        raise ValueError("PWM pin not implemented")

    chip_path = path.join(ocp_path,
                          pin.chip + '.epwmss')
    if not path.exists(chip_path):
        raise RuntimeError("Could not find PWM subsystem")

    try:
        addr_path = glob.glob(chip_path + '/*pwm')[0]
    except IndexError:
        raise RuntimeError("Could not find PWM address")

    try:
        pwm_path = glob.glob(addr_path + '/pwm/pwmchip?')[0]
    except IndexError:
        raise RuntimeError("Could not find any PWM chip")

    # Export the correct pin
    export_path = path.join(
        pwm_path,
        'export',
    )
    try:
        export_file = open(export_path, 'w')
    except IOError:
        raise RuntimeError("Could not find export file")
    else:
        export_file.write(str(pin.index))

    # Try to open the directory
    pwm_dir = path.join(
        pwm_path,
        'pwm' + str(pin.index)
    )

    period_path = path.join(pwm_dir, 'period')
    duty_cycle_path = path.join(pwm_dir, 'duty_cycle')
    polarity_path = path.join(pwm_dir, 'polarity')
    enable_path = path.join(pwm_dir, 'enable')
    if not path.exists(period_path) \
            and path.exists(duty_cycle_path) \
            and path.exists(enable_path) \
            and path.exists(polarity_path):
        raise RuntimeError("Missing sysfs files")

    pin.period_path = period_path
    pin.duty_path = duty_cycle_path
    pin.polarity_path = polarity_path
    pin.duty = 0
    pin.freq = 0

    set_frequency(key, frequency)
    set_duty_cycle(key, duty_cycle)

    # It sometimes takes a bit to open
    enabled = False
    tries = 0
    while not enabled and tries < 100:
        time.sleep(0.01)
        try:
            with open(enable_path, 'w') as f:
                f.write('1')
        except OSError:
            tries += 1
        else:
            enabled = True

    if tries >= 100:
        print("Couldn't enable {:s}".format(key))
    else:
        pin.enabled = True


def set_frequency(key, freq):
    try:
        pin = pins[key]
    except KeyError:
        raise ValueError("Unimplemented key")

    if not pin.enabled:
        raise RuntimeError("Pin has not been initialized")

    if pin.freq == freq:
        return  # nothing to do

    period_ns = int(1e9 / float(freq))
    try:
        with open(pin.period_path, 'w') as f:
            f.write(str(period_ns))
    except OSError as e:
        print("Error writing to {:s}: {:s}".format(pin.period_path, str(e)))
    pin.period_ns = period_ns
    pin.freq = freq
    set_duty_cycle(key, pin.duty)  # stay constant after changing period


def set_duty_cycle(key, duty):
    try:
        pin = pins[key]
    except KeyError:
        raise ValueError("Unimplemented key")

    if not pin.enabled:
        raise RuntimeError("Pin has not been initialized")

    if not 0 <= duty <= 100:
        raise ValueError("Duty cycle must be between 0 and 100 percent")

    duty_cycle = int(pin.period_ns * (duty / 100))
    try:
        with open(pin.duty_path, 'w') as f:
            f.write(str(duty_cycle))
    except OSError as e:
        print("Error writing to {:s}: {:s}".format(pin.duty_path, str(e)))
    pin.duty = duty
