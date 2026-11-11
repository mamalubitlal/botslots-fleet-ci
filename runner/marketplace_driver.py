#!/usr/bin/env python3
"""BotSlots marketplace loop (CI edition).

(1) Runs the legacy marketplace_poll.py (Hansa/AgentPact/Toku/OpenTask/ugig).
(2) TaskMarket sweep: taskmarket CLI on base+tempo, queues new tasks, claims
    only claim-mode data-vertical tasks (no purchase/KYC/stake/memecoin),
    submits deliverables composed via opencode zen free model for writing tasks.
State committed back encrypted; creds never printed.
"""
import json, os, subprocess, sys, datetime

BASE = os.path.join(os.getcwd(), "fleet")
STATE = os.path.join(BASE, "var", "taskmarket_state.json")
QUEUE = os.path.join(BASE, "var", "marketplace_queue.json")
LOGDIR = os.path.join(BASE, "var", "agent_log")
LOG = os.path.join(LOGDIR, "marketplaces.log")
POLL = os.path.join(BASE, "scripts", "marketplace_poll.py")
WORKDIR = "/tmp/fleet_work"
MODEL = "opencode/glm-5.3-flash-free"

os.makedirs(LOGDIR, exist_ok=True)
VETO = ("purchase", "buy", "buy_", "lumen house", "flapjax", "video model", "memecoin")


def nowz():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{nowz()} ci-marketplace: {msg}\n")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def tm(*args, timeout=90):
    r = subprocess.run(["taskmarket", "--network", args[0]] + list(args[1:]),
                       capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "").strip()
    try:
        return json.loads(out)
    except Exception:
        return None


def llm(prompt, timeout=150):
    os.makedirs(WORKDIR, exist_ok=True)
    subprocess.run(["git", "init", "-q", WORKDIR], capture_output=True)
    try:
        r = subprocess.run(["opencode", "run", "-m", MODEL, prompt],
                           capture_output=True, text=True, timeout=timeout,
                           cwd=WORKDIR, stdin=subprocess.DEVNULL)
        out = (r.stdout or "").strip()
        return out if out and len(out) > 80 else None
    except subprocess.TimeoutExpired:
        log("llm timeout")
        return None


def matches_vertical(desc):
    d = desc.lower()
    good = any(k in d for k in ("write", "article", "research", "markdown", "csv", "data", "analysis", "summar", "report"))
    bad = any(k in d for k in VETO)
    return good and not bad


def sweep_taskmarket(st):
    seen = set(st.get("tasks_seen", {}).get("tempo", [])) | set(st.get("tasks_seen", {}).get("base", []))
    queued_new = 0
    for net in ("tempo", "base"):
        d = tm(net, "task", "list", "--status", "open")
        if not d:
            log(f"taskmarket {net}: list failed")
            continue
        tasks = d.get("data", {}).get("tasks", [])
        log(f"taskmarket {net}: {len(tasks)} open")
        for t in tasks:
            ref = t.get("referenceCode")
            if not ref or ref in seen:
                continue
            desc = str(t.get("description", ""))
            mode = t.get("mode")
            reward = str(t.get("reward", ""))
            stake = t.get("stakeRequired", False)
            entry = {"ref": ref, "network": net, "mode": mode, "reward": reward,
                     "desc": desc[:200], "seen_at": nowz()}
            q = load(QUEUE, {"queue": []})
            q["queue"] = [x for x in q.get("queue", []) if x.get("ref") != ref]
            q["queue"].append(entry)
            save(QUEUE, q)
            st.setdefault("tasks_seen", {}).setdefault(net, []).append(ref)
            queued_new += 1
            # claim-mode + matching vertical -> submit deliverable
            if mode == "claim" and matches_vertical(desc) and not stake:
                deliver = llm(
                    "Produce a complete, high-quality deliverable for this agent-marketplace task. "
                    "Original writing only, no invented facts, markdown format, comprehensive but focused.\n\n"
                    "TASK:\n" + desc[:2000], timeout=240)
                if deliver:
                    path = f"/tmp/deliver_{ref}.md"
                    open(path, "w").write(deliver)
                    sub = tm(net, "task", "submit", t.get("id"), "--file", path, timeout=180)
                    ok = bool(sub and sub.get("ok"))
                    log(f"CLAIM-SUBMIT {ref}: {'ok' if ok else 'fail ' + json.dumps(sub)[:120]}")
                    if ok:
                        st.setdefault("submissions", []).append(
                            {"task": ref, "at": nowz(), "mode": "claim"})
    return queued_new


def main():
    st = load(STATE, {})
    # (1) legacy poller (Hansa/AgentPact/Toku/OpenTask/ugig) - tolerate failure
    try:
        r = subprocess.run([sys.executable, POLL], capture_output=True, text=True,
                           timeout=240, cwd=os.getcwd())
        log(f"marketplace_poll rc={r.returncode} out={r.stdout[-200:] if r.stdout else ''}")
    except Exception as e:
        log(f"marketplace_poll error: {e}")

    # (2) TaskMarket sweep
    try:
        n = sweep_taskmarket(st)
        log(f"taskmarket sweep queued_new={n}")
    except Exception as e:
        log(f"taskmarket sweep error: {e}")

    st["last_ci_run"] = nowz()
    save(STATE, st)
    print(f"marketplace loop done, see {LOG}")


if __name__ == "__main__":
    main()
