#!/usr/bin/env bash
# Daemonize the SnapList server so it survives the parent shell/tool session.
fuser -k 8000/tcp 2>/dev/null
pkill -9 -f snaplist 2>/dev/null
sleep 1
cd /home/kibo/SnapList
setsid /home/kibo/SnapList/.venv/bin/python -m snaplist.cli serve --port 8000 \
  </dev/null >/tmp/snaplist.log 2>&1 &
echo "started"
