#!/usr/bin/env bash
PID=$(sudo systemctl show --property MainPID --value wilsonbot)
sudo kill -9 $PID
sudo systemctl restart wilsonbot.service
