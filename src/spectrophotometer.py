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
