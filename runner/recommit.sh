#!/bin/bash
# Re-encrypt the bundle (state updated by the driver) and push.
# Concurrent runs race on the binary bundle -> fetch/reset --soft/retry loop
# (last-writer-wins; each run's stdout carries its own state summary).
set -e
tar -czf fleet_bundle.tar.gz fleet
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in fleet_bundle.tar.gz -out fleet_bundle.enc.new -pass env:BUNDLE_PW
mv fleet_bundle.enc.new fleet_bundle.enc
rm fleet_bundle.tar.gz
git config user.name "fleet-ci-bot"
git config user.email "botslots-ci@users.noreply.github.com"
for i in 1 2 3; do
  git fetch origin main
  git reset --soft origin/main
  git add fleet_bundle.enc
  if git diff --cached --quiet; then echo "no state changes (attempt $i)"; exit 0; fi
  git commit -m "state: ${WORKFLOW_NAME:-manual} $(date -u +%Y-%m-%dT%H:%MZ) [skip ci]"
  if git push origin HEAD:main; then echo "pushed (attempt $i)"; exit 0; fi
  echo "push race (attempt $i), retrying"
  sleep $((i * 10))
done
echo "push failed after retries - state preserved in run log only"
exit 1
