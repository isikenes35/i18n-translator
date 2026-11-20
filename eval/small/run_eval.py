"""A/B test: no skill vs this skill. Two separate agent sessions per run (no shared memory)."""
import json, os, shutil, subprocess, sys, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SKILL = os.path.dirname(os.path.dirname(HERE))
AGY = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")
# Uses the Antigravity CLI (agy). Usage: py -3 run_eval.py <model> <N> [noskill,skill]
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-4-hydrogen-medium"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 3
SKILLS = {"noskill": None, "skill": SKILL}

P1 = ("This is a React app that uses i18next. The Russian translation is incomplete. "
      "Complete locales/ru/common.json so the Russian UI has every string from locales/en/common.json. Edit the files in this folder directly.")
P2 = ("This is a React app that uses i18next. Add Russian for the new feature strings: create locales/ru/features.json "
      "from locales/en/features.json. Edit the files in this folder directly.")

def agent(cwd, prompt, skill):
    if skill:
        prompt = f"Before you start, read the agent skill at {skill}/SKILL.md (and any files it points to) and follow it.\n\n" + prompt
    cmd = [AGY, "--model", MODEL, "--mode", "auto", "--output-format", "json", "-p", prompt]
    if skill:
        cmd[1:1] = ["--add-dir", skill]
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=1500)
    return p.returncode

def one(job):
    cond, i = job
    run = f"{HERE}/runs/{MODEL}/{cond}-{i}"
    if os.path.exists(run):
        shutil.rmtree(run)
    shutil.copytree(HERE + "/fixture", run, ignore=shutil.ignore_patterns(".git"))
    a = agent(run, P1, SKILLS[cond])
    b = agent(run, P2, SKILLS[cond])
    return cond, i, a, b

CONDS = sys.argv[3].split(",") if len(sys.argv) > 3 else list(SKILLS)
jobs = [(c, i) for i in range(1, N + 1) for c in CONDS]
with cf.ThreadPoolExecutor(6) as ex:
    for res in ex.map(one, jobs):
        print(res, flush=True)
