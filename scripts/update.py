#!/usr/bin/env python3
"""Poll the Short's comments: detect a winner, and grow the guessed-word list.

Designed to run repeatedly (CI cron or local launchd). State lives in data/ and
is small enough to commit:

    data/guessed.json    word -> times submitted as a one-word comment
    data/seen_ids.txt.gz comment ids already counted (dedupe across runs)
    data/meta.json       coverage stats
    WINNER.md            written only if a pin/creator comment shows up

Raw comments are never stored -- only derived counts -- so the repo stays small.
"""
import gzip
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
GUESSED = os.path.join(DATA, "guessed.json")
SEEN = os.path.join(DATA, "seen_ids.txt.gz")
META = os.path.join(DATA, "meta.json")
WINNER = os.path.join(ROOT, "WINNER.md")

VIDEO = os.environ.get("VIDEO_URL", "https://www.youtube.com/watch?v=4TQ01xXbRWA")
SECRET = os.environ.get("SECRET_URL", "https://www.youtube.com/watch?v=E0UO6lLU23Q")


def run_ytdlp(url, max_comments, sort="new", replies=0):
    """Return the comments list, or None if extraction failed."""
    out = os.path.join(DATA, "_tmp")
    ea = f"youtube:comment_sort={sort};max_comments={max_comments},all,all,{replies}"
    cmd = ["yt-dlp", "--skip-download", "--write-comments",
           "--extractor-args", ea, "--no-warnings", "-o", out, url]
    cookies = os.environ.get("YT_COOKIES_FILE")
    if cookies and os.path.exists(cookies):
        cmd[1:1] = ["--cookies", cookies]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    raw = out + ".info.json"
    if not os.path.exists(raw):
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        return None
    with open(raw, encoding="utf-8") as fh:
        meta = json.load(fh)
    os.remove(raw)
    return meta.get("comments") or []


def load_seen():
    if not os.path.exists(SEEN):
        return set()
    with gzip.open(SEEN, "rt", encoding="utf-8") as fh:
        return {line.strip() for line in fh if line.strip()}


def save_seen(ids):
    with gzip.open(SEEN, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(ids)))


def load_guessed():
    if not os.path.exists(GUESSED):
        return {}
    with open(GUESSED, encoding="utf-8") as fh:
        return json.load(fh)


def check_winner(comments, source):
    hits = [c for c in comments
            if c.get("is_pinned") or c.get("author_is_uploader")]
    if not hits:
        return False
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    lines = [f"# Winner / creator activity detected\n",
             f"Found {stamp} on **{source}**.\n"]
    for c in hits:
        flags = []
        if c.get("is_pinned"):
            flags.append("PINNED")
        if c.get("author_is_uploader"):
            flags.append("UPLOADER")
        lines.append(f"- **[{', '.join(flags)}] {c.get('author')}** "
                     f"({c.get('like_count')} likes)\n\n"
                     f"  > {(c.get('text') or '').strip()}\n")
    with open(WINNER, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("::warning::WINNER OR CREATOR COMMENT DETECTED -- see WINNER.md")
    for line in lines:
        print(line)
    return True


def main():
    os.makedirs(DATA, exist_ok=True)
    budget = int(os.environ.get("MAX_COMMENTS", "4000"))

    # 1. Cheap winner check first: pinned comments sort to the top.
    found = False
    for url, name in ((VIDEO, "main Short"), (SECRET, "Secret video")):
        top = run_ytdlp(url, 30, sort="top")
        if top is None:
            print(f"warning: could not reach {name}")
            continue
        if check_winner(top, name):
            found = True

    # 2. Deep-ish pull on the newest comments to grow coverage.
    fresh = run_ytdlp(VIDEO, budget, sort="new")
    if fresh is None:
        # Expected on GitHub-hosted runners: YouTube blocks datacenter IPs.
        # That is a tick with no new data, not a failure -- exit 0 so the run
        # stays green and the schedule keeps firing.
        print("::notice::comment fetch blocked this tick "
              "(YouTube rate-limits datacenter IPs); no new data")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("### Poll skipped\n\nYouTube blocked this runner's IP. "
                         "The winner check still ran. See the README for the "
                         "cookies / self-hosted / local options.\n")
        return 0

    if check_winner(fresh, "main Short"):
        found = True

    seen = load_seen()
    guessed = load_guessed()
    new_ids, new_words = 0, 0
    for c in fresh:
        cid = c.get("id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        new_ids += 1
        text = (c.get("text") or "").strip()
        flat = re.sub(r"[^A-Za-z]", "", text)
        if text and len(text.split()) == 1 and flat.isalpha():
            w = flat.lower()
            if w not in guessed:
                new_words += 1
            guessed[w] = guessed.get(w, 0) + 1

    save_seen(seen)
    with open(GUESSED, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(guessed.items(), key=lambda kv: (-kv[1], kv[0]))),
                  fh, indent=0)

    meta = {
        "last_run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "comments_seen": len(seen),
        "distinct_guessed_words": len(guessed),
        "distinct_p_words": sum(1 for w in guessed if w.startswith("p")),
        "winner_found": found or os.path.exists(WINNER),
    }
    with open(META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"new comments counted : {new_ids}")
    print(f"new distinct words   : {new_words}")
    print(f"total comments seen  : {len(seen)}")
    print(f"distinct words       : {len(guessed)} ({meta['distinct_p_words']} start with p)")
    print(f"winner found         : {meta['winner_found']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
