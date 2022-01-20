########################################################################
# This file defines a Waveform class that allows us to do general
# waveform-level analysis. Specific routines for analyzing different
# detectors will be written in separate files.
#   
#    - Brian L.
#
# Note: the waveform processings stuff will need to change based on the
# type of detector that we're recording data from; i.e. an NaI signal
# will need a different processing framework than a simple PMT signal
# looking for cherenkov light. 
########################################################################

import pandas as pd
import numpy as np
from TMSAnalysis.TMSUtilities import UsefulFunctionShapes as Ufun
from TMSAnalysis.TMSUtilities import TMSWireFiltering as Filter
import scipy.optimize as opt
from scipy.ndimage import gaussian_filter
from numba import jit
import copy
import matplotlib.pyplot as plt

class Waveform:

	#######################################################################################
	def __init__( self, input_data=None, detector_type=None, sampling_period_ns=None, \
			input_baseline=-1, input_baseline_rms=-1, polarity=-1., \
			fixed_trigger=False, trigger_position=0, decay_time_us=1.e9,\
			calibration_constant=1.,store_processed_wfm=False ):

		self.data = input_data                           # <- Waveform in numpy array
		self.input_baseline = input_baseline             # <- Input baseline (not required)
		self.input_baseline_rms = input_baseline_rms     # <- Input baseline noise (not required)
		self.detector_type = detector_type               # <- Options are: 'NaI', 'Cherenkov', 'PS',
							         #      'XWire', 'YWire', 'SiPM', 'TileStrip'
		self.fixed_trigger = fixed_trigger               # <- Flag which fixes the pulse analysis window
		self.trigger_position = int(trigger_position)    # <- Location of DAQ trigger in samples
		self.polarity = polarity                         # <- Polarity switch to make waveforms positive
		self.decay_time_us = decay_time_us               # <- Decay time of preamps (for charge tile)
		self.store_processed_wfm = store_processed_wfm   # <- Flag which allows you to access the processed waveform
		self.calibration_constant = calibration_constant # <- Calibration constant (for charge tile)

		# Make the default detector type a simple PMT
		if detector_type == None:
			self.detector_type = 'PMT'

		self.sampling_period_ns = sampling_period_ns

		# All returned quantities will be stored in this
		# dict and added to the output dataframe in DataReduction.py
		self.analysis_quantities = dict()


	#######################################################################################
	def FindPulsesAndComputeAQs( self, fit_pulse_flag=False ):
		self.DataCheck()
		if self.input_baseline < 0.:
			baseline = np.mean(self.data[0:50])
			baseline_rms = np.std(self.data[0:50])
		else:
			baseline = self.input_baseline
			baseline_rms = self.input_baseline_rms		
		self.analysis_quantities['Baseline'] = baseline
		self.analysis_quantities['Baseline RMS'] = baseline_rms

		# NOTE: almost all analyses are fixed_trigger analyses, so the if statement
		#       should generally be true.

		if self.fixed_trigger:

			# Here we have different processing algorithms for different detectors.

			if 'NaI' in self.detector_type:
				window_start = self.trigger_position - int(800/self.sampling_period_ns)
				window_end = self.trigger_position + int(1600/self.sampling_period_ns)
				baseline = np.mean(self.data[window_start:window_start+10])
				baseline_rms = np.std(self.data[window_start:window_start+10])
				pulse_area, pulse_time, pulse_height = self.GetPulseArea( self.data[window_start:window_end]-baseline )
				if fit_pulse_flag == True and np.abs(pulse_height)>10.*baseline_rms:
					xwfm = np.linspace(0.,(window_end-window_start)-1,(window_end-window_start))
					popt,pcov = opt.curve_fit( self.NaIPulseTemplate, \
									xwfm, \
									self.data[window_start:window_end]-baseline,\
									p0=(pulse_height*7.,pulse_time),xtol=0.05,ftol=0.05)
					fit_height = popt[0]
					fit_time = popt[1]
				pulse_time = pulse_time - int(800/self.sampling_period_ns)
				fit_time = fit_time - int(800/self.sampling_period_ns)
				self.analysis_quantities['Baseline'] = baseline
				self.analysis_quantities['Baseline RMS'] = baseline_rms
				self.analysis_quantities['Pulse Area'] = pulse_area
				self.analysis_quantities['Pulse Time'] = pulse_time
				self.analysis_quantities['Pulse Height'] = pulse_height
				if fit_pulse_flag:
					self.analysis_quantities['Fit Time'] = fit_time

			elif 'Cherenkov' in self.detector_type:
				window_start = self.trigger_position - int(320/self.sampling_period_ns)
				window_end = self.trigger_position + int(160/self.sampling_period_ns)
				baseline = np.mean(self.data[window_start:window_start+10])
				baseline_rms = np.std(self.data[window_start:window_start+10])
				pulse_area, pulse_time, pulse_height = self.GetPulseArea( self.data[window_start:window_end]-baseline )
				if (fit_pulse_flag == True) and (pulse_height < 7.) and np.abs(pulse_height)>10.*baseline_rms:
					xwfm = np.linspace(0.,(window_end-window_start)-1,(window_end-window_start))
					popt,pcov = opt.curve_fit( self.CherenkovPulseTemplate, xwfm, self.data[window_start:window_end]-baseline,\
									p0=(pulse_height,pulse_time),xtol=0.001,ftol=0.001)
					fit_height = popt[0]
					fit_time = popt[1]
				pulse_time = pulse_time - int(320/self.sampling_period_ns)
				fit_time = fit_time - int(320/self.sampling_period_ns)
				self.analysis_quantities['Baseline'] = baseline
				self.analysis_quantities['Baseline RMS'] = baseline_rms
				self.analysis_quantities['Pulse Area'] = pulse_area
				self.analysis_quantities['Pulse Time'] = pulse_time
				self.analysis_quantities['Pulse Height'] = pulse_height
				if fit_pulse_flag:
					self.analysis_quantities['Fit Time'] = fit_time

			elif 'PS' in self.detector_type:
				window_start = self.trigger_position - int(400/self.sampling_period_ns)
				window_end = self.trigger_position + int(160/self.sampling_period_ns)
				baseline = np.mean(self.data[window_start:window_start+10])
				baseline_rms = np.std(self.data[window_start:window_start+10])
				pulse_area, pulse_time, pulse_height = self.GetPulseArea( self.data[window_start:window_end]-baseline )
				if fit_pulse_flag == True and np.abs(pulse_height>10.*baseline_rms):
					xwfm = np.linspace(0.,(window_end-window_start)-1,(window_end-window_start))
					popt,pcov = opt.curve_fit( self.PSPulseTemplate, xwfm, self.data[window_start:window_end]-baseline,\
									p0=(pulse_height,pulse_time),xtol=0.002,ftol=0.002)
					fit_height = popt[0]
					fit_time = popt[1]
				pulse_time = pulse_time - int(400/self.sampling_period_ns)
				fit_time = fit_time - int(400/self.sampling_period_ns)
				self.analysis_quantities['Baseline'] = baseline
				self.analysis_quantities['Baseline RMS'] = baseline_rms
				self.analysis_quantities['Pulse Area'] = pulse_area
				self.analysis_quantities['Pulse Time'] = pulse_time
				self.analysis_quantities['Pulse Height'] = pulse_height
				if fit_pulse_flag:
					self.analysis_quantities['Fit Time'] = fit_time

			elif 'Xwire' in self.detector_type:
				self.polarity = (-1.)*self.polarity		
				window_start = self.trigger_position - int(2400/self.sampling_period_ns) # 2.4us pretrigger
				window_end = self.trigger_position + int(10000/self.sampling_period_ns)  # 10us posttrigger

				baseline = np.mean(self.data[0:250])
				fft_wfm = Filter.WaveformFFT( self.data-baseline, 8. )
				filtered_wfm = Filter.WaveformFFTAndFilter( self.data - baseline , 8. )	
				self.analysis_quantities['RawEnergy'] = np.mean( fft_wfm[window_end:window_end+300] ) - \
									np.mean( fft_wfm[window_start-200:window_start] )
				baseline = np.mean(filtered_wfm[-500:-1])
				baseline_rms = np.std(filtered_wfm[-500:-1])
				# Pulse time, area, height, position are derived from the filtered waveform.
				pulse_area, pulse_time, pulse_height = self.GetPulseArea( filtered_wfm[window_start:window_end] )
				pulse_time = pulse_time - int(2400/self.sampling_period_ns)
				self.analysis_quantities['Baseline'] = baseline
				self.analysis_quantities['Baseline RMS'] = baseline_rms
				self.analysis_quantities['Pulse Area'] = pulse_area
				self.analysis_quantities['Pulse Time'] = pulse_time
				self.analysis_quantities['Pulse Height'] = pulse_height

			elif 'Ywire' in self.detector_type:
				self.polarity = (-1.)*self.polarity		
				window_start = self.trigger_position - int(2400/self.sampling_period_ns) # 2.4us pretrigger
				window_end = self.trigger_position + int(10000/self.sampling_period_ns)  # 10us posttrigger

				baseline = np.mean(self.data[0:250])
				fft_wfm = Filter.WaveformFFT( self.data-baseline, 8. )
				filtered_wfm = Filter.WaveformFFTAndFilter( self.data - baseline , 8. )	
				self.analysis_quantities['RawEnergy'] = np.mean( fft_wfm[window_end:window_end+300] ) - \
									np.mean( fft_wfm[window_start-200:window_start] )
				baseline = np.mean(filtered_wfm[-500:-1])
				baseline_rms = np.std(filtered_wfm[-500:-1])
				# Pulse time, area, height, position are derived from the filtered waveform.
				pulse_area, pulse_time, pulse_height = self.GetPulseArea( filtered_wfm[window_start:window_end] )
				pulse_time = pulse_time - int(2400/self.sampling_period_ns)
				self.analysis_quantities['Baseline'] = baseline
				self.analysis_quantities['Baseline RMS'] = baseline_rms
				self.analysis_quantities['Pulse Area'] = pulse_area
				self.analysis_quantities['Pulse Time'] = pulse_time
				self.analysis_quantities['Pulse Height'] = pulse_height

			elif 'SiPM' in self.detector_type:
				self.data = gaussian_filter( self.data.astype(float), 80./self.sampling_period_ns ) 
					# ^Gaussian smoothing with a 80ns width (1sig)
				window_start = self.trigger_position - int(1600/self.sampling_period_ns)
				window_end = self.trigger_position + int(2400/self.sampling_period_ns)
				baseline_calc_end = window_start + int(800/self.sampling_period_ns)
				baseline = np.mean(self.data[window_start:baseline_calc_end])
				baseline_rms = np.std(self.data[window_start:baseline_calc_end])
				pulse_area, pulse_height, t5, t10, t20, t80, t90 = \
					self.GetPulseAreaAndTimingParameters( self.data[window_start:window_end]-baseline )
				pulse_time = t10 - int(1600/self.sampling_period_ns)
				self.analysis_quantities['Baseline'] = baseline
				self.analysis_quantities['Baseline RMS'] = baseline_rms
				self.analysis_quantities['Pulse Time'] = pulse_time
				self.analysis_quantities['Pulse Area'] = pulse_area
				self.analysis_quantities['Pulse Height'] = pulse_height
				self.analysis_quantities['T5'] = t5
				self.analysis_quantities['T10'] = t10
				self.analysis_quantities['T20'] = t20
				self.analysis_quantities['T80'] = t80
				self.analysis_quantities['T90'] = t90

			elif 'TileStrip' in self.detector_type:
				self.data = gaussian_filter( self.data.astype(float), 500./self.sampling_period_ns ) * \
						self.polarity
					# ^Gaussian smoothing with a 0.5us width, also, flip polarity if necessary
				baseline = np.mean(self.data[0:int(10000./self.sampling_period_ns)])
				baseline_rms = np.std(self.data[0:int(10000./self.sampling_period_ns)])
					# ^Baseline and RMS calculated from first 10us of smoothed wfm
				corrected_wfm = DecayTimeCorrection( self.data - baseline, \
									self.decay_time_us, \
									self.sampling_period_ns ) * \
						self.calibration_constant
				if self.store_processed_wfm:
					self.processed_wfm = corrected_wfm
				charge_energy = np.mean( corrected_wfm[-int(5000./self.sampling_period_ns):] )
				#plt.plot(corrected_wfm)
				#plt.show()
				baseline_rms *= self.calibration_constant
				# ^Charge energy calculated from the last 5us of the smoothed, corrected wfm
				t10 = -1.
				t25 = -1.
				t50 = -1.
				t90 = -1.
				drift_time = -1.
				if charge_energy < 5.*baseline_rms:
					charge_energy = 0. # if it's not above 5-sigma threshold, set energy to 0
				else:
					t10 = float( np.where( corrected_wfm > 0.1*charge_energy)[0][0] )
					t25 = float( np.where( corrected_wfm > 0.25*charge_energy)[0][0] )
					t50 = float( np.where( corrected_wfm > 0.5*charge_energy)[0][0] )
					t90 = float( np.where( corrected_wfm > 0.9*charge_energy)[0][0] )
					# Compute drift time in microseconds (sampling is given in ns)
					drift_time = (t90 - self.trigger_position) * (self.sampling_period_ns / 1.e3)
				self.analysis_quantities['Baseline'] = baseline
				self.analysis_quantities['Baseline RMS'] = baseline_rms
				self.analysis_quantities['Charge Energy'] = charge_energy
				self.analysis_quantities['T10'] = t10
				self.analysis_quantities['T25'] = t25
				self.analysis_quantities['T50'] = t50
				self.analysis_quantities['T90'] = t90
				self.analysis_quantities['Drift Time'] = drift_time

			else:								
				pulse_area = 0.
				pulse_time = 0.
				pulse_height = 0.
			
	
		else:
			print('WARNING: the not-fixed-trigger analysis has not been tested, and may give' + \
				' spurious results.')
			threshold = 10*baseline_rms
			pre_nsamps = 10
			post_nsamps = 10
			if self.detector_type == 'NaI':
				pre_nsamps = 20
				post_nsamps = 100
			if self.detector_type == 'PMT':
				pre_nsamps = 5
				post_nsamps = 7
			
			pulse_idx = np.where( (self.data-baseline)**2 > threshold**2 )
			# First, check if there are no pulses
			if len(pulse_idx[0]) == 0:
				return
			# Next, check if there are multiple pulses
			elif (pulse_idx[0][-1] - pulse_idx[0][0]) > \
			   (len(pulse_idx[0])-1 + pre_nsamps + post_nsamps):
				print('Multiple pulses found in {} detector. This is not yet supported.'.format(self.detector_type))
				return
			# Finally, find the interesting characteristics of the pulse
			else:
				start = pulse_idx[0][0]-pre_nsamps
				end = pulse_idx[0][-1]+post_nsamps
				pulse_area, pulse_time = self.GetPulseArea( self.data[start:end]-baseline )
				self.analysis_quantities['Num Pulses'] = 1
				self.analysis_quantities['Pulse Areas'] = \
					np.append( self.analysis_quantities['Pulse Areas'], pulse_area )
				self.analysis_quantities['Pulse Times'] = \
					np.append( self.analysis_quantities['Pulse Times'], pulse_time+start )
				self.analysis_quantities['Pulse Heights'] = \
					np.append( self.analysis_quantities['Pulse Heights'], np.min(self.data[start:end]-baseline) )



	#######################################################################################
	def GetPulseArea( self, dat_array ):
		if len(dat_array) == 0: return 0,0,0
		cumul_pulse = np.cumsum( dat_array * self.polarity )
		pulse_area = np.mean(cumul_pulse[-4:-1])
		try:
			t0_10percent_samp = np.where( cumul_pulse > 0.1*pulse_area)[0][0]
		except IndexError:
			t0_10percent_samp = 1
		# The next chunk does a linear interpolation to get the pulse time more accurately.
		t0_10percent = ( 0.1*pulse_area - cumul_pulse[t0_10percent_samp] + \
				t0_10percent_samp * \
				(cumul_pulse[t0_10percent_samp]-cumul_pulse[t0_10percent_samp-1]) ) /\
				(cumul_pulse[t0_10percent_samp]-cumul_pulse[t0_10percent_samp-1])
		pulse_height = self.polarity * np.max( np.abs(dat_array) )

		return pulse_area, t0_10percent, pulse_height


	#######################################################################################
	def GetPulseAreaAndTimingParameters( self, dat_array ):
		if len(dat_array) == 0: return 0, 0, 0, 0
		cumul_pulse = np.cumsum( dat_array * self.polarity )
		area_window_length = int(800./self.sampling_period_ns) # average over 800ns
		pulse_area = np.mean(cumul_pulse[-area_window_length:])
		try:
			t5 = np.where( cumul_pulse > 0.05*pulse_area )[0][0]
		except IndexError:
			t5 = 1
		try:
			t10 = np.where( cumul_pulse > 0.1*pulse_area )[0][0]
		except IndexError:
			t10 = 1
		try:
			t20 = np.where( cumul_pulse > 0.2*pulse_area )[0][0]
		except IndexError:
			t20 = 1
		try:
			t80 = np.where( cumul_pulse > 0.8*pulse_area )[0][0]
		except IndexError:
			t80 = 1
		try:
			t90 = np.where( cumul_pulse > 0.9*pulse_area )[0][0]
		except IndexError:
			t90 = 1
		pulse_height = self.polarity * np.max( np.abs(dat_array) )
		
		return pulse_area, pulse_height, t5, t10, t20, t80, t90


	#######################################################################################
	def NaIPulseTemplate( self, x, amp, time):
		return Ufun.TwoExpConv(x, amp*30., time-40./self.sampling_period_ns, \
					58./self.sampling_period_ns, \
					200.5/self.sampling_period_ns)


	#######################################################################################
	def PSPulseTemplate( self, x, amp, time):
		return Ufun.DoubleExpGaussConv( x, amp*2., 0.80, time + 5./self.sampling_period_ns, \
						2./self.sampling_period_ns, \
						6.5/self.sampling_period_ns, \
						37.3/self.sampling_period_ns )


	#######################################################################################
	def CherenkovPulseTemplate( self, x, amp, time ):
		return Ufun.DoubleExpGaussConv( x, amp * 6.7, 0.90, time, \
						1.8/self.sampling_period_ns, \
						4.1/self.sampling_period_ns, \
						49./self.sampling_period_ns )  


	#######################################################################################
	def DataCheck( self ):
		if self.data is not None:
			return
		else:
			raise Exception('No data in waveform.')


