#!/bin/bash
cd /home/kavia/workspace/code-generation/sync-video-subtitle-tool-76776/subtitle_sync_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

