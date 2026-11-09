#!/usr/bin/env python3
"""Fetch and filter the comments section of a YouTube video.

The video has ~140K comments. `fetch` MERGES into comments.json (deduped by
comment id), so repeated runs accumulate rather than overwrite. There is no
resume: yt-dlp keeps continuation tokens in memory only, so an interrupted
run restarts from page 1 -- but Ctrl-C keeps whatever it already collected.

yt-dlp's default sort is NEWEST (not top). 'new' paginates deep -- ~85K on
this video; 'top' walls at ~2.2K. Prefer 'new'.

Examples:
    ./tools/comments.py fetch --max 0 --sort new --replies 0
    ./tools/comments.py import "Guess the Code, Win $1000 [4TQ01xXbRWA].info.json"
    ./tools/comments.py solo --start p --top 60    # valid one-word guesses, ranked
    ./tools/comments.py word python                # has this been guessed?
    ./tools/comments.py grep "first letter"        # full-text search
    ./tools/comments.py watch                      # cheap poll for a pinned winner
    ./tools/comments.py stats
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STORE = os.path.join(ROOT, "comments.json")
VIDEO = "https://www.youtube.com/watch?v=4TQ01xXbRWA"


def load(path=STORE):
    if not os.path.exists(path):
        sys.exit(f"no {path} yet -- run: ./tools/comments.py fetch --max 5000")
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob.get("comments", []) if isinstance(blob, dict) else blob


def cmd_fetch(args):
    """Fetch comments and MERGE into comments.json (deduped by comment id).

    YouTube caps how deep either sort will paginate -- 'top' stalls at roughly
    2.2K on this video. Neither sort alone reaches 140K, but they return
    different slices, so running both and merging beats either one.
    """
    # max_comments syntax: total, max-parents, max-replies, max-replies-per-thread
    total = "all" if args.max == 0 else str(args.max)
    ea = f"youtube:comment_sort={args.sort};max_comments={total},all,all,{args.replies}"
    out = os.path.join(ROOT, "_raw")
    cmd = [
        "yt-dlp", "--skip-download", "--write-comments",
        "--extractor-args", ea, "-o", out, args.url,
    ]
    print("running:", " ".join(cmd))
    print("(ctrl-C is safe -- whatever was fetched still gets merged)\n")

    # Stream yt-dlp's output through so progress stays visible, while sniffing
    # the true comment total out of it. yt-dlp overwrites meta['comment_count']
    # with the number it actually extracted, so that field cannot be trusted.
    reported = None
    pat = re.compile(r"/~(\d+)\)")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, errors="replace")
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            m = pat.search(line)
            if m:
                reported = int(m.group(1))
    except KeyboardInterrupt:
        proc.terminate()
    proc.wait()

    raw = out + ".info.json"
    if not os.path.exists(raw):
        sys.exit("yt-dlp produced no metadata file")
    with open(raw, encoding="utf-8") as fh:
        meta = json.load(fh)
    fetched = meta.get("comments") or []
    os.remove(raw)

    n_existing, n_merged = merge_into_store(fetched, meta, reported, args.replace)
    print(f"\nthis run fetched : {len(fetched)} (sort={args.sort})")
    print(f"new to the file  : {n_merged - n_existing}")
    print(f"total stored     : {n_merged}"
          + (f" of ~{reported} reported" if reported else ""))
    print(f"-> {STORE}")
    if reported and n_merged < reported * 0.5:
        other = "new" if args.sort == "top" else "top"
        print(f"\nYouTube stops paginating well short of the full thread. Run the other"
              f"\nsort to pick up a different slice -- results merge, they don't overwrite:"
              f"\n    ./tools/comments.py fetch --max 0 --sort {other}")


def merge_into_store(fetched, meta, reported=None, replace=False):
    """Dedupe `fetched` into comments.json. Returns (count_before, count_after)."""
    existing = []
    if os.path.exists(STORE) and not replace:
        with open(STORE, encoding="utf-8") as fh:
            blob = json.load(fh)
        existing = blob.get("comments", []) if isinstance(blob, dict) else blob
        if reported is None:
            reported = blob.get("comment_count_reported") if isinstance(blob, dict) else None

    merged, seen = [], set()
    for c in existing + fetched:
        cid = c.get("id") or (c.get("author"), c.get("text"), c.get("timestamp"))
        seen_key = cid if isinstance(cid, str) else repr(cid)
        if seen_key in seen:
            continue
        seen.add(seen_key)
        merged.append(c)

    payload = {
        "video_id": meta.get("id"),
        "title": meta.get("title"),
        "comment_count_reported": reported,
        "comments_fetched": len(merged),
        "comments": merged,
    }
    with open(STORE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return len(existing), len(merged)


def cmd_import(args):
    """Merge an .info.json produced by a manual yt-dlp run into comments.json."""
    with open(args.path, encoding="utf-8") as fh:
        meta = json.load(fh)
    fetched = meta.get("comments")
    if not fetched:
        sys.exit(f"{args.path} contains no comments "
                 f"(was --write-comments / --get-comments passed?)")
    before, after = merge_into_store(fetched, meta, None, args.replace)
    print(f"file contained  : {len(fetched)} comments")
    print(f"new to the store: {after - before}")
    print(f"total stored    : {after}")
    print(f"-> {STORE}")


def solo_counter(comments):
    """Only single-word comments count as valid guesses per the video's rules."""
    c = collections.Counter()
    for x in comments:
        text = (x.get("text") or "").strip()
        flat = re.sub(r"[^A-Za-z]", "", text)
        if text and len(text.split()) == 1 and flat.isalpha():
            c[flat.lower()] += 1
    return c


