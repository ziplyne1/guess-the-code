# guess-the-code-watch

Automated watcher for Ninye's ["Guess the Code, Win $1000"](https://www.youtube.com/shorts/4TQ01xXbRWA)
Short. Runs on a schedule and keeps three things current:

1. **Is there a winner yet?** — polls both the Short and the hidden "Secret" video for a
   pinned or creator comment. If one appears, it writes `WINNER.md` and opens a GitHub issue.
2. **Every word guessed so far** — `data/guessed.json`, word → times submitted as a
   valid one-word comment.
3. **What's left, ranked** — `data/candidates.tsv`, every pronounceable P-word nobody
   has guessed, scored by plausibility. Top 40 surfaced in [`STATUS.md`](STATUS.md).

## The puzzle

The word is **≤10 letters**, **≤3 syllables**, and **starts with P**. The third hint was
hidden behind the Short's end screen (invisible in the Shorts player) which links to an
unlisted video on a separate channel. That chain is exhausted — there are no more hints.

## Current state

Seeded with **85,627 comments (61% of the thread)**. At seeding: 15,462 distinct
one-word guesses, 5,292 of them starting with P, **no winner pinned**.

## How ranking works

Transparent heuristic, no model. Scored per word:

| signal | weight | why |
|---|---|---|
| corpus frequency (`wordfreq` zipf) | base | he said he *wants* a winner this year, so the word is probably ordinary |
| in WordNet | +1.0 | real English word rather than a CMUdict surname |
| is a noun | +0.4 | concrete nouns make satisfying answers |
| 4–8 letters | +0.3 | the "pickable" sweet spot |
| video-thematic | +0.6 | a self-referential pick suits this creator |
| **not** in WordNet | −2.5 | overwhelmingly surnames/place names (`pete`, `powell`) |
| proper noun | −3.0 | detected via WordNet capitalization (`Princeton`, `Potomac`) |
| plural / inflected | −1.5 | "a single word" — `packets` is an unsatisfying answer |
| vulgar | −5.0 | YouTube auto-holds those comments, so a winner couldn't be pinned |

Tune the weights in `scripts/rank.py`; re-run to regenerate.

## Setup

```bash
gh repo create guess-the-code-watch --public --source=. --push
```

Then **Settings → Actions → General → Workflow permissions → Read and write**, so the
job can commit results and open issues.

Trigger a first run from the Actions tab (`watch` → Run workflow).

## ⚠️ The catch: YouTube blocks GitHub-hosted runners

This is the real obstacle. YouTube aggressively rate-limits datacenter IPs, and
GitHub Actions runners frequently get `Sign in to confirm you're not a bot`. The
comment step is `continue-on-error`, so a blocked tick is skipped rather than failing
the run — but on a bad stretch it may make little progress.

Three options, best first:

**1. Run it locally instead** (most reliable — residential IP):

```bash
python scripts/update.py && python scripts/rank.py
```

On macOS, schedule it with `launchd` every 2 hours:

```bash
cat > ~/Library/LaunchAgents/com.user.gtcwatch.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.user.gtcwatch</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string><string>-c</string>
    <string>cd ~/Developer/playground/guess_the_code/watcher &amp;&amp; python3 scripts/update.py &amp;&amp; python3 scripts/rank.py</string>
  </array>
  <key>StartInterval</key><integer>7200</integer>
  <key>RunAtLoad</key><true/>
</dict></plist>
EOF
launchctl load ~/Library/LaunchAgents/com.user.gtcwatch.plist
```

**2. Add cookies.** Export cookies for youtube.com in Netscape format and store the
file's contents as the repo secret `YT_COOKIES`. The workflow picks it up
automatically. Use a throwaway Google account — these cookies grant account access,
and they expire, so this needs occasional refreshing.

**3. Self-hosted runner** on a machine with a residential IP.

## Notes

- Raw comments are never committed — only derived counts — so the repo stays ~5MB.
- `data/seen_ids.txt.gz` dedupes across runs so counts don't double.
- yt-dlp's default sort is **newest**, which paginates far deeper (~85K) than `top`
  (~2.2K). There's no resume: an interrupted pull restarts from page 1.
- Scheduled workflows are disabled after 60 days of repository inactivity; the bot's
  own commits normally count, but check in occasionally.