############################ End the Waveform class ##############################################



##################################################################################################
# The decay time correction is recursive, and runs much faster using the just-in-time capabilities
# from numba. But, I had to make it an external function
##################################################################################################
@jit("float64[:](float64[:],float64,float64)",nopython=True)
def DecayTimeCorrection( input_wfm, decay_time_us, sampling_period_ns ):

		# Here I'll assume the decay time is in units of mircoseconds
		# and the sampling period is in units of ns
		new_wfm = np.copy( input_wfm )
		for i in range(len(input_wfm)-1):
			new_wfm[i+1] = new_wfm[i] - \
					np.exp( - (sampling_period_ns/1.e3) / decay_time_us ) * input_wfm[i] + \
					input_wfm[i+1]
		return new_wfm



class Event:

	def __init__( self, reduced, path_to_tier1, event_number,\
			run_parameters_file,\
			calibrations_file,\
			channel_map_file):

		from TMSAnalysis.StruckAnalysisConfiguration import StruckAnalysisConfiguration
		import uproot

		try :
			if path_to_tier1[-1] is not '/':
				path_to_tier1 += '/'
		except TypeError:
			pass

		analysis_config = StruckAnalysisConfiguration.StruckAnalysisConfiguration()
		analysis_config.GetRunParametersFromFile( run_parameters_file, path_to_tier1.split('/')[-3] )
		analysis_config.GetCalibrationConstantsFromFile( calibrations_file )
		analysis_config.GetChannelMapFromFile( channel_map_file, path_to_tier1.split('/')[-3] )
		channel_number = analysis_config.GetNumberOfChannels()
		self.event_number 		= event_number
		self.waveform 			= {}
		self.baseline			= []
		self.charge_energy_ch		= []
		self.risetime 			= []
		self.sampling_frequency = analysis_config.run_parameters['Sampling Rate [MHz]']

		if path_to_tier1 is not None:
			path_to_file 		= path_to_tier1
			try:
				entry_from_reduced 	= pd.read_hdf(reduced, start=self.event_number, stop=self.event_number+1)
				timestamp 		= entry_from_reduced['Timestamp'].values[0]
				fname 			= entry_from_reduced['File'].values[0]
				self.tot_charge_energy 	= entry_from_reduced['TotalTileEnergy'].values[0]
				self.event_number 	= entry_from_reduced['Event'][event_number]
			except OSError:
				entry_from_reduced = pd.read_pickle(reduced).iloc[self.event_number]
				timestamp 		= entry_from_reduced['Timestamp']
				fname 			= entry_from_reduced['File']
				self.tot_charge_energy 	= entry_from_reduced['TotalTileEnergy']
				self.event_number 	= entry_from_reduced['Event']

		else:
			print('No reduced file found, charge energy and risetime information not present')
			fname = reduced.split('/')[-1]
			path_to_file = reduced[:-len(fname)]
			self.tot_charge_energy = 0.0

		tier1_tree = uproot.open('{}{}'.format(path_to_file,fname))['HitTree']
		tier1_ev = tier1_tree.arrays( entrystart=self.event_number*channel_number, entrystop=(self.event_number+1)*channel_number)
		#the events picked from the reduced file and from the tier1 root file are cross-checked with their timestamp
		try:
			if not np.array_equal(np.unique(tier1_ev[ b'_rawclock']),np.unique(timestamp)):
				raise RuntimeError('Timestamps not matching')

		except NameError:
			pass

		global software_channel 
		software_channel = tier1_ev[b'_slot']*16+tier1_ev[b'_channel']
		if analysis_config.run_parameters['Sampling Rate [MHz]'] == 62.5:
			polarity = 1.

		waveform = np.array(tier1_ev[ b'_waveform'])
		self.ix_channel = []
		#looping through channels and fill the waveforms
		for i,ch_waveform in enumerate(waveform):
			ch_type = analysis_config.GetChannelTypeForSoftwareChannel(software_channel[i])
			ch_name = analysis_config.GetChannelNameForSoftwareChannel(software_channel[i])
			if ch_name == 'Off':
				continue
			self.ix_channel.append(software_channel[i])
			self.waveform[ch_name] = Waveform(input_data = ch_waveform,\
							detector_type       = ch_type,\
							sampling_period_ns  = 1.e3/self.sampling_frequency,\
							input_baseline      = -1,\
							polarity            = polarity,\
							fixed_trigger       = False,\
							trigger_position    = analysis_config.run_parameters['Pretrigger Length [samples]'],\
							decay_time_us       = analysis_config.GetDecayTimeForSoftwareChannel( software_channel[i] ),\
							calibration_constant = analysis_config.GetCalibrationConstantForSoftwareChannel(software_channel[i]))
			#same as for Waveform class
			self.baseline.append(np.mean(ch_waveform[:int(analysis_config.run_parameters['Baseline Length [samples]'])]))
			#different cases for tile/SiPM
			try:
				self.charge_energy_ch.append(entry_from_reduced['{} {} Charge Energy'.format(ch_type,ch_name)])
				self.risetime.append(entry_from_reduced['{} {} T90'.format(ch_type,ch_name)]/self.sampling_frequency)
			except (KeyError, UnboundLocalError, AttributeError):
				self.charge_energy_ch.append(0)
				self.risetime.append(0)


	#smoothing function, the waveform is overwritten, time_width is in us
	def smooth( self, time_width ):
		for k,v in self.waveform.items():
			self.waveform[k].data = gaussian_filter( v.data.astype(float), time_width*self.sampling_frequency)
		return self.waveform


	def plot_event( self, risetime=False ):
		import matplotlib.pyplot as plt
		ch_offset = 500
		for i,e in enumerate(np.argsort(self.ix_channel)):
			v = list(self.waveform.keys())[e]
			p = plt.plot(np.arange(len(self.waveform[v].data))/self.sampling_frequency,self.waveform[v].data-self.baseline[e]+ch_offset*i,lw=1)
			plt.text(0,ch_offset*i,'{} {:.1f}'.format(v,self.charge_energy_ch[e]))
			if risetime and self.charge_energy_ch[e]>0:
				plt.vlines(self.risetime[e],ch_offset*i,ch_offset*i+2*self.charge_energy_ch[e],linestyles='dashed',colors=p[0].get_color())

		plt.xlabel('time [$\mu$s]')
		plt.title('Event {}, Energy {:.1f} ADC counts'.format(self.event_number,self.tot_charge_energy))
		plt.tight_layout()
		return(plt)