def mention_counter(comments):
    c = collections.Counter()
    for x in comments:
        for tok in re.findall(r"\b[a-zA-Z]{2,15}\b", x.get("text") or ""):
            c[tok.lower()] += 1
    return c


def cmd_solo(args):
    comments = load()
    counts = solo_counter(comments)
    rows = [(w, n) for w, n in counts.items() if w.startswith(args.start.lower())]
    rows.sort(key=lambda r: (-r[1], r[0]))
    if args.top:
        rows = rows[: args.top]
    print(f"{'count':>6}  word")
    for w, n in rows:
        print(f"{n:>6}  {w}")
    print(f"\n{len(rows)} distinct one-word guesses"
          + (f" starting with '{args.start}'" if args.start else ""))


def cmd_word(args):
    comments = load()
    w = args.word.lower()
    solo = solo_counter(comments)[w]
    seen = mention_counter(comments)[w]
    total = len(comments)
    print(f"word: {w}")
    print(f"  submitted as a valid one-word comment : {solo}")
    print(f"  appears anywhere in any comment       : {seen}")
    print(f"  sample size                           : {total} comments")
    if solo:
        print(f"\n  ALREADY GUESSED -- and this is only a sample of ~140K comments,")
        print(f"  so the real figure is roughly {solo * 140000 // max(total,1)}x across the whole thread.")
    else:
        print("\n  not guessed solo in this sample (but the sample is partial)")


def cmd_grep(args):
    comments = load()
    pat = re.compile(args.pattern, 0 if args.case else re.I)
    hits = 0
    for x in comments:
        text = (x.get("text") or "")
        if pat.search(text):
            hits += 1
            who = x.get("author", "?")
            likes = x.get("like_count") or 0
            flags = []
            if x.get("is_pinned"):
                flags.append("PINNED")
            if x.get("author_is_uploader"):
                flags.append("UPLOADER")
            tag = (" [" + ",".join(flags) + "]") if flags else ""
            print(f"[{likes:>5} likes] {who}{tag}: {text.replace(chr(10), ' / ')[:300]}")
            if args.top and hits >= args.top:
                break
    print(f"\n{hits} matching comments")


def cmd_authors(args):
    comments = load()
    for x in comments:
        if args.uploader and not (x.get("author_is_uploader") or x.get("is_pinned")):
            continue
        flags = []
        if x.get("is_pinned"):
            flags.append("PINNED")
        if x.get("author_is_uploader"):
            flags.append("UPLOADER")
        if not flags and args.uploader:
            continue
        print(f"[{','.join(flags) or '-'}] {x.get('author')}: "
              f"{(x.get('text') or '').replace(chr(10), ' / ')[:300]}")
    if args.uploader:
        n = sum(1 for x in comments if x.get("is_pinned") or x.get("author_is_uploader"))
        print(f"\n{n} pinned/uploader comments found"
              + ("  <- a pinned winner would show up here" if n == 0 else ""))


