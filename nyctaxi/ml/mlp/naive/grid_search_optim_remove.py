from __future__ import print_function

import os
import sys
import argparse
import numpy as  np
import pandas as pd

from nyctaxi.ml.utils        import *
from datetime                import date
from sklearn.neural_network  import MLPRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics         import mean_squared_error

parser = argparse.ArgumentParser()
parser.add_argument('--trip_type', type=str, default='pickups')
parser.add_argument('--start_date', type=int, nargs=3, default=[2014, 1, 1])
parser.add_argument('--end_date', type=int, nargs=3, default=[2016, 6, 30])
parser.add_argument('--trials', type=int, default=5)
parser.add_argument('--removals', type=int, default=15)
parser.add_argument('--metric', type=str, default='rel_diffs')

locals().update(vars(parser.parse_args()))

print('Trip type: %s' % trip_type)
print('Removals: %d' % removals)

report_fname = '_'.join(map(str, [25, 300, trip_type, start_date[0], start_date[1],
					start_date[2], end_date[0], end_date[1], end_date[2], metric]))

fname = '_'.join(map(str, [start_date[0], start_date[1], start_date[2],
						end_date[0], end_date[1], end_date[2], metric]))

start_date, end_date = date(*start_date), date(*end_date)

data_path = os.path.join('..', '..', 'data')
reports_path = os.path.join(data_path, 'optimization_reports')
predictions_path = os.path.join(data_path, 'grid_search_naive_opt_remove_mlp_predictions', fname)
removals_path = os.path.join(data_path, 'grid_search_naive_mlp_opt_removals', fname)

for path in [predictions_path, removals_path]:
	if not os.path.isdir(path):
		os.makedirs(path)

# Load daily capacity data.
df = load_occupancy_data(data_path, start_date, end_date)

opt_report = pd.read_csv(os.path.join(reports_path, report_fname + '.csv'))
order = list(np.array(opt_report['Removed hotel']))
all_hotel_names = set(order) & set(df['Share ID'].unique())
df = df[df['Share ID'].isin(all_hotel_names)]

observations, targets = encode_data(df)

# Save (observations, targets) to disk.
np.save(os.path.join(data_path, 'naive_observations.npy'), observations)
np.save(os.path.join(data_path, 'targets.npy'), targets)

removal_order = []
for name in order:
	if name in all_hotel_names:
		removal_order.append(name)

report = []

for i in range(removals):
	print('\nTraining, testing model (removal %d / %d)' % (i + 1, removals))
	
	# Randomly permute the data to remove sequence biasing.
	p = np.random.permutation(targets.shape[0])
	x = observations[p]
	y = targets[p]

	# Split the data into (training, test) subsets.
	split = int(0.8 * len(y))
	train_x, train_y = x[:split], y[:split]
	test_x, test_y = x[split:], y[split:]

	print('Creating and training multi-layer perceptron regression model.')

	param_grid = {'hidden_layer_sizes' : [[512, 256, 128], [1024, 512, 256], [1024, 512, 256, 128]],
				  'alpha' : [5e-5, 1e-4]}

	model = GridSearchCV(MLPRegressor(), param_grid=param_grid, verbose=5, n_jobs=-1)
	model.fit(train_features, train_targets)

	print(); print('Best model hyper-parameters:', model.best_params_); print()

	model = model.best_estimator_

	train_scores.append(model.score(train_x, train_y))
	test_scores.append(model.score(test_x, test_y))

	train_y_hat = model.predict(train_x)
	test_y_hat = model.predict(test_x)

	train_mses.append(mean_squared_error(train_y, train_y_hat))
	test_mses.append(mean_squared_error(test_y, test_y_hat))
	
	np.save(os.path.join(predictions_path, 'train_targets_%d.npy' % i), train_y)
	np.save(os.path.join(predictions_path, 'train_predictions_%d.npy' % i), train_y_hat)

	np.save(os.path.join(predictions_path, 'test_targets_%d.npy' % i), test_y)
	np.save(os.path.join(predictions_path, 'test_predictions_%d.npy' % i), test_y_hat)
	
	print()
	print('*** Results after %d / %d removals ***' % (i, removals))
	print()
	print('Training MSE: %.0f' % train_mse)
	print('Training R^2: %.4f' % train_score)
	print()
	print('Test MSE: %.0f' % test_mse)
	print('Test R^2: %.4f' % test_score)
	print()
	
	# Calculate per-hotel test MSEs.
	per_hotel_test_mses = {}
	per_hotel_idxs = {}
	for idx, name in zip(hotels.ravel(), hotel_names):
		hotel_test_targs = test_targets[(hotels == idx)[split:].ravel()]
		hotel_test_preds = test_predictions[(hotels == idx)[split:].ravel()]
		per_hotel_test_mses[name] = mean_squared_error(hotel_test_targs, hotel_test_preds)
		per_hotel_idxs[name] = idx
		
	worst = max(list(per_hotel_test_mses.items()), key=lambda x : x[1])
	
	name = removal_order[i]
	
	hotel, hotel_mse, hotel_idx = name, per_hotel_test_mses[name], per_hotel_idxs[name]
	worst_hotel, worst_mse = worst[0], worst[1]
	
	print('Removed hotel\'s test MSE: %.2f' % hotel_mse)
	print('Hotel removed: %s' % hotel)
	print('Worst MSE: %.2f' % worst_mse)
	print('Hotel with worst test MSE: %s' % worst_hotel)
	
	report.append([hotel, hotel_mse, train_mse, train_score, test_mse, test_score])

	# Remove offending hotel from data.
	hotel_names = hotel_names[hotel_names != hotel]
	hotels, weekdays, months, years, targets = hotels[(hotels != hotel_idx).ravel()], \
		weekdays[(hotels != hotel_idx).ravel()], months[(hotels != hotel_idx).ravel()], \
			years[(hotels != hotel_idx).ravel()], targets[(hotels != hotel_idx).ravel()]

