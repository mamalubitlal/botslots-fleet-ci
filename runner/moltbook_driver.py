#!/usr/bin/env python3
"""BotSlots moltbook combined loop (CI edition).

Deterministic parts here (transport, caps, state, verify); LLM parts
(post composition, challenge solving, reply composition) delegated to
opencode zen free model via CLI. Runs fully from the decrypted bundle:
creds/ never printed, plaintext wiped after the run by wipe.sh.
"""
import json, os, re, subprocess, datetime

BASE = os.path.join(os.getcwd(), "fleet")
STATE = os.path.join(BASE, "var", "moltbook_state.json")
LOGDIR = os.path.join(BASE, "var", "agent_log")
LOG = os.path.join(LOGDIR, "moltbook_loop.log")
KEY_FILE = os.path.join(BASE, "creds", "moltbook_api_key.txt")
VPS_PW_FILE = os.path.join(BASE, "creds", "vps_root_pw")
VPS = "132.243.18.164"
API = "https://www.moltbook.com/api/v1"
WORKDIR = "/tmp/fleet_work"
MODEL = "opencode/glm-5.3-flash-free"

os.makedirs(LOGDIR, exist_ok=True)


def nowz():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    line = f"{nowz()} ci-loop: {msg}"
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def vps_curl(method, ep, payload=None):
    """Moltbook API via VPS socks (paramiko exec; direct VPS egress is geo-blocked)."""
    import paramiko
    key = open(KEY_FILE).read().strip()
    pw = open(VPS_PW_FILE).read().strip()
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(VPS, username="root", password=pw, timeout=20, banner_timeout=20)
    if method == "GET":
        cmd = ("curl -s -m 25 --socks5-hostname 127.0.0.1:1080 -H 'Authorization: Bearer "
               + key + "' '" + API + ep + "'")
    else:
        data = json.dumps(payload).replace("'", "'\\''") if payload else "{}"
        cmd = ("curl -s -m 25 --socks5-hostname 127.0.0.1:1080 -H 'Authorization: Bearer "
               + key + "' -H 'Content-Type: application/json' -X POST -d '" + data + "' '" + API + ep + "'")
    _, o, _ = cli.exec_command(cmd, timeout=45)
    out = o.read().decode("utf-8", "replace")
    cli.close()
    return out


def load_state():
    with open(STATE) as f:
        return json.load(f)


def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE)


def llm(prompt, timeout=90):
    """opencode zen free model from a clean git repo (its cwd scanner chokes on big dirs)."""
    os.makedirs(WORKDIR, exist_ok=True)
    subprocess.run(["git", "init", "-q", WORKDIR], capture_output=True)
    try:
        r = subprocess.run(
            ["opencode", "run", "-m", MODEL, prompt],
            capture_output=True, text=True, timeout=timeout, cwd=WORKDIR,
            stdin=subprocess.DEVNULL)
        out = (r.stdout or "").strip()
        if out:
            return out
        log(f"llm empty stdout err={(r.stderr or '')[:150]}")
        return None
    except subprocess.TimeoutExpired:
        log("llm timeout")
        return None


def solve_challenge(json_resp):
    p = ("Solve this arithmetic challenge. Rules: word-numbers like 'Tw En Ty ThReE' mean 23, 'SeVeN' means 7; "
         "if the text says TOTAL and 'divides IT by two' the answer is a + a/b; 'new speed/velocity' after losing X means a - X; "
         "'IMPULSE' means force times time; 'TOTAL velocity' with 'gains' means a + b; duplicated word-numbers count once; "
         "when ambiguous prefer simple arithmetic. Return ONLY the final number formatted as NN.NN (two decimals), nothing else.\n\n"
         "CHALLENGE (JSON):\n" + json_resp[:1500])
    ans = llm(p, timeout=80)
    if not ans:
        return None
    m = re.search(r"\d+\.\d{2}", ans.replace(",", ""))
    return m.group(0) if m else None


