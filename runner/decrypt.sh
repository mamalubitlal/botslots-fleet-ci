#!/bin/bash
# Decrypt the fleet bundle into ./fleet (plaintext wiped at run end by wipe.sh)
set -e
: "${BUNDLE_PW:?BUNDLE_PW secret required}"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in fleet_bundle.enc -out fleet_bundle.tar.gz -pass env:BUNDLE_PW
tar -xzf fleet_bundle.tar.gz
rm fleet_bundle.tar.gz
chmod -R go-rwx fleet/creds
echo "decrypted: $(find fleet -type f | wc -l) files"
