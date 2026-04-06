#!/bin/bash
echo "🚀 Starting bot with auto-restart..."
while true; do
    python3 bot.py
    EXIT_CODE=$?
    echo "⚠️ Bot stopped (exit code: $EXIT_CODE). Restarting in 5 seconds..."
    sleep 5
done
