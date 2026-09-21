#!/usr/bin/env python3
"""Rebuild the ranked candidate list: pronounceable P-words nobody has guessed.

Constraints are exact (CMUdict pronunciations, not a syllable heuristic):
    starts with p, <= 10 letters, <= 3 syllables

Ranking is a transparent heuristic, not a model. The dominant term is corpus
frequency, because the creator said he wants someone to win this year -- which
argues for an ordinary word over an obscure one.

Outputs data/candidates.tsv (all of them, scored) and STATUS.md (human summary).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CMUDICT = os.path.join(DATA, "cmudict.dict")
GUESSED = os.path.join(DATA, "guessed.json")
META = os.path.join(DATA, "meta.json")
OUT = os.path.join(DATA, "candidates.tsv")
STATUS = os.path.join(ROOT, "STATUS.md")

MAX_LETTERS = 10
MAX_SYLLABLES = 3

# Words tied to the video's own subject matter; a self-referential pick is
# plausible for this creator, so nudge them up.
THEMATIC = {
    "prize", "puzzle", "prompt", "pixel", "premium", "preview", "playlist",
    "plugin", "popup", "patch", "proxy", "packet", "print", "post", "profile",
    "public", "private", "portal", "player", "paste", "phone", "purple",
    "pinning", "prank", "payout", "payday", "payment", "puzzler", "plot",
}

# YouTube auto-holds comments containing these for review, so a winning comment
# could never be reliably detected or pinned -- the creator would not pick one.
VULGAR = {
    "porn", "porno", "pussy", "pussycat", "piss", "pissing", "penis", "prick",
    "puke", "puking", "pee", "peeing", "poop", "pooping", "pube", "pubes",
    "prostitute", "pimp", "perv", "pervert", "phallus", "pus", "puss",
}


def load_wordnet_signal():
    """word -> (pos string, is_proper_noun_only). Generated from WordNet 3.1."""
    path = os.path.join(DATA, "wordnet_p.tsv")
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3:
                out[parts[0]] = (parts[1], parts[2] == "1")
    return out


def load_syllables():
    syl = {}
    with open(CMUDICT, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = line.split()
            word = re.sub(r"\(\d+\)$", "", parts[0]).lower()
            n = sum(1 for p in parts[1:] if p[-1].isdigit())
            if n and (word not in syl or n < syl[word]):
                syl[word] = n
    return syl


def looks_inflected(word, vocab):
    """Plurals and -ing/-ed forms make unsatisfying 'secret words'."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        if word[:-1] in vocab or (word.endswith("es") and word[:-2] in vocab):
            return True
    for suf in ("ing", "ed", "er", "ly"):
        if len(word) > len(suf) + 2 and word.endswith(suf):
            stem = word[: -len(suf)]
            if stem in vocab or stem + "e" in vocab:
                return True
    return False


def main():
    if not os.path.exists(CMUDICT):
        sys.exit("missing data/cmudict.dict -- it is committed to the repo; "
                 "restore it with: git checkout data/cmudict.dict")
    syl = load_syllables()
    vocab = set(syl)
    wn = load_wordnet_signal()

    guessed = {}
    if os.path.exists(GUESSED):
        with open(GUESSED, encoding="utf-8") as fh:
            guessed = json.load(fh)

    try:
        from wordfreq import zipf_frequency
    except ImportError:
        sys.exit("pip install wordfreq")

    rows = []
    for word, n in syl.items():
        if not word.isalpha() or not word.startswith("p"):
            continue
        if len(word) > MAX_LETTERS or n > MAX_SYLLABLES:
            continue
        if word in guessed:
            continue

        z = zipf_frequency(word, "en")
        score = z
        note = []

        entry = wn.get(word)
        if entry is None:
            # In CMUdict but absent from WordNet: overwhelmingly surnames and
            # place names (pete, pierre, powell, peterson).
            score -= 2.5
            note.append("not-in-dict")
        else:
            pos, proper = entry
            score += 1.0
            if proper:
                score -= 3.0
                note.append("proper-noun")
            elif "n" in pos:
                score += 0.4  # concrete nouns make the most satisfying answers

        if word in VULGAR:
            score -= 5.0
            note.append("vulgar")
        if 4 <= len(word) <= 8:
            score += 0.3
        if word in THEMATIC:
            score += 0.6
            note.append("thematic")
        if looks_inflected(word, vocab):
            score -= 1.5
            note.append("inflected")
        if len(word) <= 2:
            score -= 1.5

        rows.append((round(score, 3), word, len(word), n, round(z, 2),
                     ",".join(note) or "-"))

    rows.sort(key=lambda r: (-r[0], r[1]))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("rank\tscore\tword\tletters\tsyllables\tzipf\tflags\n")
        for i, (s, w, L, n, z, fl) in enumerate(rows, 1):
            fh.write(f"{i}\t{s}\t{w}\t{L}\t{n}\t{z}\t{fl}\n")

    meta = {}
    if os.path.exists(META):
        with open(META, encoding="utf-8") as fh:
            meta = json.load(fh)

    p_guessed = sum(1 for w in guessed if w.startswith("p"))
    top = rows[:40]
    lines = [
        "# Status",
        "",
        f"_Updated {meta.get('last_run_utc', 'unknown')}_",
        "",
        f"- **Winner found:** {'YES -- see WINNER.md' if meta.get('winner_found') else 'not yet'}",
        f"- Comments counted: **{meta.get('comments_seen', 0):,}**",
        f"- Distinct one-word guesses: **{meta.get('distinct_guessed_words', 0):,}** "
        f"({p_guessed:,} start with P)",
        f"- Unguessed candidates remaining: **{len(rows):,}**",
        "",
        "## Top 40 remaining candidates",
        "",
        "Ranked by corpus frequency, with bonuses for video-thematic words and a",
        "penalty for plurals and inflected forms. Heuristic, not a prediction.",
        "",
        "| # | word | letters | syl | zipf | score |",
        "|---|------|---------|-----|------|-------|",
    ]
    for i, (s, w, L, n, z, fl) in enumerate(top, 1):
        lines.append(f"| {i} | `{w}` | {L} | {n} | {z} | {s} |")
    lines += [
        "",
        f"Full scored list: [`data/candidates.tsv`](data/candidates.tsv) ({len(rows):,} rows).",
        "",
        "## Most-guessed words so far",
        "",
        "| word | times submitted |",
        "|------|-----------------|",
    ]
    for w, c in sorted(guessed.items(), key=lambda kv: -kv[1])[:15]:
        lines.append(f"| `{w}` | {c:,} |")
    lines.append("")

    with open(STATUS, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"candidates remaining : {len(rows)}")
    print(f"top 10               : {', '.join(r[1] for r in rows[:10])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