def cmd_watch(args):
    """Cheap poll for a pinned winner -- pinned comments sort to the top.

    Costs one small request, unlike a full fetch. Exit code 0 = pin found,
    1 = nothing yet, so it composes with cron/shell loops.
    """
    ea = "youtube:comment_sort=top;max_comments=30,all,0,0"
    cmd = ["yt-dlp", "--skip-download", "--write-comments",
           "--extractor-args", ea, "-o", os.path.join(ROOT, "_watch"), args.url]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    raw = os.path.join(ROOT, "_watch.info.json")
    if not os.path.exists(raw):
        print("fetch failed"); return 2
    with open(raw, encoding="utf-8") as fh:
        meta = json.load(fh)
    os.remove(raw)
    hits = [c for c in (meta.get("comments") or [])
            if c.get("is_pinned") or c.get("author_is_uploader")]
    stamp = __import__("time").strftime("%Y-%m-%d %H:%M")
    if hits:
        print(f"[{stamp}] *** PIN / CREATOR COMMENT FOUND ***")
        for c in hits:
            flags = []
            if c.get("is_pinned"):
                flags.append("PINNED")
            if c.get("author_is_uploader"):
                flags.append("UPLOADER")
            print(f"  [{','.join(flags)}] {c.get('author')}: "
                  f"{(c.get('text') or '').replace(chr(10), ' / ')[:400]}")
        return 0
    print(f"[{stamp}] no pinned winner yet")
    return 1


def cmd_stats(args):
    comments = load()
    solo = solo_counter(comments)
    print(f"comments in file      : {len(comments)}")
    print(f"distinct one-word     : {len(solo)}")
    print(f"one-word comments     : {sum(solo.values())}")
    pinned = sum(1 for x in comments if x.get("is_pinned"))
    uploader = sum(1 for x in comments if x.get("author_is_uploader"))
    print(f"pinned comments       : {pinned}")
    print(f"uploader comments     : {uploader}")
    p = {w: n for w, n in solo.items() if w.startswith("p")}
    print(f"distinct P one-word   : {len(p)}")
    print(f"top P guesses         : " + ", ".join(
        f"{w}({n})" for w, n in sorted(p.items(), key=lambda r: -r[1])[:12]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download comments via yt-dlp (merges by default)")
    f.add_argument("--max", type=int, default=5000, help="0 = as deep as YouTube allows")
    f.add_argument("--replies", type=int, default=20,
                   help="replies per thread (0 = top-level only, much faster)")
    f.add_argument("--sort", choices=["top", "new"], default="top")
    f.add_argument("--replace", action="store_true",
                   help="overwrite comments.json instead of merging into it")
    f.add_argument("--url", default=VIDEO)
    f.set_defaults(func=cmd_fetch)

    i = sub.add_parser("import", help="merge an .info.json from a manual yt-dlp run")
    i.add_argument("path")
    i.add_argument("--replace", action="store_true")
    i.set_defaults(func=cmd_import)

    s = sub.add_parser("solo", help="valid one-word guesses, ranked")
    s.add_argument("--start", default="", help="filter by first letter")
    s.add_argument("--top", type=int, default=0)
    s.set_defaults(func=cmd_solo)

    w = sub.add_parser("word", help="check one word")
    w.add_argument("word")
    w.set_defaults(func=cmd_word)

    g = sub.add_parser("grep", help="full-text search")
    g.add_argument("pattern")
    g.add_argument("--case", action="store_true")
    g.add_argument("--top", type=int, default=40)
    g.set_defaults(func=cmd_grep)

    a = sub.add_parser("authors", help="pinned / uploader comments")
    a.add_argument("--uploader", action="store_true")
    a.set_defaults(func=cmd_authors)

    wt = sub.add_parser("watch", help="cheap poll for a pinned winner")
    wt.add_argument("--url", default=VIDEO)
    wt.set_defaults(func=cmd_watch)

    st = sub.add_parser("stats", help="summary")
    st.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    rc = args.func(args)
    sys.exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    main()
