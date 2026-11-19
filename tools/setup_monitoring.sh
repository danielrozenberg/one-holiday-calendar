#!/usr/bin/env bash
#
# Sets up monitoring for the App Engine app, mirroring nyc-city-bike-at-a-glance:
# an email channel, an uptime check on /versionz, and alerts when the uptime
# check fails, when errors are logged, or when a second instance is billed.
# Safe to rerun: existing channels, checks and policies are reused by name.
#
# Usage:  ALERT_EMAIL=you@example.com ./tools/setup_monitoring.sh
set -euo pipefail

PROJECT="one-holiday-calendar"
HOST="${PROJECT}.appspot.com"
EMAIL="${ALERT_EMAIL:?Set ALERT_EMAIL to the address that gets alerts}"

channel="$(gcloud alpha monitoring channels list --project="$PROJECT" \
  --filter="type=\"email\" AND labels.email_address=\"$EMAIL\"" \
  --format="value(name)" | head -n 1)"
if [[ -z "$channel" ]]; then
  channel="$(gcloud alpha monitoring channels create --project="$PROJECT" \
    --type=email --display-name=email \
    --channel-labels="email_address=$EMAIL" --format="value(name)")"
fi
echo "Notification channel: $channel"

check="$(gcloud monitoring uptime list-configs --project="$PROJECT" \
  --filter='displayName="versionz"' --format="value(name)" | head -n 1)"
if [[ -z "$check" ]]; then
  check="$(gcloud monitoring uptime create versionz --project="$PROJECT" \
    --resource-type=uptime-url \
    --resource-labels="host=$HOST,project_id=$PROJECT" \
    --protocol=https --path=/versionz --validate-ssl=true \
    --status-classes=2xx --period=1 --timeout=10 --format="value(name)")"
fi
check_id="${check##*/}"
echo "Uptime check: $check"

# Creates an alert policy from the YAML on stdin unless one with its display
# name exists.
policy() {
  local name="$1" file
  if [[ -n "$(gcloud alpha monitoring policies list --project="$PROJECT" \
    --filter="displayName=\"$name\"" --format="value(name)")" ]]; then
    echo "Alert exists: $name"
    return
  fi
  file="$(mktemp)"
  cat > "$file"
  gcloud alpha monitoring policies create --project="$PROJECT" \
    --policy-from-file="$file" --format="value(name)"
  rm -f "$file"
  echo "Alert created: $name"
}

policy "Uptime check failure" <<EOF
displayName: Uptime check failure
combiner: OR
notificationChannels: ["$channel"]
conditions:
  - displayName: Failure of uptime check $check_id
    conditionThreshold:
      filter: >-
        metric.type="monitoring.googleapis.com/uptime_check/check_passed"
        AND metric.label.check_id="$check_id"
        AND resource.type="uptime_url"
      aggregations:
        - alignmentPeriod: 1200s
          perSeriesAligner: ALIGN_NEXT_OLDER
          crossSeriesReducer: REDUCE_COUNT_FALSE
          groupByFields: ["resource.label.*"]
      comparison: COMPARISON_GT
      thresholdValue: 1
      duration: 60s
      trigger: {count: 1}
EOF

policy "Multiple errors have been logged within 5 minutes" <<EOF
displayName: Multiple errors have been logged within 5 minutes
combiner: OR
notificationChannels: ["$channel"]
alertStrategy: {autoClose: 604800s}
conditions:
  - displayName: GAE Application - Log entries
    conditionThreshold:
      filter: >-
        resource.type = "gae_app"
        AND metric.type = "logging.googleapis.com/log_entry_count"
        AND metric.labels.severity = "ERROR"
      aggregations:
        - alignmentPeriod: 300s
          perSeriesAligner: ALIGN_SUM
      comparison: COMPARISON_GT
      thresholdValue: 2
      duration: 0s
      trigger: {count: 1}
EOF

policy "Estimated instance count is above 1 for 2×15 minutes" <<EOF
displayName: Estimated instance count is above 1 for 2×15 minutes
combiner: OR
notificationChannels: ["$channel"]
alertStrategy: {autoClose: 604800s}
conditions:
  - displayName: GAE Application - Estimated instance count
    conditionThreshold:
      filter: >-
        resource.type = "gae_app"
        AND metric.type = "appengine.googleapis.com/system/billed_instance_estimate_count"
      aggregations:
        - alignmentPeriod: 900s
          perSeriesAligner: ALIGN_MAX
          crossSeriesReducer: REDUCE_SUM
      comparison: COMPARISON_GT
      thresholdValue: 1
      duration: 0s
      trigger: {count: 2}
EOF
