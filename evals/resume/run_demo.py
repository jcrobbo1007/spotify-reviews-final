"""Interruption/resume demo for the 10,000 stage (CLAUDE.md "Interruption / resume evidence").

1. start `python -m pipeline run --paid --scope 10000` (one worker, 50 requests per wave)
2. after 2 waves are committed and a 3rd batch is submitted (in flight), hard-kill the process
3. restart the identical command; on restart the pipeline writes checkpoint_before.json,
   reconciles the in-flight batch (no resubmission), then submits the remaining work as phase=resume
4. checkpoint_after.json is written when the stage finishes

Everything printed by both processes, plus this driver's own lines, goes to evals/resume/terminal.log.
No screen recorder is available in this environment, so this log is the recording.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "evals" / "resume" / "terminal.log"
CMD = [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-u", "-m", "pipeline", "run", "--paid", "--scope", "10000",
       "--stages", "enrich", "--requests-per-wave", "50"]


def calls_count():
    p = ROOT / "outputs" / "calls.jsonl"
    return sum(1 for _ in open(p, encoding="utf-8")) if p.exists() else 0


def say(f, msg):
    line = f"[demo {time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    f.write(line + "\n")
    f.flush()


def stream(proc, f, kill_after=None):
    committed = submitted = 0
    for line in proc.stdout:
        f.write(line)
        f.flush()
        print(line, end="", flush=True)
        if "batch_committed" in line:
            committed += 1
        if "batch_submitted" in line:
            submitted += 1
            if kill_after and committed >= kill_after and submitted > committed:
                say(f, f"wave {submitted} submitted and in flight after {committed} committed waves -> killing PID {proc.pid}")
                proc.kill()  # TerminateProcess: abrupt, no cleanup handlers
                proc.wait()
                say(f, f"process killed, exit code {proc.returncode}")
                return "killed"
    proc.wait()
    return proc.returncode


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
    with open(LOG, "a", encoding="utf-8") as f:
        say(f, "$ " + " ".join(CMD[2:]))
        say(f, f"calls.jsonl lines before start: {calls_count()}")
        p = subprocess.Popen(CMD, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", env=env)
        r = stream(p, f, kill_after=2)
        if r != "killed":
            say(f, f"run ended before the kill point (returncode {r}); no interruption happened")
            return 1
        n_kill = calls_count()
        say(f, f"calls.jsonl lines at kill: {n_kill}")
        time.sleep(5)
        say(f, "restarting the identical command")
        say(f, "$ " + " ".join(CMD[2:]))
        p = subprocess.Popen(CMD, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", env=env)
        r = stream(p, f)
        say(f, f"resumed run exited with {r}; calls.jsonl lines now: {calls_count()}")
        before = json.loads((ROOT / "outputs" / "checkpoint_before.json").read_text(encoding="utf-8"))["completed_ids"]
        after_p = ROOT / "outputs" / "checkpoint_after.json"
        after = json.loads(after_p.read_text(encoding="utf-8"))["completed_ids"] if after_p.exists() else []
        say(f, f"checkpoint_before: {len(before)} completed IDs; checkpoint_after: {len(after)}; "
               f"before is subset of after: {set(before) <= set(after)}")
        # No completed ID was sent again after the restart.
        resent = 0
        for line in open(ROOT / "outputs" / "calls.jsonl", encoding="utf-8"):
            c = json.loads(line)
            if c.get("role") == "enrich" and c.get("phase") == "resume":
                resent += len(set(c["review_ids"]) & set(before))
        say(f, f"checkpoint_before IDs sent again in phase=resume calls: {resent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
