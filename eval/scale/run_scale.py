import os, shutil, subprocess, sys, concurrent.futures as cf
# Uses the Antigravity CLI (agy). Usage: py -3 make_fixture.py && py -3 run_scale.py <model> <N>
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SKILL = os.path.dirname(os.path.dirname(HERE))
AGY = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")
MODEL, N = sys.argv[1], int(sys.argv[2])
SK = {"noskill": None, "skill": SKILL}
P = ["This is a React app that uses i18next. Russian support is being added file by file. In this session: complete locales/ru/common.json and create locales/ru/workspaces.json from the English files. Edit the files in this folder directly.",
     "This is a React app that uses i18next. Russian support is being added file by file. In this session: create locales/ru/boards.json and locales/ru/tickets.json from the English files. Edit the files in this folder directly.",
     "This is a React app that uses i18next. Russian support is being added file by file. In this session: create locales/ru/reports.json and locales/ru/settings.json from the English files. Edit the files in this folder directly."]
def agent(cwd, prompt, skill):
    cmd = [AGY, "--model", MODEL, "--mode", "auto", "--output-format", "json", "-p",
           (f"Before you start, read the agent skill at {skill}/SKILL.md (and any files it points to) and follow it.\n\n" if skill else "") + prompt]
    if skill: cmd[1:1] = ["--add-dir", skill]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=1800).returncode
def one(job):
    c, i = job; run = f"{HERE}/runs/{MODEL}/{c}-{i}"
    shutil.rmtree(run, ignore_errors=True); shutil.copytree(HERE + "/fixture", run)
    return c, i, [agent(run, p, SK[c]) for p in P]
with cf.ThreadPoolExecutor(4) as ex:
    for res in ex.map(one, [(c, i) for i in range(1, N + 1) for c in SK]): print(res, flush=True)
