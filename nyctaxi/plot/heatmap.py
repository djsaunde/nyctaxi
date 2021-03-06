import os
import sys
import csv
import imp
import gmplot
import argparse
import webbrowser
import numpy as np
import pandas as pd
import cPickle as p
import multiprocessing as mp
import matplotlib.pyplot as plt

from datetime import datetime
from scipy.stats import entropy
from timeit import default_timer
from joblib import Parallel, delayed
from IPython.core.display import HTML
from mpl_toolkits.mplot3d import Axes3D
from IPython.display import Image, display

import warnings
warnings.filterwarnings('ignore')

from util import *

plots_path = os.path.join('..', '..', 'plots')
data_path = os.path.join('..', '..', 'data', 'preprocessed_100')


def plot_heatmap_times(taxi_data, distance, days, times, map_type):
	'''
	taxi_data: Dictionary of (data type, pandas DataFrame of taxicab coordinates and metadata)
	distance: Distance in feet from hotel criterion.
	days: Day of week to include.
	times: Times of days to include.
	map_type: 'static' or 'gmap', for either ARCGIS NYC map queried from their website or Google Maps overlay.
	'''
	start_time = default_timer()

	# get coordinates of new distance and time-constraint satisfying taxicab trips with nearby pick-ups
	all_coords = {}
	for key in taxi_data.keys():
		data = taxi_data[key]

		# Create a number of CPU workers equal to the number of hotels in the data
		pool = mp.Pool(n_jobs)

		# Get a list of the names of the hotels we aim to plot distributions for (removing NaNs)
		hotel_names = [ hotel_name for hotel_name in data['Hotel Name'].unique() if not pd.isnull(hotel_name) ]

		# Get the pick-up (drop-off) coordinates of the trip which ended (began) near this each hotel
		if key == 'pickups':
			coords = pool.map(get_nearby_pickups_times, [ (data.loc[data['Hotel Name'] == hotel_name], \
							distance, days, times[0], times[1] - 1) for hotel_name in hotel_names ])
		elif key == 'dropoffs':
			coords = pool.map(get_nearby_dropoffs_times, [ (data.loc[data['Hotel Name'] == hotel_name], \
							distance, days, times[0], times[1] - 1) for hotel_name in hotel_names ])
		
		coords = { hotel_name : args for (hotel_name, args) in zip(hotel_names, coords) }

		print 'Total satisfying nearby', key, ':', sum([single_hotel_coords.shape[1] \
											for single_hotel_coords in coords.values()]), '/', len(data), '\n'
		
		print 'Satisfying nearby', key, 'by hotel:'
		for name in coords:
			print '-', name, ':', coords[name].shape[1], 'satisfying taxicab rides'

		all_coords = all_coords.update(coords)

		print '\n'

	coords = all_coords

	print '\nIt took', default_timer() - start_time, 'seconds to find all criteria-satifying taxicab trips.\n'

	start_time = default_timer()

	if map_type == 'static':
		# Plot all ARCGIS maps.
		directory = str(distance) + 'ft_' + '_'.join([ key for key in taxi_data.keys() ]) + '_'.join([ str(day) for day in days ]) \
				+ '_weekdays_' + str(times[0]) + '_' + str(times[1]) + '_start_end_hours_heatmap.png'
		empirical_dists = Parallel(n_jobs=len(coords.keys())) (delayed(plot_arcgis_nyc_map)((coords[hotel_name][0], coords[hotel_name][1]),
							hotel_name, os.path.join(plots_path, directory)) for hotel_name in coords.keys())
	elif map_type == 'gmap':
		for hotel_name in coords.keys():
			map_name = hotel_name + '_Jan2016_' + str(distance) + 'ft_pickups_' + ','.join([ str(day) for day in days ]) + \
														'_weekdays_' + str(times[0]) + '_' + str(times[1]) + '_start_end_hours_heatmap.html'
			filepath = plots_path + map_name[:-5] + '.png'

			# get the Google maps area we wish to plot at
			gmap = gmplot.GoogleMapPlotter(np.median(coords[hotel_name][0]), np.median(coords[hotel_name][1]), 13)

			# plot the map
			gmap.heatmap(coords[hotel_name][0], coords[hotel_name][1], threshold=10, radius=1, gradient=None, opacity=0.6, dissipating=False)

			# draw the map
			gmap.draw(plots_path + map_name)

			# display it in the web browser
			webbrowser.open(plots_path + map_name)

	else:
		raise Exception('Expecting map type of "static" or "gmap".')

	print '\nIt took', default_timer() - start_time, 'seconds to plot the heatmaps\n'

	return empirical_dists, coords.keys()


