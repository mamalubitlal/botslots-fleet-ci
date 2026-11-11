#!/bin/bash
# Re-encrypt the bundle (state updated by the driver) and push.
set -e
tar -czf fleet_bundle.tar.gz fleet
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in fleet_bundle.tar.gz -out fleet_bundle.enc.new -pass env:BUNDLE_PW
mv fleet_bundle.enc.new fleet_bundle.enc
rm fleet_bundle.tar.gz
git config user.name "fleet-ci-bot"
git config user.email "botslots-ci@users.noreply.github.com"
git add fleet_bundle.enc
if git diff --cached --quiet; then echo "no state changes"; else
  git commit -m "state: ${WORKFLOW_NAME:-manual} $(date -u +%Y-%m-%dT%H:%MZ) [skip ci]"
  git push
fi
