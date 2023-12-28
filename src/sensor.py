import numpy as np
import Adafruit_MCP3008  # for the analog-to-digital converter MCP3008
import random
import time

# Average over this many voltage recordings for each measurement, with the
# given delay between each recording.
# The continuous voltage at the top are single recordings.

N_MEASUREMENTS_EACH_SAMPLE = 32
DELAY_BETWEEN_READINGS = 0.02  # seconds

DEBUG = False
def debugprint(x):
    if DEBUG:
        print(x)

######################################################################
## class Sensor
##
## Interface with MCP3008 A/D chip.
## Methods read voltage from MCP3008, updates the continuous voltage display, and returns
## average of multiple samples
######################################################################

class Sensor():

    def __init__(self, key):
        self.key = key

        # Software SPI configuration:
        self.pin_on_MCP3008_for_spectro_volts = 0
        CLK  = 18
        MISO = 23
        MOSI = 24
        CS   = 25

        try:
            self.mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)
            self.connected = True
        except:
            self.mcp = None
            self.connected = False
            
    def read_and_display_voltage(self):
        if self.mcp:
            volts = self.mcp.read_adc(self.pin_on_MCP3008_for_spectro_volts)
            self.window['@random-volts-used'](visible=False)
        else:
            volts = random.normalvariate(500, 10)
            self.window['@random-volts-used'](visible=True)
            try:
                self.mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)
            except:
                self.mcp = None

        # Update display of binary volts
        self.window[self.key].update('{:.2f}'.format(volts))
        return volts

    def read_multiple_voltages(self):
        voltage_sum = 0
        for values in range(N_MEASUREMENTS_EACH_SAMPLE):
            time.sleep(DELAY_BETWEEN_READINGS)
            if self.mcp:
                volts = self.mcp.read_adc(self.pin_on_MCP3008_for_spectro_volts)
                self.window['@random-volts-used'](visible=False)
            else:
                volts = random.normalvariate(500, 10)
                self.window['@random-volts-used'](visible=True)
                try:
                    self.mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)
                except:
                    self.mcp = None
            voltage_sum += volts
        voltage_mean = voltage_sum / N_MEASUREMENTS_EACH_SAMPLE
        return voltage_mean

    def set_volts_zero_concentration(self, volts):
        self.volts_for_zero_concentration = volts

    def volts_to_absorbance(self, volts):
        # volts_for_zero_concentration set during recording of 0 concentration
        try:
            debugprint('{} {}'.format(self.volts_for_zero_concentration, volts))
            debugprint(self.volts_for_zero_concentration/ volts)
            debugprint(np.log10(self.volts_for_zero_concentration/volts))
            absorb = np.log10(self.volts_for_zero_concentration / volts)
        except Exception as ex:
            print(ex)
            print('WARNING: Ratio of zero concentrations volts to volts just measured is negative!')
            print('Using absorbance of 0.')
            absorb = 0
        return absorb

    def set_window(self, window):
        self.window = window
