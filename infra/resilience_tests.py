#!/usr/bin/env python3
"""
resilience_tests.py - breaks the running system on purpose and measures how it recovers.

Run it from your PC (needs the server up, the .pem key and ssh in the PATH):

    python resilience_tests.py                      # tests 1 to 4 (about 10 minutes)
    python resilience_tests.py --include-server-loss  # also destroys the server and rebuilds it (+12 min)
    python resilience_tests.py --only crash-db      # one test

Tests (each one records: failure, expectation, observation, recovery time):
    crash-app      kill -9 on GlassFish           -> systemd restarts it
    crash-db       kill -9 on the MySQL container -> Docker restarts it, data intact
    load           300 requests, 20 at a time + login flood -> service stays up, nginx limits logins
    bad-war        a corrupt file and a broken WAR as new versions -> the running version survives
    server-loss    terminate the EC2 instance      -> rebuild with deploy.py and restore the backup

It writes resilience_report.md and resilience_report.json next to this file.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import config
import deploy

HERE = os.path.dirname(os.path.abspath(__file__))
API = f"/{config.CONTEXT_ROOT}/api"
RESULTS = []


def say(message=""):
    print(message, flush=True)


# ------------------------------------------------------------------ helpers

def http(host, path, method="GET", body=None, timeout=6):
    """Returns (status code or 0, body text)."""
    request = urllib.request.Request(f"http://{host}{path}", method=method,
                                     data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except Exception:
        return 0, ""


def api_ok(host):
    return http(host, f"{API}/restaurants")[0]


def count(host, resource):
    code, text = http(host, f"{API}/{resource}")
    if code != 200:
        return None
    try:
        return len(json.loads(text))
    except ValueError:
        return None


def snapshot(host):
    return {"restaurants": count(host, "restaurants"), "reviews": count(host, "reviews")}


def ssh(host, command, pem, data=None, timeout=180):
    """Runs a command on the server. Returns (exit code, output text)."""
    args = ["ssh", "-i", pem, "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={os.devnull}",
            "-o", "ConnectTimeout=15", "-o", "LogLevel=ERROR", f"ec2-user@{host}", command]
    done = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    return done.returncode, (done.stdout + done.stderr).decode("utf-8", "replace")


def measure_recovery(host, timeout, grace=15):
    """After a failure was injected: seconds until the API answers 200 again.
    Returns (seconds or None, codes seen). 0.0 means no outage was ever seen."""
    start = time.time()
    seen, saw_failure = [], False
    while time.time() - start < timeout:
        code = api_ok(host)
        seen.append(code)
        elapsed = time.time() - start
        if code != 200:
            saw_failure = True
        elif saw_failure:
            return round(elapsed, 1), seen
        elif elapsed > grace:
            return 0.0, seen
        time.sleep(2)
    return None, seen


def wait_healthy(host, timeout=180):
    """Waits until the API answers 200 (used so one test does not leak into the next)."""
    start = time.time()
    while time.time() - start < timeout:
        if api_ok(host) == 200:
            return True
        time.sleep(3)
    return False


def codes_text(seen):
    summary = {}
    for code in seen:
        summary[code] = summary.get(code, 0) + 1
    return ", ".join(f"{count}x HTTP {code}" if code else f"{count}x no answer" for code, count in sorted(summary.items()))


def record(name, failure, expected, observed, seconds, passed):
    RESULTS.append({"test": name, "failure": failure, "expected": expected, "observed": observed,
                    "recovery_seconds": seconds, "passed": passed})
    say(f"\n  -> {'PASS' if passed else 'FAIL'}: {observed}")


def same_data(before, after):
    return all(before[k] is None or before[k] == after[k] for k in before)


# -------------------------------------------------------------------- tests

def test_crash_app(ctx):
    say("\n[1] crash-app: kill -9 on GlassFish")
    before = snapshot(ctx.host)
    ssh(ctx.host, "sudo pkill -9 java; true", ctx.pem)
    seconds, seen = measure_recovery(ctx.host, 240)
    after = snapshot(ctx.host)
    ok = seconds is not None and same_data(before, after)
    record("crash-app", "kill -9 of the GlassFish process",
           "systemd restarts GlassFish by itself (Restart=always); the app comes back with the same data",
           f"{codes_text(seen)}; data before {before}, after {after}",
           seconds, ok)


def test_crash_db(ctx):
    say("\n[2] crash-db: kill -9 on the MySQL process")
    before = snapshot(ctx.host)
    # kill -9 on the mysqld process from the host: Docker sees a crash (exit 137), not a manual stop
    ssh(ctx.host, "sudo kill -9 $(sudo docker inspect -f '{{.State.Pid}}' rr-mysql)", ctx.pem)
    seconds, seen = measure_recovery(ctx.host, 180)
    after = snapshot(ctx.host)
    ok = seconds is not None and same_data(before, after)
    if seconds is None:
        ssh(ctx.host, "sudo docker start rr-mysql", ctx.pem)   # leave the system healthy
        wait_healthy(ctx.host)
    errors = [c for c in seen if c not in (0, 200)]
    record("crash-db", "kill -9 of the mysqld process (a crash, not a manual stop)",
           "while MySQL is down the API answers 500 (it does not crash); Docker restarts MySQL (unless-stopped); data intact",
           f"{codes_text(seen)}; data before {before}, after {after}; "
           f"{'errors were clean HTTP codes' if errors else 'no outage visible'}",
           seconds, ok)


def test_load(ctx):
    say("\n[3] load: 300 requests (20 at a time) and 60 simultaneous login attempts")
    wait_healthy(ctx.host)
    latencies, failures = [], [0]
    lock = threading.Lock()

    def one(_):
        started = time.time()
        code = http(ctx.host, f"{API}/restaurants", timeout=20)[0]
        with lock:
            latencies.append((time.time() - started) * 1000)
            if code != 200:
                failures[0] += 1

    started = time.time()
    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(one, range(300)))
    duration = time.time() - started
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]

    body = json.dumps({"username": "resilience_probe", "password": "wrong-password"}).encode()
    with ThreadPoolExecutor(max_workers=30) as pool:
        codes = list(pool.map(lambda _: http(ctx.host, f"{API}/auth/login", "POST", body)[0], range(60)))
    limited = codes.count(503) + codes.count(429)
    alive = api_ok(ctx.host)
    ok = failures[0] == 0 and limited > 0 and alive == 200
    record("load", "300 requests with 20 concurrent users, then 60 simultaneous login attempts",
           "no failed request; nginx limits the login burst (HTTP 503) and the API keeps answering",
           f"{300 - failures[0]}/300 requests OK in {duration:.1f}s ({300 / duration:.0f} req/s), "
           f"median {p50:.0f} ms, p95 {p95:.0f} ms; login burst: {codes.count(401)} answered 401, "
           f"{limited} blocked by the limiter; API after the burst: HTTP {alive}",
           None, ok)


def make_war(path, web_xml):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("WEB-INF/web.xml", web_xml)


def test_bad_war(ctx):
    say("\n[4] bad-war: publishing broken versions")
    deployer_fix(ctx)
    good = deploy.get_param(ctx.ssm, "war_key")
    previous = deploy.get_param(ctx.ssm, "war_key_previous")
    cases = [
        ("a file that is not a WAR", lambda p: open(p, "wb").write(b"this is not a zip file"),
         lambda key: [f"REJECTED {key}"],
         "the file is rejected before touching the running app: zero downtime"),
        ("a WAR with a broken web.xml", lambda p: make_war(p, "<<< this is not xml"),
         lambda key: [f"FAILED to deploy {key}", "previous version restored"],
         "GlassFish fails to deploy it and the previous version is restored automatically"),
    ]
    uploaded = []
    for label, build, markers, expectation in cases:
        say(f"  - {label}")
        path = os.path.join(tempfile.mkdtemp(), "bad.war")
        build(path)
        key = deploy.upload_war(ctx.s3, ctx.ssm, ctx.bucket, path)
        uploaded.append(key)
        started, samples, found = time.time(), [], False
        while time.time() - started < 300:
            samples.append((time.time() - started, api_ok(ctx.host)))
            _, log = ssh(ctx.host, "sudo journalctl -u rr-deploy --no-pager -n 30", ctx.pem)
            found = all(marker in log for marker in markers(key))
            if found and samples[-1][1] == 200:
                break
            time.sleep(4)
        failed_times = [t for t, code in samples if code != 200]
        downtime = round(failed_times[-1] - failed_times[0] + 6, 1) if failed_times else 0.0
        final = api_ok(ctx.host)
        ok = found and final == 200
        record("bad-war", f"publish {label} as the new version", expectation,
               f"{codes_text([c for _, c in samples])}; deployer log {'shows' if found else 'does NOT show'} "
               f"the expected lines; API at the end: HTTP {final}", downtime, ok)
    # leave the system as it was
    deploy.put_string_param(ctx.ssm, "war_key", good)
    if previous:
        deploy.put_string_param(ctx.ssm, "war_key_previous", previous)
    for key in uploaded:
        ctx.s3.delete_object(Bucket=ctx.bucket, Key=key)
    say("  (publishing the original version again)")
    api_ok(ctx.host)


def deployer_fix(ctx):
    """Makes sure the server runs the latest deployer script (idempotent)."""
    text = deploy.render_user_data(ctx.bucket, ctx.region)
    match = re.search(r"cat > /usr/local/bin/rr-deploy-war <<'DEPLOYEOF'\n(.*?)DEPLOYEOF\n", text, re.S)
    wanted = match.group(1).replace("\r\n", "\n")
    _, current = ssh(ctx.host, "sudo cat /usr/local/bin/rr-deploy-war", ctx.pem)
    if current.replace("\r\n", "\n").strip() != wanted.strip():
        ssh(ctx.host, "sudo tee /usr/local/bin/rr-deploy-war >/dev/null && sudo chmod +x /usr/local/bin/rr-deploy-war",
            ctx.pem, data=wanted.encode())
        say("  (the server had an older deployer script; updated it)")


def test_server_loss(ctx):
    say("\n[5] server-loss: terminating the EC2 instance")
    code, out = ssh(ctx.host, "sudo systemctl start rr-backup.service && echo backup-ok", ctx.pem)
    if "backup-ok" not in out:
        record("server-loss", "terminate the instance", "restore from backup", f"could not make a backup first: {out.strip()}", None, False)
        return
    before = snapshot(ctx.host)
    say(f"  backup done; data before: {before}")
    started = time.time()
    ids = [i["InstanceId"] for i in config.find_instances(ctx.ec2)]
    ctx.ec2.terminate_instances(InstanceIds=ids)
    ctx.ec2.get_waiter("instance_terminated").wait(InstanceIds=ids)
    say(f"  server terminated after {time.time() - started:.0f}s; rebuilding with deploy.py ...")
    run = subprocess.run([sys.executable, os.path.join(HERE, "deploy.py"), "server", "--region", ctx.region],
                         capture_output=True, text=True, cwd=HERE)
    seconds = round(time.time() - started, 1)
    ctx.host = config.find_addresses(ctx.ec2)[0]["PublicIp"]
    after = snapshot(ctx.host)
    ok = run.returncode == 0 and api_ok(ctx.host) == 200 and same_data(before, after)
    record("server-loss", "terminate the EC2 instance (server and disks lost)",
           "deploy.py rebuilds the server, the Elastic IP is reattached and the latest backup restores the data",
           f"deploy.py exit code {run.returncode}; data before {before}, after {after}",
           seconds, ok)


# ------------------------------------------------------------------- report

def merged_results():
    """Keeps results of earlier runs for tests that were not run now (so partial runs add up)."""
    path = os.path.join(HERE, "resilience_report.json")
    old = []
    try:
        with open(path, encoding="utf-8") as handle:
            old = json.load(handle).get("results", [])
    except (OSError, ValueError):
        pass
    fresh = {(r["test"], r["failure"]) for r in RESULTS}
    merged = [r for r in old if (r["test"], r["failure"]) not in fresh] + RESULTS
    order = {name: i for i, name in enumerate(TESTS)}
    merged.sort(key=lambda r: order.get(r["test"], 99))
    return merged


def write_report(ctx):
    stamp = time.strftime("%Y-%m-%d %H:%M")
    results = merged_results()
    with open(os.path.join(HERE, "resilience_report.json"), "w", encoding="utf-8") as handle:
        json.dump({"date": stamp, "region": ctx.region, "results": results}, handle, indent=2)
    lines = [f"# Resilience tests ({stamp}, {ctx.region})", "",
             "| Test | Failure injected | Expected | Observed | Recovery (s) | Result |",
             "|---|---|---|---|---|---|"]
    for r in results:
        seconds = "-" if r["recovery_seconds"] is None else ("no outage" if r["recovery_seconds"] == 0 else r["recovery_seconds"])
        lines.append(f"| {r['test']} | {r['failure']} | {r['expected']} | {r['observed']} | {seconds} | {'PASS' if r['passed'] else 'FAIL'} |")
    with open(os.path.join(HERE, "resilience_report.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


class Context:
    pass


TESTS = {"crash-app": test_crash_app, "crash-db": test_crash_db, "load": test_load, "bad-war": test_bad_war,
         "server-loss": test_server_loss}


def main():
    parser = argparse.ArgumentParser(description="Resilience tests for the Restaurant Review platform")
    parser.add_argument("--region", default=config.DEFAULT_REGION)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--pem", default=os.path.join(HERE, f"{config.KEY_NAME}.pem"))
    parser.add_argument("--only", choices=list(TESTS), help="run just one test")
    parser.add_argument("--include-server-loss", action="store_true", help="also run the destructive server-loss test")
    parser.add_argument("--host", default=None, help="override the server address (testing)")
    args = parser.parse_args()

    session = config.make_session(args.profile, args.region)
    ctx = Context()
    ctx.region, ctx.pem = args.region, args.pem
    ctx.ec2, ctx.s3, ctx.ssm = (session.client(n) for n in ("ec2", "s3", "ssm"))
    ctx.bucket = config.bucket_name(session, args.region)
    addresses = config.find_addresses(ctx.ec2)
    ctx.host = args.host or (addresses[0]["PublicIp"] if addresses else None)
    if not ctx.host:
        raise SystemExit("There is no server. Run: python deploy.py server")
    if not os.path.exists(ctx.pem):
        raise SystemExit(f"The key file was not found: {ctx.pem}")
    if api_ok(ctx.host) != 200:
        raise SystemExit("The API does not answer 200 right now. Check it with: python deploy.py status")
    if ssh(ctx.host, "echo ok", ctx.pem)[1].strip() != "ok":
        raise SystemExit("SSH does not work (did your IP change? run: python deploy.py base)")

    names = [args.only] if args.only else ["crash-app", "crash-db", "load", "bad-war"]
    if args.include_server_loss and not args.only:
        names.append("server-loss")
    say(f"Server {ctx.host}. Tests: {', '.join(names)}")
    for name in names:
        try:
            TESTS[name](ctx)
        except Exception as error:   # keep going and report it
            record(name, "(test crashed)", "-", f"{type(error).__name__}: {error}", None, False)
    write_report(ctx)
    say("\nSummary")
    for r in RESULTS:
        say(f"  {'PASS' if r['passed'] else 'FAIL'}  {r['test']}")
    say("\nReport: resilience_report.md and resilience_report.json")


if __name__ == "__main__":
    main()
