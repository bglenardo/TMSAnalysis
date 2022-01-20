############################################################################
# This file defines a class that reads the ROOT files produced by the 
# NGM Daq and puts the data into Pandas dataframes 
# for analysis purposes.
#
#    - Brian L.
############################################################################

import pandas as pd
import numpy as np
import uproot as up
import time
import os
import sys


class NGMRootFile:

        ####################################################################
	def __init__( self, input_filename=None, output_directory=None, channel_map_file=None ):
		print('NGMFile object constructed.')

		package_directory = os.path.dirname(os.path.abspath(__file__))
		if output_directory is None:
			self.output_directory = './'
		else:
			self.output_directory = output_directory + '/'

		if input_filename is not None:
			self.LoadRootFile( input_filename )
		if channel_map_file is not None:
			self.channel_map = pd.read_csv(channel_map_file,skiprows=9)
			print('Channel map loaded:')
			print(self.channel_map)
			print('\n{} active channels.'.format(len(self.channel_map)))
		else:
			print('WARNING: No channel map file provided. Using the default one...')
			self.channel_map = pd.read_csv(package_directory + '/channel_map_8ns_sampling.txt',skiprows=9)
		self.h5_file = None

        ####################################################################
	def LoadRootFile( self, filename ):
		self.infile = up.open(filename)
		self.filename = filename
		print('Input file: {}'.format(self.filename))
		try:
			self.intree = self.infile['HitTree']
		except ValueError as e:
			print('Some problem getting the HitTree out of the file.')
			print('{}'.format(e))
			return
		print('Got HitTree.')
		

        ####################################################################
	def GroupEventsAndWriteToHDF5( self, nevents = -1 ):
		
		try:
			self.infile
		except NameError:
			self.LoadFile()
	
		start_time = time.time()		
		self.current_evt = pd.Series()
		self.outputdf = pd.DataFrame(columns=['Timestamp','Channels','Data'])
		this_event_timestamp = -1
		file_counter = 0
		global_evt_counter = 0
		local_evt_counter = 0
		local_entry_counter = 0
		df = pd.DataFrame(columns=['Channels','Timestamp','Data','ChannelTypes','ChannelPositions'])
		start_time = time.time()
		print('{} entries per event.'.format(len(self.channel_map)))

		for data in self.intree.iterate(['_waveform','_rawclock','_slot','_channel'],namedecode='utf-8',entrysteps=1):

			data_series = pd.Series(data)
			this_entry_timestamp = data_series['_rawclock']
			if local_entry_counter==0:
				this_evt_timestamp = this_entry_timestamp
				this_evt_series = data_series

			# If the timestamp is consistent, append this to the current event
			if this_entry_timestamp == this_evt_timestamp:
				local_entry_counter += 1
			#	for index, value in this_evt_series.iteritems():
			#		this_evt_series[index] = np.append(this_evt_series[index],data_series[index])
				continue

			# If the timestep has jumped forward, save this event and start the next one
			else:	
				#print(this_evt_series)
				if nevents > 0:
					if global_evt_counter > nevents:
						break
				channel_mask, channel_types, channel_positions = self.GenerateChannelMask( data['_slot'],data['_channel'])
				#for column in this_evt_series.items():
				#	this_evt_series[ column[0] ] = np.array(this_evt_series_series[column[0]][channel_mask])
				output_series = pd.Series()
				output_series['Channels'] = this_evt_series['_slot']*16+this_evt_series['_channel']
				output_series['Timestamp'] = this_evt_series['_rawclock']
				output_series['Data'] = this_evt_series['_waveform']
				channel_mask, channel_types, channel_positions = self.GenerateChannelMask( this_evt_series['_slot'],this_evt_series['_channel'])
				output_series['ChannelTypes'] = channel_types
				output_series['ChannelPositions'] = channel_positions
				df = df.append(output_series,ignore_index=True)	


				global_evt_counter += 1
				local_evt_counter += 1
				if local_evt_counter > 200:
					output_filename = '{}{}_{:0>3}.h5'.format( self.output_directory,\
										self.GetFileTitle(str(self.infile.name)),\
										file_counter )
					df.to_hdf(output_filename,key='raw')
					local_evt_counter = 0
					file_counter += 1
					df = pd.DataFrame(columns=['Channels','Timestamp','Data','ChannelTypes','ChannelPositions'])
					print('Written to {} at {:4.4} seconds'.format(output_filename,time.time()-start_time))	

				# Now that the previous event is written, start the next event:
				this_evt_timestamp = this_entry_timestamp
				this_evt_series = data_series
				local_entry_counter = 1
				
				
		
		output_filename = '{}{}_{:0>3}.h5'.format( self.output_directory,\
								self.GetFileTitle(str(self.infile.name)),\
								file_counter )
		df.to_hdf(output_filename,key='raw')
		end_time = time.time()
		print('{} events written in {:4.4} seconds.'.format(global_evt_counter,end_time-start_time))
	
	####################################################################
	def GenerateChannelMask( self, slot_column, channel_column ):

		channel_mask = np.array(np.ones(len(slot_column),dtype=bool))
		channel_types = ['' for i in range(len(slot_column))]
		channel_positions = np.zeros(len(slot_column),dtype=int)

		for index,row in self.channel_map.iterrows():
			
			slot_mask = np.where(slot_column==row['Slot'])
			chan_mask = np.where(channel_column==row['Channel'])
			intersection = np.intersect1d(slot_mask,chan_mask)
			if len(intersection) == 1:
				this_index = intersection[0]
			else:
				 continue
			channel_types[this_index] = row['Type']
			channel_positions[this_index] = int(row['Position'])
			if row['Type']=='Off':
				channel_mask[this_index] = False
		return channel_mask, channel_types, channel_positions
	
        ####################################################################
	def GetFileTitle( self, filepath ):
		filename = filepath.split('/')[-1]
		filetitle = filename.split('.')[0]
		return filetitle
		
	
	
