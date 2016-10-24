"""
This module implements a simple closed-loop PID controller. The output
of the control loop is the duty cycle of a PWM pin, specified in
``wconfig['pin']``. The input is the ``process_variable`` member
variable of the ``WoodwardControl`` class. This member variable is set
externally. The tuning parameters of the PID loop are set based on the
configuration map passed into the constructor. Tunings can also be
adjusted on the fly, using the ``set_tunings`` function. The PID loop
also implements slew-rate limiting, which caps the maximum rate of
change for the output variable (in units of percent). This rate is set
by the configuration map in the constructor.

The PID loop was developed along the lines sketched out by a series of
blog posts which can be found
`here <http://brettbeauregard.com/blog/2011/04/improving-the-beginners-pid-introduction/>`_.

The ``WoodwardControl`` class also implements the ``csv_line`` and
``csv_header`` functions, which enable it to be used as a "data source"
in the main program loop. It returns five pieces of data: setpoint,
Kp, Ki, Kd, and current output percent.

As used in the HyGen, the output of this class, the PWM, is filtered
with a low-pass RC filter to make it a true analog value. This signal
then acts as the remote RPM setpoint for the Woodward engine
controller. Its input is set in the main program loop (``main.py``),
using the analog current input. It controls the RPM setpoint to
maintain the current at 25A.
"""

import time

from monotonic import monotonic

from . import pwm
from . import utils
from .asyncio import AsyncIOThread


