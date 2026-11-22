#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push_via_api.py — 当本机到 github.com:443 被阻断（DNS 污染）时，用 GitHub Git Data API 推送。

前提：gh 已登录（读 gh auth token），api.github.com 可达。
用法：python build-chain/tools/push_via_api.py（仓库内任意目录）
行为：把本地 HEAD 相对 .git/remote_main_sha 记录的本地基点之间的提交逐个重放为远端提交
      （blob -> tree -> commit），最后 PATCH refs/heads/main；随后把远端 sha 与本地 HEAD 写回
      .git/remote_main_sha（格式：<remote_sha> <local_sha>）。
注意：github.com 恢复后直接 git push 即可；若远端已领先（force=False 会报 422），先人工核对。
"""
import base64, json, os, ssl, subprocess, sys, time, urllib.request

REPO = "awadmw/senna-b-port"
BRANCH = "main"
TOKEN = subprocess.check_output(["gh", "auth", "token"]).decode().strip()
TOP = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip()
SHAFILE = os.path.join(TOP, ".git", "remote_main_sha")

def api(method, path, body=None):
    url = "https://api.github.com" + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "senna-push")
    if data:
        req.add_header("Content-Type", "application/json")
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            print("HTTP", e.code, path, e.read().decode()[:500])
            raise
        except (urllib.error.URLError, ssl.SSLError, TimeoutError) as e:
            last = e
            print("  retry %d: %s" % (attempt + 1, e))
            time.sleep(2 + attempt * 3)
    raise last

def git(*args, binary=False):
    out = subprocess.check_output(["git"] + list(args), cwd=TOP)
    return out if binary else out.decode("utf-8", "replace").strip()

remote = local_base = None
if os.path.exists(SHAFILE):
    parts = open(SHAFILE).read().split()
    if parts:
        remote = parts[0]
    if len(parts) > 1:
        local_base = parts[1]
if not remote:
    remote = api("GET", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH))["object"]["sha"]
head = git("rev-parse", "HEAD")
base_local = local_base or remote
if head == base_local:
    print("up-to-date local", base_local[:12], "remote", remote[:12])
    sys.exit(0)

commits = git("rev-list", "--reverse", base_local + ".." + head).split()
print("pushing", len(commits), "commit(s); remote base", remote[:12], "local base", base_local[:12])
cur_remote = remote
cur_tree = api("GET", "/repos/%s/git/commits/%s" % (REPO, remote))["tree"]["sha"]
for c in commits:
    msg = git("log", "-1", "--format=%B", c)
    parent = git("rev-parse", c + "^").strip()
    changed = [l.split("\t") for l in git("diff", "--name-status", parent, c).splitlines() if l]
    entries = []
    for parts in changed:
        st, path = parts[0], parts[-1]
        if st.startswith("D"):
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            print("  delete", path)
            continue
        content = git("show", c + ":" + path, binary=True)
        blob = api("POST", "/repos/%s/git/blobs" % REPO,
                   {"content": base64.b64encode(content).decode(), "encoding": "base64"})
        mode = subprocess.check_output(["git", "ls-tree", c, "--", path], cwd=TOP).decode().split()[0]
        entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        print("  blob", path, len(content))
    cur_tree = api("POST", "/repos/%s/git/trees" % REPO, {"base_tree": cur_tree, "tree": entries})["sha"]
    commit = api("POST", "/repos/%s/git/commits" % REPO,
                 {"message": msg, "tree": cur_tree, "parents": [cur_remote]})
    cur_remote = commit["sha"]
    print("  commit", cur_remote[:12], msg.splitlines()[0])

api("PATCH", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH), {"sha": cur_remote, "force": False})
open(SHAFILE, "w").write(cur_remote + " " + head)
print("main ->", cur_remote)
