#!/bin/bash


set -exo pipefail

REDIS_RDB_DIR="/db"
REDIS_DUMP_FILE=dump.rdb
REDIS_CONFIG_FILE=redis.conf
REDIS_CONFIG_TEMPLATE=redis.conf.template

export REDIS_RDB_DIR REDIS_DUMP_FILE REDIS_CONFIG_FILE


function show_help() {
    cat >&2 <<EOF
$0 --dump-file FILE --dumpfile-dir PATH --config-file FILE --config-template FILE
Starts redis server backend with a given name for a dumpfile, parent directory for dumpfile and a given redis.conf file for server configuration
Required:
    -f FILENAME --dump-file FILENAME
        Name of .rdb file 
    -d PATH --dumpfile-dir PATH
        Parent path that will contain .rdb dumpfile
    -c FILE --config-file FILE
        File for configuring redis server on boot
Optional
    -t FILE --template-file FILE
        Path to template file to generate configfrom
EOF
    exit 1
}

while [ "$#" -gt 0 ]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -f|--dump-file)
            REDIS_DUMP_FILE="$2"
            shift 2
            ;;
        -d|--dumpfile-dir)
            REDIS_RDB_DIR="$2"
            shift 2
            ;;
        -c|--config-file)
            REDIS_CONFIG_FILE="$2"
            shift 2
            ;;
        -t|--template-file)
            REDIS_CONFIG_TEMPLATE="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Invalid option $1 provided." >&2
            show_help
            ;;
    esac
done

# rdb_dir="${REDIS_DUMP_DIR:-/db}"
# dump_file="${REDIS_DUMPFILE:-'dump.rdb'}"

# # set parent directory of redis .rdb based on env var, if not use default
# if [ $REDIS_DUMP_DIR ]; then
#     $rdb_dir=$REDIS_DUMP_DIR
# fi

# # set the name of the .rdb file based on env var, if not use default
# if [ $REDIS_DUMPFILE ]; then
#     $dump_file=$REDIS_DUMPFILE
# fi

if [ -f $REDIS_CONFIG_TEMPLATE ]; then
    envsubst < $REDIS_CONFIG_TEMPLATE > $REDIS_CONFIG_FILE
fi


redis-server /"${REDIS_CONFIG_FILE}" --dbfilename $REDIS_DUMP_FILE --dir $REDIS_RDB_DIR

# # check for .rdb file before running redis-server
# if [ -f "${REDIS_DUMP_DIR}/${REDIS_DUMP_FILE}" ]; then
#     echo "Starting redis-server with database path: ${rdb_dir}/${dump_file}"
#     redis-server redis.conf --dbfilename $dump_file --dir $rdb_dir 
# elif [ $REDIS_DUMP_DIR ]; then
#     echo "Warning: No redis dump file named ${dump_file} at path ${rdb_dir}, using directory ${rdb_dir} to store dumpfile"
#     redis-server redis.conf --dir $rdb_dir 
# else
#     echo "Warning: No redis dump file named ${dump_file} at path ${rdb_dir}, default path ${rdb_dir} to store dumpfile"
#     redis-server redis.conf --dir $rdb_dir 
# fi
