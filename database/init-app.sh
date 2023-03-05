#!/bin/bash

set -e

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:=postgres}" --dbname "${POSTGRES_DB:=sounds}" 
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /schema/sounds.sql