class Simulated_Event:

	def __init__( self, reduced, path_to_tier1, event_number,\
			run_parameters_file,\
			calibrations_file,\
			channel_map_file,\
			add_noise=True):

		from TMSAnalysis.StruckAnalysisConfiguration import StruckAnalysisConfiguration
		from TMSAnalysis.ParseSimulation import NEXOOfflineFile
		import pickle

		try :
			if path_to_tier1[-1] is not '/':
				path_to_tier1 += '/'
		except TypeError:
			pass

		analysis_config = StruckAnalysisConfiguration.StruckAnalysisConfiguration()
		analysis_config.GetRunParametersFromFile( run_parameters_file, path_to_tier1.split('/')[-3] )
		analysis_config.GetCalibrationConstantsFromFile( calibrations_file )
		analysis_config.GetChannelMapFromFile( channel_map_file, path_to_tier1.split('/')[-3] )
		channel_number = analysis_config.GetNumberOfChannels()
		self.event_number 		= event_number
		self.waveform 			= {}
		self.baseline			= []
		self.baseline_rms		= []
		self.charge_energy_ch		= []
		self.risetime 			= []
		self.sampling_frequency = analysis_config.run_parameters['Simulation Sampling Rate [MHz]']

		if path_to_tier1 is not None:
			path_to_file 		= path_to_tier1
			try:
				entry_from_reduced 	= pd.read_hdf(reduced, start=self.event_number, stop=self.event_number+1)
				timestamp 		= entry_from_reduced['Timestamp'].values[0]
				fname 			= entry_from_reduced['File'].values[0]
				self.tot_charge_energy 	= entry_from_reduced['TotalTileEnergy'].values[0]
				self.event_number 	= entry_from_reduced['Event'][event_number]
			except OSError:
				entry_from_reduced = pd.read_pickle(reduced).iloc[self.event_number]
				timestamp 		= entry_from_reduced['Timestamp']
				fname 			= entry_from_reduced['File']
				self.tot_charge_energy 	= entry_from_reduced['TotalTileEnergy']
				self.event_number 	= entry_from_reduced['Event']

		else:
			print('No reduced file found, charge energy and risetime information not present')
			fname = reduced.split('/')[-1]
			path_to_file = reduced[:-len(fname)]
			self.tot_charge_energy = 0.0

		pickled_fname = path_to_file + 'channel_status.p'
		global software_channel 
		software_channel = analysis_config.channel_map['Board']*16+analysis_config.channel_map['InputChannel']
		global ch_status
		with open(pickled_fname,'rb') as f:
			ch_status = pickle.load(f)

		input_file = NEXOOfflineFile.NEXOOfflineFile( input_filename = path_to_file+fname,\
								config = analysis_config,\
								add_noise = add_noise,\
								noise_lib_directory='/usr/workspace/wsa/nexo/jacopod/dedicated_noise_run/')

		if path_to_tier1 is not None and add_noise:
			input_file.global_noise_file_counter = entry_from_reduced['NoiseIndex'][0]
			input_file.noise_file_event_counter  = entry_from_reduced['NoiseIndex'][1]
		input_df = input_file.GroupEventsAndWriteToHDF5(save = False, start_stop=[self.event_number,self.event_number+1])
		#since the timestamps are not filled in the simulated data there is no real handle to cross-checked the event is actually the same

		waveform = input_df['Data'][0]
		self.ix_channel = []
		#looping through channels and fill the waveforms
		for i,ch_waveform in enumerate(waveform):
			ch_type = analysis_config.GetChannelTypeForSoftwareChannel(software_channel[i])
			ch_name = analysis_config.GetChannelNameForSoftwareChannel(software_channel[i])
			self.ix_channel.append(software_channel[i])

			if ch_name in ch_status.keys():
				mean,sigma = ch_status[ch_name]
				ch_waveform = np.random.normal(mean,sigma,len(ch_waveform))

			self.waveform[ch_name] = Waveform(input_data = ch_waveform,\
							detector_type       = ch_type,\
							sampling_period_ns  = 1.e3/self.sampling_frequency,\
							input_baseline      = -1,\
							polarity            = -1,\
							fixed_trigger       = False,\
							trigger_position    = analysis_config.run_parameters['Pretrigger Length [samples]'],\
							decay_time_us       = analysis_config.GetDecayTimeForSoftwareChannel(software_channel[i]),\
							calibration_constant = analysis_config.GetCalibrationConstantForSoftwareChannel(software_channel[i]))
			#same as for Waveform class
			self.baseline.append(np.mean(ch_waveform[:int(analysis_config.run_parameters['Baseline Length [samples]'])]))
			#different cases for tile/SiPM
			try:
				self.charge_energy_ch.append(entry_from_reduced['{} {} Charge Energy'.format(ch_type,ch_name)])
				self.baseline_rms.append(entry_from_reduced['{} {} Baseline RMS'.format(ch_type,ch_name)])
				self.risetime.append(entry_from_reduced['{} {} T90'.format(ch_type,ch_name)]/self.sampling_frequency)
			except (KeyError, UnboundLocalError):
				self.charge_energy_ch.append(0)
				self.baseline_rms.append(0)
				self.risetime.append(0)


	#smoothing function, the waveform is overwritten, time_width is in us
	def smooth( self, time_width ):
		for k,v in self.waveform.items():
			self.waveform[k].data = gaussian_filter( v.data.astype(float), time_width*self.sampling_frequency)
		return self.waveform


	def plot_event( self, risetime=False ):
		import matplotlib.pyplot as plt
		ch_offset = 250
		for i,e in enumerate(np.argsort(self.ix_channel)):
			v = list(self.waveform.keys())[e]
			p = plt.plot(np.arange(len(self.waveform[v].data))/self.sampling_frequency,self.waveform[v].data-self.baseline[e]+ch_offset*i)
			plt.text(0,ch_offset*i,'{} {:.1f}'.format(v,self.charge_energy_ch[e]))
			if risetime and self.charge_energy_ch[e]>0:
				plt.vlines(self.risetime[e],ch_offset*i,ch_offset*i+2*self.charge_energy_ch[e],linestyles='dashed',colors=p[0].get_color())

		plt.xlabel('time [$\mu$s]')
		plt.title('Event {}, Energy {:.1f} ADC counts'.format(int(self.event_number),self.tot_charge_energy))
		plt.tight_layout()
		return(plt)