def plot_heatmap_window(taxi_data, distance, start_datetime, end_datetime, map_type):
	'''
	taxi_data: Dictionary of (data type, pandas DataFrame of taxicab coordinates and metadata)
	distance: Distance in feet from hotel criterion.
	start_datetime: Date at which to begin looking for data.
	end_datetime: Date at which to end looking for data.
	map_type: 'static' or 'gmap', for either ARCGIS NYC map queried from their website or Google Maps overlay.
	'''

	start_time = default_timer()

	# get coordinates of new distance and time-constraint satisfying taxicab trips with nearby pick-ups
	all_coords = {}
	for key in taxi_data.keys():
		data = taxi_data[key]

		# Create a number of CPU workers equal to the number of hotels in the data
		pool = mp.Pool(n_jobs)

		# Get a list of the names of the hotels we aim to plot distributions for (removing NaNs)
		hotel_names = [ hotel_name for hotel_name in data['Hotel Name'].unique() if not pd.isnull(hotel_name) ]

		# Get the pick-up (drop-off) coordinates of the trip which ended (began) near this each hotel
		if key == 'pickups':
			coords = pool.map(get_nearby_pickups_window, [ (data.loc[data['Hotel Name'] == hotel_name], \
								distance, start_datetime, end_datetime) for hotel_name in hotel_names ])
		elif key == 'dropoffs':
			coords = pool.map(get_nearby_dropoffs_window, [ (data.loc[data['Hotel Name'] == hotel_name], \
								distance, start_datetime, end_datetime) for hotel_name in hotel_names ])
		
		coords = { hotel_name : coord for (hotel_name, coord) in zip(hotel_names, coords) }

		print 'Total satisfying nearby', key, ':', sum([single_hotel_coords.shape[1] \
											for single_hotel_coords in coords.values()]), '/', len(data), '\n'
		
		print 'Satisfying nearby', key, 'by hotel:'
		for name in coords:
			print '-', name, ':', coords[name].shape[1], 'satisfying taxicab rides'

		all_coords.update(coords)

	coords = all_coords

	print '\nIt took', default_timer() - start_time, 'seconds to find all criteria-satifying taxicab trips.\n'

	start_time = default_timer()

	if map_type == 'static':
		# Plot all ARCGIS maps.
		directory = '_'.join([ '_'.join(taxi_data.keys()), str(distance), str(start_datetime), str(end_datetime) ])

		if scatter:
			empirical_dists = Parallel(n_jobs=n_jobs) (delayed(plot_arcgis_nyc_scatter_plot)((coords[hotel_name][0], 
								coords[hotel_name][1]), hotel_name, os.path.join(plots_path, directory)) for hotel_name in coords.keys())

			empirical_dists.append(plot_arcgis_nyc_scatter_plot((np.concatenate([ coords[hotel_name][0] for hotel_name in coords.keys() ]),
								np.concatenate([ coords[hotel_name][1] for hotel_name in coords.keys() ])), 'All Hotels', os.path.join(plots_path, directory)))
		else:
			empirical_dists = Parallel(n_jobs=n_jobs) (delayed(plot_arcgis_nyc_map)((coords[hotel_name][0], 
								coords[hotel_name][1]), hotel_name, os.path.join(plots_path, directory)) for hotel_name in coords.keys())

			empirical_dists.append(plot_arcgis_nyc_map((np.concatenate([ coords[hotel_name][0] for hotel_name in coords.keys() ]),
								np.concatenate([ coords[hotel_name][1] for hotel_name in coords.keys() ])), 'All Hotels', os.path.join(plots_path, directory)))

	elif map_type == 'gmap':
		for hotel_name in coords.keys():
			map_name = '_'.join([ hotel_name, str(distance), to_plot, ','.join([ str(day) for day in days ]), str(times[0]), str(times[1]) ]) + '.html'
			filepath = plots_path + map_name[:-5] + '.png'

			# Get the Google maps area we wish to plot on.
			gmap = gmplot.GoogleMapPlotter(np.median(coords[hotel_name][0]), np.median(coords[hotel_name][1]), 13)

			# Plot the map.
			gmap.heatmap(coords[hotel_name][0], coords[hotel_name][1], threshold=10, radius=1, gradient=None, opacity=0.6, dissipating=False)

			# Draw the map.
			gmap.draw(plots_path + map_name)

			# Display it in a web browser
			webbrowser.open(plots_path + map_name)

	else:
		raise Exception('Expecting map type of "static" or "gmap".')

	print '\nIt took', default_timer() - start_time, 'seconds to plot the heatmaps.\n'

	return empirical_dists, coords.keys()