class WoodwardControl(AsyncIOThread):
    """
    Control the Woodward.
    """
    # Define directions
    DIRECT = 0
    REVERSE = 1

    def __init__(self, wconfig, handlers):
        """
        :param wconfig:
            Configuration map for the Woodward.

        :param handlers:
            List of log handlers.
        """
        super(WoodwardControl, self).__init__(handlers)
        # Check configuration to ensure all values present
        WoodwardControl.check_config(wconfig)

        # Initialize member variables
        self.cancelled = False
        self._pin = wconfig['pin']
        self._sample_time = wconfig['period']
        self._direction = self.DIRECT
        self.setpoint = wconfig['setpoint']
        self.out_min = 0.0
        self.out_max = 100.0
        self.last_time = 0  # ensure that we run on the first time
        self._last_compute_time = 0
        self.process_variable = self.setpoint  # Start by assuming we are there
        self.last_input = self.process_variable  # Initialize
        self.integral_term = 0.0  # Start with no integral windup
        self.in_auto = False  # Start in manual control
        self.kp, self.ki, self.kd = None, None, None
        self.set_tunings(wconfig['Kp'],
                         wconfig['Ki'],
                         wconfig['Kd'])

        self._logger.info("Setting PID tunings: " + str(wconfig))

        try:
            self.slew = wconfig['slew']  # Units of % duty cycle / sec
        except KeyError:  # If not included in configuration
            self.slew = 100.0  # Effectively no limit, since range = 100

        # Mode switch: step or pid
        self.mode = 'pid'

        # Initialize the property for ideal output, output and PWM
        self._ideal_output = 0.0
        self._output = 0.0
        pwm.start(self._pin, 0.0, 100000)

        # { Step configuration
        # Values for step
        self.period = 20  # period in seconds
        self.on = False
        self.low_val = 40
        self.high_val = 50
        # }

        self._logger.info("Started Woodward controller")

    # Output property automatically updates
    def get_output(self):
        """RPM Setpoint"""
        return self._output

    def set_output(self, value):
        # Only set it if it's in the valid range
        if 0 <= value <= 100:
            pwm.set_duty_cycle(self._pin, value)
            self._output = value

    def del_output(self):
        # Maybe close PWM here
        del self._output

    output = property(get_output, set_output, del_output, "PWM Output Value")

    @staticmethod
    def check_config(wconfig):
        """
        Check to make sure all the required values are present in the
        configuration map.

        :param wconfig:
            Woodward configuration map
        """
        required_config = ['pin', 'Kp', 'Ki', 'Kd', 'setpoint', 'period']
        for val in required_config:
            if val not in wconfig:
                raise ValueError(
                    "Missing " + val + ", required for woodward config")
                # If we get to this point, the required values are present

    def set_tunings(self, kp, ki, kd):
        """Set new PID controller tunings.

        Kp, Ki, Kd are positive floats or integers that serve as the
        PID coefficients.

        :param kp:
            Proportional gain

        :param ki:
            Integral gain

        :param kd:
            Derivative gain
        """
        # We can't ever have negative tunings
        # that is accomplished with self.controller_direction
        if kp < 0 or ki < 0 or kd < 0:
            return
        self.kp = kp
        self.ki = ki * self._sample_time
        self.kd = kd / self._sample_time

        if self._direction == self.REVERSE:
            self.kp = -self.kp
            self.ki = -self.ki
            self.kd = -self.kd

    def set_controller_direction(self, direction):
        """
        Set the controller direction. Possible values:
        :const:`WoodwardControl.DIRECT`, :const:`WoodwardControl.REVERSE`
        """
        old_direction = self._direction
        if direction in [self.DIRECT, self.REVERSE]:
            self._direction = direction
            if direction != old_direction:
                # If we've changed direction, invert the tunings
                self.set_tunings(self.kp, self.ki, self.kd)

    def set_sample_time(self, new_sample_time):
        """
        Set the current sample time. The sample time is factored into
        the stored values for the tuning parameters, so recalculate
        those also.
        """
        if self._sample_time == 0:
            self._sample_time = new_sample_time
        elif new_sample_time > 0:
            ratio = float(new_sample_time) / self._sample_time
            self.ki *= ratio
            self.kd /= ratio
            self._sample_time = float(new_sample_time)

    def set_output_limits(self, out_min, out_max):
        """
        Set limits on the output. If the current output or integral term is
        outside those limits, bring it inside the boundaries.
        """
        if out_min < 0:
            out_min = 0
        if out_max > 100:
            out_max = 100

        if out_max < out_min:
            return
        self.out_min = out_min
        self.out_max = out_max

        if self.output < self.out_min:
            self.output = self.out_min
        elif self.output > self.out_max:
            self.output = self.out_max

        if self.integral_term < self.out_min:
            self.integral_term = self.out_min
        elif self.integral_term > self.out_max:
            self.integral_term = self.out_max

    def set_auto(self, new_auto):
        """
        Set whether we're in auto mode or manual.
        """
        if new_auto and not self.in_auto:
            self.initialize_pid()

        if new_auto != self.in_auto:
            self.in_auto = new_auto
            if new_auto:
                self._logger.info('Entering auto mode')
            else:
                self._logger.info('Exiting auto mode')

    def initialize_pid(self):
        """
        Initialize the PID to match the current output.
        """
        self.last_input = self.process_variable
        self._ideal_output = self.output
        self.integral_term = self.output
		
        now = monotonic()
        self.last_time = now
        self._last_compute_time = now

        if self.integral_term > self.out_max:
            self.integral_term = self.out_max
        elif self.integral_term < self.out_min:
            self.integral_term = self.out_min

    def compute(self):
        """
        Compute the next output value for the PID based on the member variables
        """
        if not self.in_auto:
            return self.output

        # Time for PID calculation
        now = monotonic()
        time_change = (now - self.last_time)

        # Slew-rate limiting
        dt = now - self._last_compute_time
        self._last_compute_time = now
        output = self.output

        if time_change >= self._sample_time:
            # Set output limits based on the slew rate
            self.set_output_limits(output - time_change * self.slew,
                                   output + time_change * self.slew)

            # Compute error variable
            error = self.setpoint - self.process_variable

            # Calculate integral term
            self.integral_term += error * self.ki
            if self.integral_term > self.out_max:
                self.integral_term = self.out_max
            elif self.integral_term < self.out_min:
                self.integral_term = self.out_min

            # Compute the proxy for the derivative term
            d_pv = (self.process_variable - self.last_input)

            # Compute output
            ideal_output = (self.kp * error +
                            self.integral_term -
                            self.kd * d_pv)
            if ideal_output > self.out_max:
                ideal_output = self.out_max
            elif ideal_output < self.out_min:
                ideal_output = self.out_min

            # Save variables for the next time
            self.last_time = now
            self.last_input = self.process_variable

            # Return the calculated value
        else:
            ideal_output = self._ideal_output

        # Move via the given slew rate to the ideal output
        if ideal_output == output:
            return output
        elif ideal_output > output + (self.slew * dt):
            self._ideal_output = ideal_output
            return output + self.slew * dt
        elif ideal_output < output - (self.slew * dt):
            self._ideal_output = ideal_output
            return output - self.slew * dt
        else:
            self._ideal_output = ideal_output
            return ideal_output

    def run(self):
        """
        Overloaded method from Thread.run. Start the control loop.
        """
        i = 0
        if self.mode == 'step':
            # If we're in step mode, we do a square wave
            half_period = 0.5 * self.period
            while not self.cancelled:
                # noinspection PyBroadException
                try:
                    # Period
                    if i >= half_period:
                        if self.on:
                            self.output = self.low_val
                        else:
                            self.output = self.high_val
                        self.on = not self.on
                        i = 0
                    i += 1
                    time.sleep(1.0)
                except Exception as e:
                    utils.log_exception(self._logger, e)

        elif self.mode == 'pid':
            while not self.cancelled:
                # noinspection PyBroadException
                try:
                    # output property automatically adjusts PWM output
                    self.output = self.compute()
                    time.sleep(0.1)  # avoid tight looping
                except Exception as e:
                    utils.log_exception(self._logger, e)

    ##########################
    # Methods from Main thread
    ##########################

    def print_data(self):
        """
        Print all the data as we currently have it, in human-
        readable format.
        """
        print("%20s %10s %10s" % ("PID enabled", str(self.in_auto), "T/F"))
        print("%20s %10.2f %10s" % ("PID output", self.output, "%"))
        print("%20s %10.2f %10s" % ("Setpoint A", self.setpoint, "A"))

        factor = 1
        if self._direction == self.REVERSE:
            factor = -1
        print("%20s %10.2f" % ("Kp", self.kp * factor))
        print("%20s %10.2f" % ("Ki", self.ki * factor / self._sample_time))
        print("%20s %10.2f" % ("Kd", self.kd * factor * self._sample_time))

    @staticmethod
    def csv_header():
        """
        Return the CSV header line.
        Does not include newline or trailing comma.

        :return:
            A string with the CSV header.
        """
        titles = ["pid_out_percent", "setpoint_amps", "kp", "ki", 'kd']
        return ','.join(titles)

    def csv_line(self):
        """
        Return a CSV line of the data we currently have.
        Does not include newline or trailing comma.

        :return:
            A string with the CSV data.
        """
        if self._direction == self.REVERSE:
            factor = -1
        else:
            factor = 1
        values = [
            str(self.output),
            str(self.setpoint),
            str(self.kp * factor),
            str(self.ki * factor / self._sample_time),
            str(self.kd * factor * self._sample_time),
        ]
        return ','.join(values)
