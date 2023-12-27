# spectrometer.py


```python
# Set DEBUG to True to produce output while running to help DEBUGging
DEBUG = False
SHOW_TEST_BUTTON = True

######################################################################
## import required packages
######################################################################

import PySimpleGUI as sg
import numpy as np
import os
import sensor
import model
import table
import usb

######################################################################
## Setting display parameters
######################################################################

sg.theme('DefaultNoMoreNagging')
sg.set_options(font=('latin modern roman', 16, 'bold'))

def debugprint(x):
    if DEBUG:
        print(x)

######################################################################
## Set initial values for global variables
######################################################################

measured_samples = []  #[sample id, volts, absorbance, concentration]

# Set spectro to Sensor object to access Spectrophotometer through Raspberry Pi
spectro = sensor.Sensor('@Volts')

# Initialize model
model = model.Model('@calibration-plot', '@measuring-plot')

# functions to call given key events
key_function = {}

######################################################################
#### Layouts and associated functions
######################################################################

# Main Screen
# Layouts

heading = [[sg.Text("Seth's Spectacular Spectrophotometer", size=(50, 1), justification='center',
                    font=('latin modern roman', 24, 'bold'))],
           [sg.Text('Charles W. Anderson, Seth H. Frisbie, Erika J. Mitchell, and Kenneth R. Sikora',
                    size=(80, 1),
                    justification='right', font=('latin modern roman', 12, 'bold'))],
           [sg.Text('\"It\'s the questions that drive us, Mr. Anderson" -- Agent Smith (The Matrix)',
                    size=(75, 1),
                    justification='right', font=('latin modern roman', 14, 'italic'))],
           [sg.Text('Spectrophotometer is not connected. Random voltage values will be used.',
                    key='@random-volts-used', visible=False, justification='center',
                    size=(75, 1), font=('latin modern roman', 16, 'bold'), text_color='red')]]

layout_voltage = [[sg.Column([[sg.Frame('', [
    [sg.Text(size=(8, 2),
             justification='right', key='@Volts'),
     sg.Text('binary volts', size=(15, 2), 
             justification='left')]], size=(340, 50))]])]]

######################################################################
### Calibration Panel 1, choose expected equation

# Layouts

all_calibration_layouts = []
all_calibration_keys = []

panel_calibration_equation_form = [[sg.pin(sg.Column([
    [sg.Text('Do you expect a linear or quadratic calibration equation?')],
    [sg.Radio('Linear', 'CalForm', default=False, key='@linear', enable_events=True)],
    [sg.Radio('Quadratic', 'CalForm', default=False, key='@quadratic', enable_events=True)],
    [sg.Text('', key='@n-samples-needed', visible=True)],
    [sg.Text('Put the zero concentration standard in the holder.\n'
    'Use the potentiometers on the spectrophotometer to carefully\n'
    'adjust the voltage to approximately 1,000 binary volts.\n'
    'Click OK when this is done.',
             key='@put-zero-standard', visible=False),
    sg.Button('Ok', key='@zero-conc-ok', visible=False)]],
                                                     visible=True,
                                                     key='@cal-equation-form'))]]

all_calibration_layouts += panel_calibration_equation_form
all_calibration_keys.append('@cal-equation-form')

# Functions

want_linear_calibration = False
want_quadratic_calibration = False
    
def equation_form_chosen(form):
    global want_linear_calibration, want_quadratic_calibration
    
    want_linear_calibration = want_quadratic_calibration = False

    if form == 'linear':
        window['@n-samples-needed'].update('You will need a minimum of 4 calibration standards,\n'
                                            'including the blank, for a statistical line.')
        want_linear_calibration = True
    else:
        window['@n-samples-needed'].update('You will need a minimum of 5 calibration standards,\n'
                                           'including the blank, for a statistical line.')
        want_quadratic_calibration = True
    window['@put-zero-standard'].update(visible=True)
    window['@zero-conc-ok'].update(visible=True)
    
key_function['@linear'] = lambda event_not_used, values_not_used: equation_form_chosen('linear')
key_function['@quadratic'] = lambda event_not_used, values_not_used: equation_form_chosen('quadratic')

def zero_conc_ok(event, values_not_used):
    volts = spectro.read_multiple_voltages()
    spectro.set_volts_zero_concentration(volts)

    model.clear_calibration_samples()
    model.add_calibration_sample(0, volts, spectro.volts_to_absorbance(volts))
    calibration_samples_table.set_samples(model.samples)
    make_calibration_layout_visible('@cal2')
    window['@record-cal'].update(disabled=False)
    calibration_samples_table.refresh()


key_function['@zero-conc-ok'] = zero_conc_ok

######################################################################
### Calibration Panel 2, collecting samples

# Layouts

calibration_samples_table = table.Table('@cal-table',
                                        [], 
                                        ('Concentration', 'Binary Volts', 'Absorbance'),
                                        spectro)

panel_calibration_samples = [[sg.pin(sg.Column([
    [sg.Column([[sg.Button('Load Test Samples', key='@load-samples'),
                 sg.Text('to test with predefined samples.')]],
               visible=True)], 
    [sg.Text('Place a new standard in the holder.')],
    [sg.Text('What is the concentration of this standard?'),


     sg.Input(key='@concentration', size=(10, 2)),
     sg.Text(' ', key='@concentration-error')],
    [sg.Column([
        [sg.Text('                                         '),
         sg.Button('Record', key='@record-cal', disabled=True),
         sg.Button('Done Recording', key='@done-recording-cal', disabled=True)]],
               element_justification='right', expand_x=True)],
    [sg.Text('', key='@nmore')],
    [calibration_samples_table.make_sgTable()]], visible=False, key='@cal2'))]]

all_calibration_layouts += panel_calibration_samples
all_calibration_keys.append('@cal2')

# Functions

def make_calibration_layout_visible(visible_layout_key):
    for layout_key in all_calibration_keys:
        debugprint('layout_key={}'.format(layout_key))
        window[layout_key].update(visible=False)
    window[visible_layout_key].update(visible=True)

### Add ability to preload testing data for calibration samples.

simulate_trend = None

# Functions

def set_trend_test(key, values_not_used):
    global simulate_trend
    simulate_trend = key[1:key.index('-test')]

def load_samples(key, values_not_used):
    global window_load_samples
    layout_select_testing_data = [
            [sg.Text('TESTING. Choose test data to load.')],
            [sg.Radio('linear no intercept', 'TrendForm', default=False,
                      key='@linear-no-intercept-test', enable_events=True),
             sg.Radio('linear with intercept', 'TrendForm', default=False,
                      key='@linear-intercept-test', enable_events=True)],
            [sg.Radio('quadratic no intercept', 'TrendForm', default=False,
                      key='@quadratic-no-intercept-test', enable_events=True),
             sg.Radio('quadratic with intercept', 'TrendForm', default=False,
                      key='@quadratic-intercept-test', enable_events=True)],
            [sg.Radio('no trend', 'TrendForm', default=False,
                      key='@no-trend-test', enable_events=True),
             sg.Radio('cubic', 'TrendForm', default=False,
                      key='@cubic-test', enable_events=True)],
            [sg.Button('Done', key='@done-loading-samples')]]
    window_load_samples = sg.Window("Load Test Samples", layout_select_testing_data,
                                    finalize=True)

def done_loading_samples(key, values):
    global window_load_samples
    test_data = [k for (k, v) in values.items() if v][0]
    # Trim leading @ and trailing '-test'
    test_data = test_data[1:test_data.index('-test')]
    model.set_calibration_samples_for_testing(test_data)
    calibration_samples_table.set_samples(model.samples)
    spectro.set_volts_zero_concentration(model.samples[0][1])
    calibration_samples_table.refresh()    
    window_load_samples.close()
    main_window['@done-recording-cal'].update(disabled=False)
    
key_function['@no-trend-test'] = set_trend_test
key_function['@linear-no-intercept-test'] = set_trend_test
key_function['@linear-intercept-test'] = set_trend_test
key_function['@quadratic-no-intercept-test'] = set_trend_test
key_function['@quadratic-intercept-test'] = set_trend_test
key_function['@cubic-test'] = set_trend_test
key_function['@done-loading-samples'] = done_loading_samples
key_function['@load-samples'] = load_samples

### End of testing data loading

## Check for valid numerical input in text boxes

def check_input(input_key, convert_f, error_key, error_message):
    inputbox_text = values[input_key]
    errorbox = window[error_key]
    if len(inputbox_text) > 0:
        try:
            n_measurements = convert_f(inputbox_text)
            errorbox.update('')
            return n_measurements
        except:
            errorbox.update(error_message, text_color='red')
            return None

def record_calibration_sample(event, values_not_used):
    # global recording_calibration_samples

    # recording_calibration_samples = True
    conc = check_input('@concentration', float, '@concentration-error', 'Must be a number.')            
    if conc and event == '@record-cal':
        # Read mean of multiple voltages
        mean_volts = spectro.read_multiple_voltages()
        # Add sample to calibration_samples_table
        model.add_calibration_sample(conc, mean_volts, spectro.volts_to_absorbance(mean_volts))
        calibration_samples_table.set_samples(model.samples)
        calibration_samples_table.refresh()
        n_calibration_recordings = len(model.samples)
        # Enable the "Done Recording" button if enough calibration samples
        # Clear the concentration field window
        window['@concentration']('')
        # have been collected for 
        if ((want_quadratic_calibration and n_calibration_recordings >= 5)
            or
            (want_linear_calibration and n_calibration_recordings >= 4)):
            window['@done-recording-cal'].update(disabled=False)
        if want_quadratic_calibration:
            window['@nmore'].update('You need a minimum of {} more calibration standards for a '
                                    'statistical curve.'.format(max(5 - n_calibration_recordings, 0)))
        elif want_linear_calibration:
            window['@nmore'].update('You need a minimum of {} more calibration standards for a '
                                    'statistical curve.'.format(max(4 - n_calibration_recordings, 0)))

key_function['@record-cal'] = record_calibration_sample

def done_recording(event, values_not_used):
    # recording_calibration_samples = False
    calibration_samples = np.array(model.samples) # np.array(calibration_samples)
    debugprint(calibration_samples)

    ### Algorithm for checking trends and y intercepts.
    
    # If quadratic wanted:
    #     Test for cubic trend.
    #     If cubic found:
    #         "Please recalibrate"
    #     Else cubic not found:
    #         Test for quadratic.
    #         If quadratic found:
    #             Test for y-intercept non-zero.
    #             If y-intercept is non-zero;
    #                 Ask "Use or recalibrate?"
    #             Else y-intercept is zero:
    #                 Use this calibration and move to "Measure Concentration".
    #         Else quadratic not found:
    #             Test for linear.
    #             If linear found:
    #                 Test for y-intercept non-zero.
    #                 if y-intercept is non-zero:
    #                     Ask "Use or Recalibrate?"
    #                 Else y-intercept is zero:
    #                     Ask "Use or Recalibrate?"
    #             Else linear not found:
    #                 "Please recalibrate"

    # If linear wanted:
    #     Test for quadratic.
    #     If quadratic found:
    #         "Please recalibrate."
    #     Else quadratic not found:
    #         Test for linear.
    #         If linear found:
    #             Test for y-intercept non-zero.
    #             if y-intercept is non-zero:
    #                 Ask "Use or Recalibrate?"
    #             Else y-intercept is zero:
    #                 Ask "Use or Recalibrate?"
    #                 (previous step here was: Move to "Measure Concentration")
    #         Else linear not found:
    #             "Please recalibrate"

    if want_quadratic_calibration:

        debugprint('WANT QUADRATIC')

        if model.significant_cubic():  # calls model.train([0, 1, 2, 3])

            debugprint('cubic found')
            model.update_calibration_plot()
            ask_to_recalibrate(
                'Your calibration equation has a signficant cubic trend.') #. Please recalibrate')

        else:

            if model.significant_quadratic():  # calls model.train([0, 1, 2])

                debugprint('quadratic found')
                if model.significant_y_intercept():
                    debugprint('y_intercept found')
                    model.update_calibration_plot()
                    ask_use_or_recalibrate(
                        'Your calibration equation does not go through the origin (0,0);\n'
                        'more specifically, it has a statistically significant y-intercept\n'
                        'at the 95% confidence level.')
                else:
                    debugprint('no y intercept')
                    model.update_calibration_plot()
                    ask_use_or_recalibrate(
                        'Your calibration equation has a significant quadratic trend and the y-intercept is zero.')

            elif model.significant_linear():  # calls model.train([0, 1])

                debugprint('linear found')
                if model.significant_y_intercept():
                    debugprint('y_intercept found')
                    model.update_calibration_plot()
                    ask_use_or_recalibrate(
                        'Your calibration equation is linear and does not go through the origin (0,0).\n'
                        'More specifically, your calibration does not have a statistically significant\n'
                        'quadratic trend at the 95% confidence level; however it does have a statistically\n'
                        'significant linear trend at the 95% confidence level. And it has a statistically\n'
                        'significant y-intercept at 95% confidence level.')
                else:

                    debugprint('no y_intercept')
                    model.update_calibration_plot()
                    ask_use_or_recalibrate(
                        'Your calibration equation is linear, not quadratic. More specifically, your calibration\n'
                        'does not have a statistically significant quadratic trend at the 95% confidence level;\n'
                        'however, it does have a statistically significant linear trend at the 95% confidence level.')
            else:

                debugprint('no trend found')
                model.update_calibration_plot()
                ask_to_recalibrate(
                    'Your calibration equation does not have a significant trend.') # Please recalibrate')

    if want_linear_calibration:
        debugprint('WANT LINEAR')
        if model.significant_quadratic():  # calls model.train([0, 1, 2])

            debugprint('quadratic found')
            model.update_calibration_plot()
            ask_to_recalibrate(
                'Your calibration equation has a signficant quadratic trend.') #  Please recalibrate')

        else:
            if model.significant_linear():  # calls model.train([0, 1])

                debugprint('linear found')
                if model.significant_y_intercept():
                    debugprint('y intercept found')
                    model.update_calibration_plot()
                    ask_use_or_recalibrate(
                        'Your calibration equation does not go through the origin (0,0);\n'
                        'more specifically, it has a statistically significant y-intercept\n'
                        'at the 95% confidence level.')
                else:

                    debugprint('no intercept found')
                    model.update_calibration_plot()
                    ask_use_or_recalibrate(
                        'Your calibration equation has a significant linear trend and the y-intercept is zero.')
                    # move_to_measure_concentration()
            else:

                debugprint('no trend found')
                model.update_calibration_plot()
                ask_to_recalibrate(
                    'Your calibration equation does not have a signficant linear trend.') # Please recalibrate')

key_function['@done-recording-cal'] = done_recording

######################################################################
### Calibration Panel 3, ask to accept or recalibrate if not immediately accepted

# Layouts

calibration_panel_ask = [[sg.pin(sg.Column([
    [sg.pin(sg.Column([[sg.Text('', key='@trend-status-ok')],
                       [sg.Text('Please recalibrate.'), sg.Button('Ok', key='@recalibrate1')]],
                      key='@just-recalibrate'))],
    [sg.pin(sg.Column([[sg.Text('', key='@trend-status-ask')],
                       [sg.Text('Do you want to use this calibration equation,\n'
                       'or do you want to recalibrate?'), sg.Button('Use', key='@use'),
                       sg.Button('Recalibrate', key='@recalibrate2')]],
                      key='@use-or-recalibrate'))],
    [sg.Canvas(key='@calibration-plot')]],
                                           visible=False, key='@ask-recalibrate'))]]
all_calibration_layouts += calibration_panel_ask
all_calibration_keys.append('@ask-recalibrate')

# Functions

def ask_to_recalibrate(text):
    window['@trend-status-ok'].update(text)
    make_calibration_layout_visible('@ask-recalibrate')
    window['@use-or-recalibrate'].update(visible=False)
    window['@just-recalibrate'].update(visible=True)
    debugprint("window['@calibration-plot'])")
    debugprint(window['@calibration-plot'])
    
def ask_use_or_recalibrate(text):
    window['@trend-status-ask'].update(text)
    make_calibration_layout_visible('@ask-recalibrate')
    window['@use-or-recalibrate'].update(visible=True)
    window['@just-recalibrate'].update(visible=False)
        
first_time_measuring = True
def use_calibration(event=None, values_not_used=None):
    global first_time_measuring
    first_time_measuring = True
    debugprint('changing selection to measure tab')
    window['@measure-tab'].update(disabled=False)  # Set to false when calibration done
    window['@measure-tab'].select()
    
def move_to_measure_concentration():
    use_calibration()
    
key_function['@use'] = use_calibration

def recalibrate(event, values_not_used):
    
    model.clear_calibration_samples()
    calibration_samples_table.set_samples(model.samples)
    make_calibration_layout_visible('@cal-equation-form')
    window['@done-recording-cal'].update(disabled=True)
    window['@cal-equation-form'].update(visible=True)
    
key_function['@recalibrate1'] = recalibrate
key_function['@recalibrate2'] = recalibrate

######################################################################
### Measuring Panel

# Layouts

measured_samples = []  #[sample id, volts, absorbance, concentration]

measured_samples_table = table.Table('@measure-table',
                                     measured_samples,
                                     ('Sample ID', 'Binary Volts', 'Absorbance', 'Concentration'),
                                     spectro)

measuring_panel = [[sg.Column([
    [sg.Canvas(key='@measuring-plot')],
    [sg.Text('Sample ID'), sg.Input(key='@ID', size=15), sg.Button('Record', key='@measure')],
    [measured_samples_table.make_sgTable()],
    [sg.Text('When you are ready to save these values, please insert a USB drive into the Raspberry Pi.', key='@insert-usb', visible=False)],
    # when inserted, the above row will disappear and the following row will appear
    [sg.Text('Enter file name:', key='@enter-filename', visible=True),
     sg.Input(key='@filename', size=20, default_text='', visible=True),
     sg.Button('Save', key='@save', disabled=True, visible=True)],
    [sg.pin(sg.Text(key='@lines-saved', visible=False))]])]]

# Functions

def measure(key_not_used, values_not_used):
    # Read multiple voltages and return their average.
    mean_volts = spectro.read_multiple_voltages()
    # convert volts to absorbances and display.
    absorbance = spectro.volts_to_absorbance(mean_volts)
    # use model to convert absorbance to concentration, and display
    concentration = model.use(absorbance)
    # The "Measure" button clicked, so add this sample to the measured_samples_table.
    id = window['@ID'].get()
    if DEBUG:
        debugprint(id, mean_volts, absorbance, concentration)
    measured_samples_table.add([id, mean_volts, absorbance, concentration])
    # Refresh the table display
    window['@ID'].update('')
    measured_samples_table.refresh()

def save(event, values_not_used):
    filename = window['@filename'].get()
    if not filename.endswith('.csv'):
        filename += '.csv'
    if os.path.exists(filename):
        main_window['@lines-saved'].update(visible=False)
    else:
        success, msg = measured_samples_table.save(filename, ('Sample ID', 'Binary Volts', 'Absorbance', 'Concentration'))
        main_window['@lines-saved'].update(msg)
        main_window['@lines-saved'].update(visible=True)

key_function['@measure'] = measure
key_function['@save'] = save

######################################################################
#### Set up the TabGroup for the Calibration tab panel and the Measure Concentration tab panel

tab_group = sg.TabGroup([[
    sg.Tab('Calibration', all_calibration_layouts, key='@calibration-tab', border_width=5),
    sg.Tab('Measure Concentration', measuring_panel, key='@measure-tab', border_width=5)]],
                        tab_location='topleft', border_width=5)

tabbed_layout = [[tab_group], [sg.Push(), sg.Button('Quit')]]

######################################################################
#### Define screen as heading, voltage, and tabbed panel layouts

screen = heading + layout_voltage + tabbed_layout  # layout_calibrate + layout_sample


######################################################################
## Define PySimpleGUI main window and initialize calibration and measured sample tables.

main_window = sg.Window('Spectrophotometer', screen, finalize=True)
spectro.set_window(main_window)
model.set_window(main_window)
calibration_samples_table.set_window(main_window)
measured_samples_table.set_window(main_window)

# recording_calibration_samples = False
main_window['@measure-tab'].update(disabled=True)  # Set to false when calibration done

if simulate_trend is not None:
    main_window['@done-recording-cal'].update(disabled=False)

######################################################################
######################################################################
## Start main loop
######################################################################
######################################################################

while True:

    # Read events and values from PySimpleGUI components that have changed state
    # event, values = window.read(timeout=500)  # milliseconds
    window, event, values = sg.read_all_windows(timeout=500)  # milliseconds

    if DEBUG and event != '__TIMEOUT__':
        print('event={} values={} tab_group.Get()= {}'.format(event, values, tab_group.Get()))

    # Close application if window is closed or Quit is clicked
    if event in (sg.WIN_CLOSED, 'Quit'):  # Closed window or clicked Quit button
        window.close()
        try:
            if window == window_load_samples:
                window_load_samples = None
            else:
                break
        except:
            break

    # Determine which tab panel is showing
    if tab_group.Get() == '@calibration-tab':
        tab = 'calibrating'
    else:
        tab = 'measuring'

    # Read and display current volts
    volts = spectro.read_and_display_voltage()
    if tab == 'measuring':
        # Display equation found by inverting calibration curve.
        if first_time_measuring:
            model.update_measuring_plot()
            first_time_measuring = False
            # Read multiple voltages and return their average.
            mean_volts = spectro.read_multiple_voltages()
            # convert volts to absorbances and display.
            absorbance = spectro.volts_to_absorbance(mean_volts)
            # use model to convert absorbance to concentration, and display
            concentration = model.use(absorbance)

    # Handle editting table cells
    if isinstance(event, tuple):
        if event[0] == '@cal-table':
            row, col = event[2]
            if row is not None:
                calibration_samples_table.edit_cell('@cal-table',  row + 1, col)

        elif event[0] == '@measure-table':
            row, col = event[2]
            if row is not None:
                measured_samples_table.edit_cell('@measure-table',  row + 1, col)

        continue

    ####  Handle all other events by calling function sassociated with event in
    ####  key_function dictionary

    if event != '__TIMEOUT__':
        key_function[event](event, values)

    if tab == 'measuring':
        usb_found = usb.usb_inserted()
        debugprint('usb_found {}'.format(usb_found))
        main_window['@insert-usb'].update(visible=not usb_found)
        main_window['@enter-filename'].update(visible=usb_found)
        main_window['@filename'].update(visible=usb_found)
        main_window['@save'].update(visible=usb_found)
        main_window['@save'].update(disabled=False)

window.close()
```

