#!/bin/bash

set -exo pipefail

nohup /usr/local/bin/rqscheduler > scheduler.log &
nohup rqworker --with-scheduler metadata --name metadata > metadata_worker.log &
nohup rqworker --with-scheduler generic_worker --name generic_worker > generic_worker.log &
nohup rqworker plays --name plays > plays_worker.log &

# run the app
python3 main.py 