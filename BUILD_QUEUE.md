# BUILD_QUEUE — consumed by ai-build.yml (hourly GitHub cron)

How it works: the workflow takes the first unchecked `- [ ]` item, hands it
to opencode zen in CI, and opens a draft PR with the implementation draft.
Check items off as their PRs merge. Add new items freely — GitHub cron
replaces platform crons entirely (owner rule 2026-11-24). Requires the
repo secret OPENCODE_ZEN_KEY.

## Queue

- [ ] [AI-61] Weekly "what changed in my logs" summary per bot (opencode-routed; diff last 7d bot_log per slot, honest wording)
- [ ] [AI-62] Auto-draft gallery descriptions from slot code, RU + EN (opencode-routed)
- [ ] [AI-63] Crash triage: paste a traceback, get explanation + suggested patch (opencode-routed, no auto-apply)
- [ ] [AI-64] Config reviewer: checks .env/config for classic mistakes before deploy (opencode-routed)
- [ ] [AI-65] Test generator: pytest smoke tests for a slot's code (opencode-routed, tests land as draft)
- [ ] [AI-66] README generator for each slot from its code (opencode-routed)
- [ ] [AI-67] Cost advisor: which add-ons you barely use, from real api_meter/user_addons data only (opencode-routed, no invented numbers)
- [ ] [AI-68] Changelog writer: converts deploy diffs into a human changelog (opencode-routed)
- [ ] [AI-69] Migration helper: converts competitor-host configs to BotSlots format (opencode-routed)
- [ ] [AI-70] Support pre-answer: drafts a reply from ticket text + relevant log excerpts (opencode-routed, staff sends manually)
- [ ] v2-48 GitHub App install mode for deploy-from-git (no personal tokens): accept App installation webhooks, installation-token clone path
- [ ] v2-55 Canary deploys: 10-min trial run on deploy-from-git, auto-rollback on error spike (reaper incident data)
- [ ] v2-77 Official BotSlots TG bot: signup, renewals, alerts in-chat (long-poll worker, account link via pairing code)
- [ ] Add pytest smoke suite for /opt/botslots add-on rail (db.ADDONS -> invoice -> activate -> /addon page)
- [ ] Public docs page listing all SKUs with prices pulled from db.ADDONS
- [ ] RU translations for the 10 new add-on pages (addon_db, addon_logs, bottemplates, addon_toolkit, addon_mail, addon_shots, addon_git, addon_wizard, addon_agent, addon_burst)
- [ ] Burst Boost: per-slot selection instead of all-slots-at-once
- [ ] A4 logs: webhook alerting on ERROR burst (reuse watcher plumbing)
- [ ] D3 mailrelay: DKIM setup guide per provider (Mailgun/SES/postmark)
- [ ] Status page: embeddable badge PNG endpoint
- [ ] Template gallery: community template submission flow

Standing rules for every build: backup, patch, py_compile, restart,
e2e, verify live, log; pricing always read from db.ADDONS/PLANS; honest
wording only; no invented numbers.