# sensor.py

```python
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
```


# model.py

```python
DEBUG = False

import numpy as np
import math
import scipy.stats as ss
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

plt.rcParams.update({
    "figure.facecolor":  (1.0, 0.0, 0.0, 0.0),
    "axes.facecolor":    (0.5, 0.5, 0.5, 0.0),  # green with alpha = 50%
    })

def debugprint(x):
    if DEBUG:
        print(x)

######################################################################
## class Model
##
## Fits calibration model to samples.
## Checks for signficance of coefficients.
## Produces plots and equations.
######################################################################

class Model():

    def __init__(self, calibration_key, measuring_key):
        self.model = None
        self.samples = []
        self.calibration_figure = plt.figure(figsize=(7, 4), dpi=100, facecolor=(0.8, 0.8, 0.8))
        self.calibration_axis = self.calibration_figure.add_subplot(111)  #, facecolor=(0.6, 0.8, 0.6))
        self.measuring_figure = plt.figure(figsize=(9, 0.3), facecolor=(0.8, 0.8, 0.8))
        self.measuring_axis = self.measuring_figure.add_subplot(111)
        self.calibration_key = calibration_key
        self.measuring_key = measuring_key
        self.calibration_canvas = None
        self.measuring_canvas = None
        
    def set_window(self, window):
        self.window = window
        
    def clear_calibration_samples(self):
        self.samples = []
        
    def add_calibration_sample(self, concentration, mean_volts, absorbance):
        self.samples.append([concentration, mean_volts, absorbance])
        
    def get_samples(self):
        return np.array(self.samples)
    
    def get_n_samples(self):
        return len(self.samples)
    
    def set_calibration_samples_for_testing(self, simulate_trend):
        self.samples = calibration_samples_for_testing[simulate_trend]
        
    def set_calibration_samples(self, samples):
        self.samples = samples
        
    def make_X_powers(self, X, powers):
        return np.hstack([X[:, c:c+1] ** powers for c in range(X.shape[1])])

    def train(self, powers=[0, 1, 2, 3]):
        # each sample is concentration, volts, absorbance
        samps = np.array(self.samples)
        X = samps[:, 0:1]  # concentration
        T = samps[:, 2:3]  # absorbance
        X = self.make_X_powers(X, powers)
        W = np.linalg.lstsq(X, T, rcond=None)[0]
        Y = X @ W
        n, p = X.shape
        MSE = np.sum((T - Y)**2) / (n - p)
        Sxx_inv = np.linalg.pinv(X.T @ X)
        SE_W = np.sqrt(MSE * Sxx_inv.diagonal().reshape(-1, 1))
        t_W = W / SE_W
        p_values = np.array([2 * (1 - ss.t.cdf(np.abs(tw), n - p)) for tw in t_W]).reshape(-1, 1)
        t_ppf = ss.t.ppf(1 - 0.025, n - p)
        half_interval = t_ppf * SE_W
        CI = np.hstack((W - half_interval, W + half_interval))
        R2 = 1 - np.sum((T - Y)**2) / np.sum((T - np.mean(T))**2)
        if n > p:
            R2adj = 1 - (1 - R2) * (n - 1) / (n - p)
        else:
            R2adj = np.nan
        self.model = {'powers': powers,
                      'coef': W.ravel(),
                      'std err': SE_W.ravel(),
                      't': t_W.ravel(),
                      'P>|t|': p_values.ravel(),
                      '[0.025': CI[:, 0],
                      '0.975]': CI[:, 1],
                      'R-squared': R2,
                      'Adj. R-squared': R2adj}
        return self.model

    def confidence_interval_does_not_include_zero(self, coefficient_index):
        low = self.model['[0.025'][coefficient_index]
        high = self.model['0.975]'][coefficient_index]
        return  low * high > 0 # different signs return True

    def significant_linear(self):
        self.train([0, 1])
        return self.confidence_interval_does_not_include_zero(1)

    def significant_quadratic(self):
        self.train([0, 1, 2])
        return self.confidence_interval_does_not_include_zero(2)

    def significant_cubic(self):
        self.train([0, 1, 2, 3])
        return self.confidence_interval_does_not_include_zero(3)

    def significant_y_intercept(self):
        sig_y = self.confidence_interval_does_not_include_zero(0) 
        if not sig_y:
            self.model['coef'][0] = 0  # set to zero because y intercept not significant
        return sig_y
        
    def use(self, absorbance):
        if len(self.model['coef']) == 3:
            # absorbance is quadratic function of concentration
            # To solve for concentration, use quadratic discriminant function
            # ab = a conc^2 + b conc + c
            # conc = (-b +- sqrt(b^2 - 4 a (c - ab))) / 2a
            c, b, a = self.model['coef']
            try:
                sqrt = math.sqrt(b * b - 4 * a * (c - absorbance))
            except:
                debugprint('In model.use. sqrt is nan. Returning 0 for concentration.')
                return 0
            conc1, conc2 = (-b + sqrt) / (2 * a), (-b - sqrt) / (2 * a)

            samps = np.array(self.samples)
            self.min_concentration = samps[:, 0].min()
            self.max_concentration = samps[:, 0].max()

            test1 = self.min_concentration <= conc1 <= self.max_concentration
            test2 = self.min_concentration <= conc2 <= self.max_concentration
            if test1 and not test2:
                return conc1
            if test2 and not test1:
                return conc2
            else:
                debugprint('Both concentrations within range. Using first one')
                return conc1

        elif len(self.model['coef']) == 2:
            # linear model, absorb = a conc + b
            # so conc = (absorb - b) / a
            b, a = self.model['coef']
            conc = (absorbance - b) / a
            return conc

        else:
            debugprint('Cannot use cubic model')
            return None

    def format_model_equation(self):
        f = mticker.ScalarFormatter(useMathText=True)
        f.set_powerlimits((-3, 3))
        coefficients = self.model['coef']
        powers = self.model['powers']
        s = 'Absorbance = '
        make_two_lines = False
        for i in reversed(range(len(self.model['powers']))):
            p = self.model['powers'][i]
            if p > 1:
                c = coefficients[i]
                if s[-2] == '=':
                    # first term
                    sgn = ''
                else:
                    sgn = '\;-\;' if c < 0 else '\;+\;'
                    c =  np.abs(c)
                s += '${} {:.3f} \; (Concentration)^{} $'.format(sgn, c, p)
            elif p == 1:
                c = coefficients[i]
                if s[-2] == '=':
                    # first term
                    sgn = ''
                else:
                    sgn = '\;-\;' if c < 0 else '\;+\;'
                    c = np.abs(c)
                s += '${} {:.3f} \; (Concentration) $'.format(sgn, c)
            else:
                c = coefficients[i]
                debugprint(c)
                if np.abs(c) > 0.0005:
                    if s[-2] == '=':
                        # first term
                        sgn = ''
                    else:
                        sgn = '\;-\;' if c < 0 else '\;+\;'
                        c = np.abs(c)
                    s += '${} {:.3f}$'.format(sgn, c)
        return s

    def format_concentration_equation(self):
        f = mticker.ScalarFormatter(useMathText=True)
        f.set_powerlimits((-3, 3))
        pm = r'\pm'
        sqrt = r'\sqrt'
        s = 'Concentration ='
        if len(self.model['coef']) == 3:
            c, b, a = self.model['coef']
            stra = '{:.3f}'.format(a)
            strb = '{:.3f}'.format(b)
            if c != 0:
                strc = '{:.3f}'.format(c)
            else:
                strc = ''
            s += ' $( -{} {} {}{{({})^2 - 4 ({}) ({} - absorbance)}})\; / \;( 4 ({})^2)$'.format(strb, pm, sqrt, strb, stra, strc, stra)

        elif len(self.model['coef']) == 2:
            # linear
            b, a = self.model['coef']
            stra = '({:.3f})'.format(a) if a < 0 else '{:.3f}'.format(a)
            if b != 0:
                sgn = '\;+\;' if b < 0 else '\;-\;'
                strb = '{} {:.3f}'.format(sgn, b)
                s += '$(Absorbance {})\; /\; {}$'.format(strb, stra)
            else:
                strb = ''
                # s += f' $(absorbance) \; /\; {stra}$'
                s += ' $(Absorbance \; / \; {})$'.format(stra)

        return s

    def get_canvas(self, figure, key):
        return FigureCanvasTkAgg(figure, self.window[key].TKCanvas).get_tk_widget()

    def update_calibration_plot(self):
        if self.calibration_canvas:
            self.calibration_canvas.forget()
        self.calibration_canvas = self.get_canvas(self.calibration_figure, self.calibration_key)
        samps = np.array(self.samples)
        X = samps[:, 0:1]  # concentration
        T = samps[:, 2:3]  # absorbance

        self.calibration_axis.cla()
        self.calibration_axis.plot(X, T, 'o')
        self.calibration_axis.set_xlabel('Concentration')
        self.calibration_axis.set_ylabel('Absorbance')
        n = 20
        xs = np.linspace(X.min(), X.max(), 20).reshape(-1, 1)
        xs_powers = self.make_X_powers(xs, self.model['powers'])
        self.calibration_axis.plot(xs, xs_powers @ self.model['coef'], 'r')
        equation = self.format_model_equation()
        r2 = '$R^2$ = {:.2f}\n$R^2$ adj = {:.2f}'.format(self.model["R-squared"], self.model["Adj. R-squared"])
        self.calibration_axis.text(0.05, 0.8, equation + '\n' + r2,
                                   transform=self.calibration_axis.transAxes, fontsize='small')
        self.calibration_canvas.pack(side='top')
        self.calibration_figure.tight_layout()


    def update_measuring_plot(self):
        if self.measuring_canvas:
            self.measuring_canvas.forget()
        equation = self.format_concentration_equation()
        self.measuring_canvas = self.get_canvas(self.measuring_figure, self.measuring_key)
        self.measuring_axis.text(0.02, 0.1, equation, fontsize='large')
        self.measuring_axis.axis('off')
        self.measuring_canvas.pack(side='top')

# Test data for quickly filling in calibration table.
# Only available if spectrophotometer is not connected.

calibration_samples_for_testing = {
    'cubic': [
        [0.0, 994.28, 0.0],
        [1.16, 749.75, 0.123],
        [2.9, 566.9, 0.244],
        [6.84, 414, 0.381],
        [11.15, 313.03, 0.502],
        [12.9, 234.37, 0.628],
        [14.035, 182.75, 0.736]],
    'quadratic-no-intercept': [
        [0.0, 987.75, 0.0],
        [0.576, 741.96, 0.124],
        [1.22, 558.21, 0.248],
        [1.942, 401.06, 0.391],
        [2.836, 305.21, 0.510],
        [3.969, 229.06, 0.635],
        [6.473, 178.65, 0.743]],
    'quadratic-intercept': [
        [0.0, 995.87, 0.0],
        [0.001, 740, 0.12314],
        [0.002, 680, 0.1657],
        [0.724, 411.28, 0.384],
        [1.618, 312.03, 0.504],
        [2.751, 234.62, 0.628],
        [5.255, 182.31, 0.600]], # 737]],
    'linear-no-intercept': [
        [0.0, 987.56, 0.0],
        [0.875, 741.93, 0.124],
        [1.681, 556.46, 0.249],
        [2.514, 394, 0.399],
        [3.380, 304.84, 0.510],
        [4.214, 228.53, 0.636],
        [5.015, 178.28, 0.743]],
    'linear-intercept': [
        [0.0, 994.46, 0.0],
        [0.001, 747.31, 0.124],
        [0.847, 563.15, 0.247],
        [1.68, 401.84, 0.394],
        [2.546, 312.34, 0.503],
        [3.379, 233.40, 0.629],
        [4.181, 181.31, 0.739]],
    'no-trend': [
        [0.0, 994.46, 0.0],
        [0.001, 747.31, 1],
        [0.847, 563.15, 1],
        [1.68, 401.84, 1],
        [2.546, 312.34, 1],
        [3.379, 233.40, 1],
        [4.181, 181.31, 1]]
    }
```

