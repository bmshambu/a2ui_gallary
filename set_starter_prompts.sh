#!/usr/bin/env bash
# Set Gemini Enterprise starter prompts (the clickable suggestion chips shown
# BEFORE the user types anything). These are GE assistant config, not agent code.
#
# Clicked starter prompts arrive as real message text, so they route through the
# agent's normal typed-message markers (unlike A2UI button clicks). Combine:
# starter prompts for turn 1, A2UI nav buttons for every turn after.
#
# Prereqs: gcloud auth login with access to the GE app's project.
# Fill in these three values from your GE app (Admin console → app details):
PROJECT_ID="${PROJECT_ID:-YOUR_PROJECT_ID}"
LOCATION="${LOCATION:-global}"          # GE apps are usually in "global"
ENGINE_ID="${ENGINE_ID:-YOUR_APP_ID}"   # the GE app / engine id

ENDPOINT_HOST="discoveryengine.googleapis.com"
[ "$LOCATION" != "global" ] && ENDPOINT_HOST="${LOCATION}-discoveryengine.googleapis.com"

URL="https://${ENDPOINT_HOST}/v1/projects/${PROJECT_ID}/locations/${LOCATION}/collections/default_collection/engines/${ENGINE_ID}/assistants/default_assistant?updateMask=starterPrompts"

curl -sS -X PATCH \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${URL}" \
  -d '{
    "starterPrompts": [
      { "text": "Show me a form with validation" },
      { "text": "Show me a data table" },
      { "text": "Show me a dropdown picker" },
      { "text": "Show me the references" },
      { "text": "What components can you show?" }
    ]
  }'
