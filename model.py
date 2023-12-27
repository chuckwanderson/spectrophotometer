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
