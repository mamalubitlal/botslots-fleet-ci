# botslots-fleet-ci

Autonomous CI fleet for the BotSlots project. **The tree carries zero readable secrets** —
all operational files (scripts, playbook, state, credentials) live encrypted inside
`fleet_bundle.enc` (AES-256-CBC, PBKDF2-200k). The passphrase exists only as the
`BUNDLE_PW` Actions secret.

Workflows (scheduled, also dispatchable):
- `moltbook-loop` 3x/day — socialize + post via opencode zen free model
- `marketplace-loop` hourly — marketplace poll + TaskMarket sweep/claim
- `ops-loop` 3x/day — VPS health, bridge guard, supervisor audit

Plaintext is wiped (`runner/wipe.sh`) after every run, win or fail.
