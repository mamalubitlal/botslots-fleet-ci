#!/usr/bin/env python3
"""BotSlots ops loop (CI edition): VPS health + bridge guard + supervisor
staleness audit. Pre-approved remediation only (single restart each for
botslots/healthz-fail and residential-socks/socks-dead). Writes logs into the
bundle tree (committed back encrypted).
"""
import json, os, datetime, subprocess, ssl, socket

BASE = os.path.join(os.getcwd(), "fleet")
LOGDIR = os.path.join(BASE, "var", "agent_log")
VPS_PW_FILE = os.path.join(BASE, "creds", "vps_root_pw")
VPS = "132.243.18.164"

os.makedirs(LOGDIR, exist_ok=True)
os.makedirs(os.path.join(BASE, "var"), exist_ok=True)


def nowz():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(path, msg):
    with open(os.path.join(LOGDIR, path), "a") as f:
        f.write(f"{nowz()} {msg}\n")


def vps_exec(cmd, timeout=40):
    import paramiko
    pw = open(VPS_PW_FILE).read().strip()
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(VPS, username="root", password=pw, timeout=20, banner_timeout=20)
    _, o, _ = cli.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    cli.close()
    return out


def public_check(url):
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-m", "20", url],
                       capture_output=True, text=True)
    return r.stdout.strip()


def tls_days(host):
    r = subprocess.run(["bash", "-c",
                        f"echo | openssl s_client -servername {host} -connect {host}:443 2>/dev/null | "
                        f"openssl x509 -noout -enddate"],
                       capture_output=True, text=True)
    try:
        from datetime import datetime as dt
        end = r.stdout.strip().split("=")[1]
        days = (dt.strptime(end, "%b %d %H:%M:%S %Y GMT") - dt.now()).days
        return days
    except Exception:
        return -1


def main():
    findings = {}
    # services
    svc = vps_exec("systemctl is-active botslots nginx residential-socks sing-box 2>/dev/null | tr '\\n' ' '")
    findings["services"] = svc.strip()
    # healthz
    hz = vps_exec("curl -s -m 10 http://127.0.0.1:8080/healthz")
    hz_ok = '"ok":true' in hz
    findings["healthz_ok"] = hz_ok
    if not hz_ok:
        vps_exec("systemctl restart botslots")
        hz2 = vps_exec("curl -s -m 10 http://127.0.0.1:8080/healthz")
        findings["healthz_after_restart"] = '"ok":true' in hz2
        log("ops_loop.log", f"healthz FAIL -> restarted botslots, after={findings['healthz_after_restart']}")
    # disk
    disk = vps_exec("df --output=pcent / | tail -1 | tr -dc '0-9'")
    findings["disk_pct"] = disk.strip()
    # tls
    findings["tls_days"] = {"chator.space": tls_days("chator.space"),
                            "botslots.duckdns.org": tls_days("botslots.duckdns.org")}
    # public checks
    findings["public"] = {
        "duckdns_miniapp": public_check("https://botslots.duckdns.org/miniapp"),
        "chator": public_check("https://chator.space/"),
        "chator_ru": public_check("https://chator.space/ru/"),
    }
    # socks exit ip + bridge listeners
    ip = vps_exec("curl -s -m 15 --socks5-hostname 127.0.0.1:1090 https://api.ipify.org")
    findings["socks_exit_ip"] = ip.strip()[:64]
    listeners = vps_exec("ss -tln | grep -E ':2222|:2223' | awk '{print $4}' | tr '\\n' ' '")
    findings["bridge_listeners"] = listeners.strip()
    # ssh noise (non-Alibaba)
    ssh = vps_exec("grep 'Accepted' /var/log/auth.log 2>/dev/null | tail -40 | grep -oE 'from [0-9.]+' | awk '{print $2}' | sort -u | grep -vE '^(47\\.|8\\.212\\.)' | head -5 | tr '\\n' ' '")
    findings["ssh_non_baseline"] = ssh.strip()
    if ssh.strip():
        log("incidents.log", f"NON-BASELINE SSH SOURCES: {ssh.strip()}")

    log("ops_loop.log", "CI ops: " + json.dumps(findings))
    log("bridge_guard.log", "CI bridge: listeners=" + findings["bridge_listeners"] +
        " socks_exit=" + findings["socks_exit_ip"] + " active_service=see listeners")
    # supervisor-style staleness lines
    for name, hours in (("marketing_loop.log", 12), ("brainstormer.log", 24), ("seo_agent.log", 26)):
        p = os.path.join(LOGDIR, name)
        stale = True
        if os.path.exists(p):
            age = (datetime.datetime.now().timestamp() - os.path.getmtime(p)) / 3600
            stale = age > hours
        if stale:
            log(name, f"SUPERVISOR (ci): missed run detected (no fresh entry; threshold {hours}h)")
    print("ops loop done: " + json.dumps(findings)[:400])


if __name__ == "__main__":
    main()
