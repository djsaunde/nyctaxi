distance=${1:-100}

declare -a fnames=("yellow_tripdata_2015-05.csv", "yellow_tripdata_2014-08.csv")

for fname in "${fnames[@]}"
do
	sbatch filename_one_preprocess.sh $distance $fname
done