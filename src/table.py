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

