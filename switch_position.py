import RPi.GPIO as GPIO


class PV_Switch:
    def __init__(self, gpio_number):
        self.gpio_number = gpio_number
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio_number, GPIO.IN)

    def is_switch_set_to_pv_only(self):
        return GPIO.input(self.gpio_number)
