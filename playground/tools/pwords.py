#!/usr/bin/env python3
"""Find candidate words by first letter, length, and syllable count.

Syllables come from CMUdict (real pronunciations, not a heuristic).
Definitions and the "is this a real word" filter come from WordNet.

Examples:
    ./tools/pwords.py                              # P, <=10 letters, <=3 syllables
    ./tools/pwords.py --defs                       # same, with definitions
    ./tools/pwords.py --pos noun --defs            # nouns only
    ./tools/pwords.py --guessed comments.json      # annotate with guess counts
    ./tools/pwords.py --guessed comments.json --hide-guessed
    ./tools/pwords.py --start f --max-syllables 2  # last year's rumoured "F" word
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
CMUDICT = os.path.join(DATA, "cmudict.dict")
WORDNET = os.path.join(DATA, "wordnet")

POS_FILES = {"noun": "data.noun", "verb": "data.verb", "adj": "data.adj", "adv": "data.adv"}


def load_syllables():
    """word -> syllable count, from CMUdict vowel phonemes (those carry a stress digit)."""
    if not os.path.exists(CMUDICT):
        sys.exit(f"missing {CMUDICT} -- run tools/setup.sh")
    syl = {}
    with open(CMUDICT, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = line.split()
            word = re.sub(r"\(\d+\)$", "", parts[0]).lower()  # drop (2) variants
            n = sum(1 for p in parts[1:] if p[-1].isdigit())
            if n and (word not in syl or n < syl[word]):
                syl[word] = n
    return syl


def load_wordnet():
    """word -> list of (pos, gloss). Single words only, no multi-word phrases."""
    if not os.path.isdir(WORDNET):
        sys.exit(f"missing {WORDNET} -- run tools/setup.sh")
    defs = {}
    for pos, fname in POS_FILES.items():
        path = os.path.join(WORDNET, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("  "):  # licence header
                    continue
                head, _, gloss = line.partition("|")
                fields = head.split()
                if len(fields) < 5:
                    continue
                try:
                    w_cnt = int(fields[3], 16)
                except ValueError:
                    continue
                gloss = gloss.strip().split(";")[0].strip().strip('"')
                for i in range(w_cnt):
                    idx = 4 + i * 2
                    if idx >= len(fields):
                        break
                    word = fields[idx].lower()
                    if "_" in word or not word.isalpha():
                        continue
                    defs.setdefault(word, [])
                    if len(defs[word]) < 4:
                        defs[word].append((pos, gloss))
    return defs


def load_guessed(path):
    """Read comments.json -> (solo Counter, mention Counter)."""
    import collections

    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    comments = blob.get("comments", blob) if isinstance(blob, dict) else blob
    solo, mention = collections.Counter(), collections.Counter()
    for c in comments:
        text = (c.get("text") or "").strip()
        if not text:
            continue
        flat = re.sub(r"[^A-Za-z]", "", text)
        if len(text.split()) == 1 and flat.isalpha():
            solo[flat.lower()] += 1
        for tok in re.findall(r"\b[a-zA-Z]{2,15}\b", text):
            mention[tok.lower()] += 1
    return solo, mention


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="p", help="required first letter(s) (default: p)")
    ap.add_argument("--max-letters", type=int, default=10)
    ap.add_argument("--min-letters", type=int, default=3)
    ap.add_argument("--max-syllables", type=int, default=3)
    ap.add_argument("--min-syllables", type=int, default=1)
    ap.add_argument("--pos", help="comma-separated: noun,verb,adj,adv")
    ap.add_argument("--defs", action="store_true", help="show definitions")
    ap.add_argument("--any-word", action="store_true",
                    help="don't require a WordNet entry (noisier, includes proper nouns)")
    ap.add_argument("--guessed", metavar="comments.json", help="annotate with guess counts")
    ap.add_argument("--hide-guessed", action="store_true", help="drop words already guessed solo")
    ap.add_argument("--sort", choices=["alpha", "len", "syl", "guessed"], default="alpha")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    syl = load_syllables()
    wn = load_wordnet()
    want_pos = set(args.pos.split(",")) if args.pos else None

    solo = mention = None
    if args.guessed:
        solo, mention = load_guessed(args.guessed)

    prefix = args.start.lower()
    rows = []
    for word, n in syl.items():
        if not word.isalpha() or not word.startswith(prefix):
            continue
        if not (args.min_letters <= len(word) <= args.max_letters):
            continue
        if not (args.min_syllables <= n <= args.max_syllables):
            continue
        entries = wn.get(word)
        if not args.any_word and not entries:
            continue
        if want_pos and not any(p in want_pos for p, _ in (entries or [])):
            continue
        s = solo.get(word, 0) if solo is not None else 0
        m = mention.get(word, 0) if mention is not None else 0
        if args.hide_guessed and s > 0:
            continue
        rows.append((word, len(word), n, entries or [], s, m))

    keys = {
        "alpha": lambda r: r[0],
        "len": lambda r: (r[1], r[0]),
        "syl": lambda r: (r[2], r[0]),
        "guessed": lambda r: (-r[4], -r[5], r[0]),
    }
    rows.sort(key=keys[args.sort])
    if args.limit:
        rows = rows[: args.limit]

    hdr = f"{'word':<14}{'len':>4}{'syl':>4}"
    if solo is not None:
        hdr += f"{'solo':>6}{'seen':>6}"
    if args.defs:
        hdr += "  definition"
    print(hdr)
    print("-" * len(hdr))
    for word, L, n, entries, s, m in rows:
        line = f"{word:<14}{L:>4}{n:>4}"
        if solo is not None:
            line += f"{s:>6}{m:>6}"
        if args.defs:
            if entries:
                pos, gloss = entries[0]
                line += f"  ({pos}) {gloss[:88]}"
            else:
                line += "  -"
        print(line)
    print(f"\n{len(rows)} words")


if __name__ == "__main__":
    main()