def main():
    st = load_state()
    cs = st.get("challenge_safety", {})
    if cs.get("recent_failures", 0) >= 5:
        log("ALERT: challenge failure counter >= 5, creating nothing this run")
        print("SKIP: challenge safety")
        return
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    pt = st.get("posts_today", {})
    posted_today = pt.get("count", 0) if pt.get("date") == today else 0

    # --- PHASE 1: socialize ---
    me = vps_curl("GET", "/agents/me")
    me_ok = me.strip().startswith("{")
    log(f"agents/me ok={me_ok}")
    if me_ok:
        try:
            d = json.loads(me)["data"]
            log(f"karma={d.get('karma')} followers={d.get('followers')}")
        except Exception:
            pass

    replied = 0
    try:
        home = vps_curl("GET", "/home")
        if home.strip().startswith("{"):
            notifs = json.loads(home).get("data", {}).get("notifications", [])
            my_ids = set(st.get("my_content_ids", {}).get("posts", []))
            for n in notifs[:12]:
                kind = str(n.get("type", ""))
                pid = str(n.get("post_id") or n.get("parent_post_id") or "")
                cid = str(n.get("comment_id") or "")
                if "comment" in kind and pid in my_ids and cid and replied < 3:
                    body = vps_curl("GET", "/posts/" + pid)
                    parent_txt = ""
                    try:
                        comments = json.loads(body).get("data", {}).get("post", {}).get("comments", [])
                        for c in comments:
                            if c.get("id") == cid:
                                parent_txt = str(c.get("content", ""))[:600]
                    except Exception:
                        pass
                    if not parent_txt:
                        continue
                    rep = llm(
                        "Write ONE short technical reply (2-4 sentences, plain text, no hashtags, no links) to this "
                        "comment on our Moltbook post. Be specific and useful, no product pitch unless they ask about hosting. "
                        "COMMENT:\n" + parent_txt, timeout=80)
                    if rep:
                        r = vps_curl("POST", "/posts/" + pid + "/comments", {"content": rep[:800]})
                        ok = r.strip().startswith("{") and '"error"' not in r[:80].lower()
                        log(f"reply to {cid}: {'ok' if ok else 'fail ' + r[:80]}")
                        if ok:
                            replied += 1
                    time.sleep(2)
    except Exception as e:
        log(f"socialize error: {e}")

    # --- PHASE 2: post (guarded) ---
    last_ts = st.get("last_post_ts", "")
    gap_ok = True
    try:
        lt = datetime.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        gap_min = (datetime.datetime.now(datetime.timezone.utc) - lt).total_seconds() / 60
        gap_ok = gap_min >= 29
    except Exception:
        pass
    pool = [t for t in st.get("topic_pool", []) if t not in st.get("used_topics", [])]
    verdict_recipe = ("PROMO-TEST VERDICT 2026-11-11: ops-lesson war-stories win ~5x over story/pricing angles; "
                      "direct pitch scores ZERO. Write a first-person ops war-story with one concrete technical lesson.")
    posted = False
    if gap_ok and posted_today < 12 and pool:
        topic = pool[0]
        sub = topic.get("submolt", "general")
        hint = topic.get("title") or topic.get("topic", "")
        body = llm(
            "Write a Moltbook post (150-300 words, first person, plain text, no markdown headers, no hashtags, "
            "end with ONE question to other agents). Topic submolt: " + sub + ". Angle hint: " + str(hint) + ". " +
            verdict_recipe + " Real ops material themes: restart-exactly-once-then-escalate, sandbox wipes and written "
            "playbooks as memory, half-dead proxy pipes, racing 5-minute challenge windows, hosting economics. "
            "Product mention only if natural (we run a cheap bot-hosting panel), never hard-sell, never crypto details.",
            timeout=120)
        if body and len(body) > 300:
            payload = {"submolt_name": sub, "title": (str(hint)[:90] or "Ops lesson from a live fleet"),
                       "content": body[:3500]}
            r = vps_curl("POST", "/posts", payload)
            try:
                d = json.loads(r)
            except Exception:
                d = {}
            data = d.get("data", {}) or {}
            pid = data.get("id") or (data.get("post", {}) or {}).get("id")
            ver = (data.get("verification", {}) or {})
            code = ver.get("verification_code") or data.get("verification_code")
            if pid and code:
                ans = solve_challenge(json.dumps(data)[:1600])
                if ans:
                    v = vps_curl("POST", "/verify", {"verification_code": code, "answer": ans})
                    ok = '"success":true' in v or '"verified":true' in v
                    log(f"post {pid} verify answer={ans} ok={ok} resp={v[:120]}")
                    if ok:
                        st["last_post_ts"] = nowz()
                        st["last_post_id"] = pid
                        st.setdefault("posts_today", {"date": today, "count": 0})["date"] = today
                        st["posts_today"]["count"] = posted_today + 1
                        st.setdefault("used_topics", []).append(topic)
                        st.setdefault("my_content_ids", {}).setdefault("posts", []).append(pid)
                        cs["recent_failures"] = 0
                        posted = True
                    else:
                        cs["recent_failures"] = cs.get("recent_failures", 0) + 1
                else:
                    cs["recent_failures"] = cs.get("recent_failures", 0) + 1
                    log(f"post {pid} challenge unsolved, left pending")
            else:
                log(f"post attempt: no pid/code in resp {r[:150]}")
        else:
            log("llm post composition failed/short, skipping post phase")
    else:
        log(f"post skipped (gap_ok={gap_ok} posted_today={posted_today} pool={len(pool)})")

    st["challenge_safety"] = cs
    st["last_ci_run"] = {"ts": nowz(), "replied": replied, "posted": posted}
    save_state(st)
    log(f"run done replied={replied} posted={posted} failures={cs.get('recent_failures', 0)}")
    print(f"moltbook loop done: replied={replied} posted={posted}")


if __name__ == "__main__":
    import time
    main()
