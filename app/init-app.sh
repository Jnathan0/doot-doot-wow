#!/bin/sh

# Set timezone preference using $TZ env var
# Can be configured as a docker runtime variable
# Default: UTC
cp /usr/share/zoneinfo/$TZ /etc/localtime

set -exo pipefail

nohup /env/bin/rqscheduler > scheduler.log &
nohup rqworker --with-scheduler metadata --name metadata > metadata_worker.log &
nohup rqworker --with-scheduler generic_worker --name generic_worker > generic_worker.log &
nohup rqworker plays --name plays > plays_worker.log &

# run the app
poetry run python3 main.py 