# Save hotel removal report to disk.
df = pd.DataFrame(report, columns=['Hotel', 'Hotel Test MSE', 'Train MSE', 'Train R^2', 'Test MSE', 'Test R^2'])
df.to_csv(os.path.join(removals_path, 'removals.csv'))

print()

train_scores = []
test_scores = []
train_mses = []
test_mses = []

for i in range(trials):  # Run 5 independent realizations of training / test.
	print('\nTraining, testing model %d / %d' % (i + 1, trials))
	
	# Randomly permute the data to remove sequence biasing.
	p = np.random.permutation(targets.shape[0])
	x = observations[p]
	y = targets[p]

	# Split the data into (training, test) subsets.
	split = int(0.8 * len(y))
	train_x, train_y = x[:split], y[:split]
	test_x, test_y = x[split:], y[split:]

	print('Creating and training multi-layer perceptron regression model.')

	model.fit(train_x, train_y)

	print('Training complete. Getting predictions and calculating R^2, MSE.')

	train_scores.append(model.score(train_x, train_y))
	test_scores.append(model.score(test_x, test_y))

	train_y_hat = model.predict(train_x)
	test_y_hat = model.predict(test_x)

	train_mses.append(mean_squared_error(train_y, train_y_hat))
	test_mses.append(mean_squared_error(test_y, test_y_hat))
	
	print()
	print('*** Results on %d / %d trial ***' % (i + 1, trials))
	print()
	print('Training MSE: %.0f' % train_mses[-1])
	print('Training R^2: %.4f' % train_scores[-1])
	print()
	print('Test MSE: %.0f' % test_mses[-1])
	print('Test R^2: %.4f' % test_scores[-1])
	print()

	np.save(os.path.join(predictions_path, 'train_targets_%d.npy' % i), train_y)
	np.save(os.path.join(predictions_path, 'train_predictions_%d.npy' % i), train_y_hat)

	np.save(os.path.join(predictions_path, 'test_targets_%d.npy' % i), test_y)
	np.save(os.path.join(predictions_path, 'test_predictions_%d.npy' % i), test_y_hat)

print()
print('*** Multiple averaged results after %d / %d removals ***' % (removals, removals))
print()
print('Mean, standard deviation of training MSE: %.0f $\pm$ %.0f' % (np.mean(train_mses), np.std(train_mses)))
print('Mean, standard deviation of training R^2: %.4f' % np.mean(train_scores))
print()
print('Mean, standard deviation of test MSE: %.0f $\pm$ %.0f' % (np.mean(test_mses), np.std(test_mses)))
print('Mean, standard deviation of test R^2: %.4f' % np.mean(test_scores))
print()