def plot_KL_divergences(empirical_distributions, hotel_names):
	'''
	Given the empirical distributions of pick-up / drop-off points on the discretized map of NYC, calculate their
	pairwise Kullbeck-Liebler divergences and arrange them in a bar plot.

	empirical_distributions: A list of empirical distributions of pick-up / drop-off points on a discretized map of NYC.
	hotel_names: The ordered list of the names of the hotels whose empirical distributions we've calculated.
	'''
	kl_diverges = []
	for dist1 in empirical_distributions:
		cur_diverges = []
		for dist2 in empirical_distributions:
			cur_diverges.append(entropy(dist1, dist2))
		kl_diverges.append(cur_diverges)

	kl_diverges = np.array(kl_diverges)

	width = 0.9 / float(kl_diverges.shape[0])
	idxs = np.arange(kl_diverges.shape[0])

	cm = plt.get_cmap('gist_rainbow')

	fig = plt.figure(figsize=(18, 9.5))
	ax = fig.add_subplot(111, projection='3d')

	for idx, hotel_name, klds in zip(range(len(kl_diverges)), hotel_names, kl_diverges):
		ax.bar(np.arange(len(klds)), klds, zs=[ idx ] * len(klds), zdir='y', alpha=0.8, color=cm(1.0 * idx / len(hotel_names)))

	ax.set_yticks(xrange(len(hotel_names)))
	ax.set_yticklabels([ 'H' + str(idx + 1) for idx in xrange(len(hotel_names))])
	ax.set_xticks(xrange(len(hotel_names)))
	ax.set_xticklabels([ 'H' + str(idx + 1) for idx in xrange(len(hotel_names))])

	fig.suptitle('pairwise Kullbeck-Liebler divergence per hotel distribution')

	plt.clf()
	plt.close()

	return kl_diverges


if __name__ == '__main__':
	parser = argparse.ArgumentParser()

	parser.add_argument('--to_plot', type=str, default='pickups', \
						help='Whether to plot data from nearby "pickups", "dropoffs", or "both"')
	parser.add_argument('--distance', type=int, default=100, help='Distance from hotel criterion (in feet).')
	parser.add_argument('--map_type', type=str, default='static', \
						help='Plot a heatmap in Google Maps or using an ARCGIS map of NYC.')
	parser.add_argument('--n_jobs', type=int, default=2, help='The number of parallel processes to run for all parallel processing routines.')
	parser.add_argument('--scatter', type=str, default='True', help='Whether to create a scatterplot or a heatmap.')

	subparsers = parser.add_subparsers(title='subcommands', dest='subcommand')

	times_subparser = subparsers.add_parser('times', help='Parser for heatmap plotting \
													by days of the week and times of day.')

	times_subparser.add_argument('--days', type=list, default=[0, 1, 2, 3, 4, 5, 6], \
				help='Days of the week indexed by the integers 0, 1, ..., 6 for Sunday, Monday, ..., Saturday.')
	times_subparser.add_argument('--times', type=tuple, default=(0, 24), \
											help='Start and ending time (in hours) to look for data.')

	window_subparser = subparsers.add_parser('window', help='Parser for heatmap plotting a specific window of time.')

	window_subparser.add_argument('--start_datetime', type=int,
					nargs=4, default=[2016, 6, 20, 0], metavar=('YEAR', 'MONTH', 'DAY', 'HOUR'), 
					help='Tuple giving year, month, day, and hour of the time from which to start looking for data.')
	window_subparser.add_argument('--end_datetime', type=int,
					nargs=4, default=[2016, 6, 27, 0], metavar=('YEAR', 'MONTH', 'DAY', 'HOUR'), 
					help='Tuple giving year, month, day, and hour of the time from which to stop looking for data.')

	args = parser.parse_args()
	args = vars(args)

	# parse arguments and place them in local scope
	locals().update(args)

	if subcommand not in [ 'times', 'window' ]:
		raise Exception('Specify either "times" or "window".')

	if subcommand == 'window':
		start_datetime = datetime(start_datetime[0], start_datetime[1], start_datetime[2], start_datetime[3])
		end_datetime = datetime(end_datetime[0], end_datetime[1], end_datetime[2], end_datetime[3])

	if to_plot == 'pickups':
		data_files = [ 'destinations.csv' ]
	elif to_plot == 'dropoffs':
		data_files = [ 'starting_points.csv' ]
	elif to_plot == 'both':
		data_files = [ 'destinations.csv', 'starting_points.csv' ]		

	if scatter == 'True':
		scatter = True
	elif scatter == 'False':
		scatter = False
	else:
		raise Exception('Expecting one of "True" or "False" for command-line argument "scatter".')

	# get dictionary of taxicab trip data based on `to_plot` argument
	taxi_data = load_data(to_plot, data_files, data_path)

	if subcommand == 'times':
		empirical_distributions, keys = plot_heatmap_times(taxi_data, distance, days, times, map_type)
	elif subcommand == 'window':
		empirical_distributions, keys = plot_heatmap_window(taxi_data, distance, start_datetime, end_datetime, map_type)

	kl_divergences = plot_KL_divergences(empirical_distributions, keys)