# table.py

```python
import PySimpleGUI as sg
import os
import usb

######################################################################
## class Table
##
## Used for table of calibration samples and also for table of measured samples
######################################################################

class Table():

    def __init__(self, key, data, headings, spectro):  # data, headings):

        self.key = key
        self.data = data
        self.headings = headings
        self.spectro = spectro
        self.dec_places = 3
        
    def make_sgTable(self):

        self.sgtable = sg.Table(key=self.key, values=self.data, headings=self.headings,
                                justification='right', enable_click_events=True,
                                expand_x=True, expand_y=True,
                                col_widths=120, row_height=25)  #300
        return self.sgtable

    def set_window(self, window):
        self.window = window

    def set_samples(self, samples):
        self.data = []
        dp = self.dec_places
        for row in samples:
            row_decimals = []
            for r in row:
                try:
                    rconv = int(float(r) * 10**dp) / 10**dp
                except:
                    rconv = r
                row_decimals.append(rconv)
            self.data.append(row_decimals)
            
    def add(self, row):
        '''Used only for table of measured values, not calibration samples.'''
        dp = self.dec_places
        row_decimals = []
        for r in row:
            try:
                rconv = int(float(r) * 10**dp) / 10**dp
            except:
                rconv = r
            row_decimals.append(rconv)
        self.data.append(row_decimals)
        
    def cell_callback(self, event, row, col, text, keypressed):
        table = self.window[self.key].Widget
        widget = event.widget
        if keypressed == 'Return':
            text = widget.get()
        values = list(table.item(row, 'values'))
        values[col] = text
        table.item(row, values=values)
        self.data[row-1][col] = float(text)
        widget.destroy()

        if self.data[row-1][0] == 0:
            self.spectro.set_volts_zero_concentration(self.data[row-1][1])
        self.data[row-1][2] = self.spectro.volts_to_absorbance(self.data[row-1][1])

        widget.master.destroy()
        self.refresh()
    
    def refresh(self):
        self.sgtable.update(values=self.data)
        table = self.window[self.key].Widget
        self.sgtable.update(visible=True)
        
    def edit_cell(self, key, row, col):
        root = self.window.TKroot
        table = self.window[self.key].Widget
        text = table.item(row, 'values')[col]
        x, y, width, height = table.bbox(row, col)
        wx, wy = table.winfo_x(), table.winfo_y()
        frame = sg.tk.Frame(table)
        frame.place(x=x, y=y, anchor='nw', width=width, height=height)
        textvariable = sg.tk.StringVar()
        textvariable.set(text)
        entry = sg.tk.Entry(frame, textvariable=textvariable, justify='right',
                            font=('latin modern roman', 16, 'bold'))
        entry.pack()
        entry.select_range(0, sg.tk.END)
        entry.icursor(sg.tk.END)
        entry.focus_force()
        entry.bind('<Return>', lambda e, r=row, c=col, t=text,
                   k='Return':self.cell_callback(e, r, c, t, k))
        
    def save(self, filename, columns):

        # Look for USB devcies.  Exit if not found.
        
        path = usb.get_usb_path()
        if path is None:
            return False, 'USB drive not found. Save was not successful.'
            
        if not filename.endswith('.csv'):
            filename += '.csv'

        filename = path + '/' + filename 

        if os.path.exists(filename):
            answer = sg.popup_yes_no('The file ' + filename + ' already exists.  Do you want to replace it with this new data?')
            if answer == 'No':
                return False, 'Please enter a different filename.'
            
        # Open file and write each row from this table's data.

        try:
            with open(filename, 'w') as f:
                f.write(', '.join(columns))
                f.write('\n')
                for row in self.data:
                    for i, col in enumerate(row):
                        if isinstance(col, str):
                            f.write(col)
                        elif isinstance(col, int):
                            f.write(str(col))
                        elif isinstance(col, float):
                            f.write('{:.7g}'.format(col))
                        if i + 1 < len(row):
                            f.write(', ')
                    f.write('\n')

                return True, '{} lines written to {}'.format(len(self.data), filename)

        except:
            return False, 'Save to file ' + filename + ' was not successful.  Please try again or choose different file name.'
```

