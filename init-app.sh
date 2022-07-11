#!/bin/bash

set -exo pipefail

rdb_dir="/db"
dump_file="dump.rdb"

# set parent directory of redis .rdb based on env var, if not use default
if [ $REDIS_DUMP_DIR ]; then
    $rdb_dir=$REDIS_DUMP_DIR
fi

# set the name of the .rdb file based on env var, if not use default
if [ $REDIS_DUMPFILE ]; then
    $dump_file=$REDIS_DUMPFILE
fi

# check for .rdb file before running redis-server
if [ -f "${rdb_dir}/${dump_file}" ]; then
    echo "Starting redis-server with database path: ${rdb_dir}/${dump_file}"
    nohup redis-server redis.conf --dbfilename $dump_file --dir $rdb_dir &
elif [ $REDIS_DUMP_DIR ]; then
    echo "Warning: No redis dump file named ${dump_file} at path ${rdb_dir}, using directory ${rdb_dir} to store dumpfile"
    nohup redis-server redis.conf --dir $rdb_dir &
else
    echo "Warning: No redis dump file named ${dump_file} at path ${rdb_dir}, default path ${rdb_dir} to store dumpfile"
    nohup redis-server redis.conf --dir $rdb_dir &
fi

# run the app
python3 main.py 