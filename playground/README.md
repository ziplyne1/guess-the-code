# Guess the Code — $1000 word hunt

Ninye, ["Guess the Code, Win $1000"](https://www.youtube.com/shorts/4TQ01xXbRWA) (`4TQ01xXbRWA`).

## Known hints

1. `<= 10 letters`
2. `<= 3 syllables`
3. **starts with P** — the hidden hint

## Where the third hint was hidden

The Short's **end screen** (45.5s–50.5s) links to an **unlisted 15-second video**
titled "Secret" (`E0UO6lLU23Q`), hosted on a *separate, otherwise empty* channel
[`@TheNinyays`](https://www.youtube.com/@TheNinyays). End screens never render in the
Shorts player and the video is unlisted, so it's unreachable from a phone — which is
what "you won't find it from your phone" meant.

In it he says: *"Well, well, well. You found my secret… I'm going to tell you what the
first letter of the word is. Don't share this in the comments of the main video. It's a P."*

Same trick as his earlier short "Find my Secret Channel, Win $100".

### Ruled out

Video frames (all 3,032 scanned — the purple bar is mosaic-baked, no clean frame exists),
storyboards, thumbnails incl. A/B `_custom_N` slots, audio tracks (only `en-US` + Klingon
`tlh`), creator subtitles (none — ASR only), localized titles/descriptions (identical across
90 locales), description, tags/keywords, chapters. The "View corrections" info card on both
videos is a **decoy** — the panel has no server-side content.

## Tools

```bash
./tools/setup.sh      # one-time: downloads CMUdict + WordNet into data/ (~20MB)
```

### `tools/pwords.py` — find candidate words

Syllables come from **CMUdict** (real pronunciations, not a heuristic).
Definitions and the real-word filter come from **WordNet**.

```bash
./tools/pwords.py                          # P, <=10 letters, <=3 syllables -> 1958 words
./tools/pwords.py --defs                   # with definitions
./tools/pwords.py --pos noun --defs        # nouns only

# the useful one: real words that nobody has actually submitted yet
./tools/pwords.py --pos noun --defs --guessed comments.json --hide-guessed

# narrow it down
./tools/pwords.py --pos noun --min-letters 5 --max-letters 7 \
                  --min-syllables 2 --max-syllables 2 \
                  --guessed comments.json --hide-guessed --defs

./tools/pwords.py --start f --max-syllables 2   # last year's rumoured "F" word
```

Flags: `--start --min-letters --max-letters --min-syllables --max-syllables --pos
--defs --any-word --guessed --hide-guessed --sort {alpha,len,syl,guessed} --limit`

`solo` = times submitted as a valid one-word comment. `seen` = times the word appears
anywhere in any comment.

### `tools/comments.py` — read and filter the comments section

```bash
./tools/comments.py stats
./tools/comments.py solo --start p --top 60   # valid one-word P guesses, ranked
./tools/comments.py word python               # has this specific word been guessed?
./tools/comments.py grep "first letter"       # full-text search
./tools/comments.py authors --uploader        # pinned / creator comments
```

### Fetching — you cannot get all 140K

YouTube stops handing out continuation tokens long before the end of the thread,
and the two sorts stall in different places:

| sort  | depth reached on this video |
|-------|------------------------------|
| `top` | **~2,200** — genuine wall at page 63; `--max 0` changes nothing |
| `new` | **85,008** — 4,180 pages before YouTube cut it off (~45 min) |

**yt-dlp's default sort is `new`**, not `top` — an unflagged `yt-dlp --get-comments`
gets the deep one. There is **no resume**: continuation tokens live in memory only,
so an interrupted run restarts from page 1. Ctrl-C does keep what it collected.

Neither reaches 140K. They return *different slices*, so `fetch` **merges into
`comments.json` by default** (deduped by comment id) — run both and repeat over
days to accumulate coverage:

```bash
./tools/comments.py fetch --max 0 --sort new --replies 0   # deepest, fastest
./tools/comments.py fetch --max 0 --sort top               # different slice
./tools/comments.py fetch --max 0 --sort new --replace     # start clean instead
```

`--replies 0` skips reply threads and is much faster; drop it when you want replies
too. Ctrl-C is safe — whatever was fetched still gets merged.

### Importing a manual yt-dlp run

```bash
yt-dlp --get-comments https://www.youtube.com/shorts/4TQ01xXbRWA
./tools/comments.py import "Guess the Code, Win \$1000 [4TQ01xXbRWA].info.json"
```

### Watching for the winner

Pinned comments sort to the top, so this costs one small request (~3s) rather
than a full pull. Exit code `0` = pin found, `1` = nothing yet.

```bash
./tools/comments.py watch
while ! ./tools/comments.py watch; do sleep 1800; done   # poll until it lands
```

## State of the hunt (85,627 comments = 61% of the thread)

- **No pinned comment and no creator comment** on either video — nobody has won.
- **1,597 of 1,958** dictionary candidates (82%) already submitted as one-word guesses.
- Only **361** survive, and they are almost entirely proper nouns (`Paducah`, `Pasteur`,
  `Pyongyang`), inflected forms (`papering`, `peeled`), obscure technical terms
  (`pegmatite`, `phlogopite`), and profanity YouTube likely auto-holds.
- The crowd has also tried **3,695 non-dictionary** P-words (`petrichor`, `passcode`,
  `pokemon`, `pogonip`).

Brute force is effectively exhausted. Either the word is outside standard vocabulary,
or Ninye simply has not pinned yet — hence `watch`.

## Why the popular guesses are probably wrong

Rule 2 of the video means **only single-word comments count**. In the 2,216-comment
sample, `programmer` was submitted solo **156 times (~7%)**, which scales to roughly
10,000 submissions across the full thread — and **no comment is pinned**. Same story for
`potential`, `password`, `premiere`, `powerpoint`, `process`, `pin`.

Check before you spend a guess:

```bash
./tools/comments.py word <yourword>
./tools/comments.py authors --uploader    # a pinned winner would appear here
```

Caveat: the sample is ~1.6% of the thread, so "0 solo" means *absent from the sample*,
not *nobody has tried it*.