# usb.py

```python
import os
import glob
import subprocess

# Functions to find and access USB drive
#  from http://stackoverflow.com/questions/22615750/how-can-the-directory-of-a-usb-drive-connected-to-a-system-be-obtained

DEBUG = False

def debugprint(x):
    if DEBUG:
        print(x)

def get_usb_devices():
    sdb_devices = map(os.path.realpath, glob.glob('/dev/sd*'))
    usb_devices = [d for d in sdb_devices if len(d) > 0]
    debugprint('{} {}'.format(list(sdb_devices), list(usb_devices)))
    return dict((os.path.basename(dev), dev) for dev in usb_devices)

def get_usb_path():
    devices = get_usb_devices()
    output = subprocess.check_output(['mount']).splitlines()
    is_usb = lambda path: any(dev in path.decode('utf8') for dev in devices)
    usb_info = (line for line in output if is_usb(line.split()[0]))
    fullInfo = []
    for info in usb_info:
        mountURI = info.split()[0]
        usbURI = info.split()[2]
        for x in range(3, info.split().__sizeof__()):
            if info.split()[x].__eq__("type"):
                for m in range(3, x):
                    usbURI += " "+info.split()[m]
                break
        fullInfo.append([mountURI.decode('utf8'), usbURI.decode('utf8')])
    debugprint('devices {}'.format(devices))
    debugprint('usb_info {}'.format(list(usb_info)))
    debugprint('fullInfo {}'.format(fullInfo))
    if not fullInfo:
        return None
    for dev in fullInfo[0]:
        if 'media' in dev:
            return dev
    return None

def usb_inserted():
    path = get_usb_path()
    return path is not None
    
if __name__ == '__main__':
    print('get_usb_path() returns', get_usb_path())
```
