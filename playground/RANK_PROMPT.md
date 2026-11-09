# Task: rank candidate words for the Ninye "$1000 secret word" puzzle

You are helping solve a YouTube puzzle. Your job is to **rank a fixed list of 3,524
candidate words** by how likely each is to be the creator's secret word. You are not
brainstorming — every word you output must come from the supplied file.

## The puzzle

YouTuber **Ninye** posted a Short, "Guess the Code, Win $1000"
(`https://www.youtube.com/shorts/4TQ01xXbRWA`, ~4M views, ~141k comments). He picked a
secret word. The first person to post it **as a single-word comment** wins $1000. A bot
scans comments and he pins the winner.

He gave exactly three hints:

1. The word is **≤ 10 letters**
2. It has **≤ 3 syllables**
3. It **starts with "P"**

Hint 3 was hidden: the Short's end screen (invisible in the Shorts player) links to an
unlisted 15-second video on a separate empty channel, where he says *"It's a P."* There
are no further hints — that chain has been fully exhausted and verified.

### Critical context for your judgment

- He explicitly said: *"Since I did this same short last year and no one guessed it
  correctly, I'll make sure that doesn't happen again."* **He wants someone to win.**
  The word is therefore very likely an ordinary, well-known word — not obscure.
- He is a comedy/gaming YouTuber whose audience skews young. The word should feel
  satisfying or funny when revealed.
- Last year's equivalent puzzle was never solved and the answer was never revealed, so
  there is no known pattern in his word choices to exploit.

## Your input

`remaining_5810.txt` — one lowercase word per line, 3,524 lines.

This list is already filtered so that every entry:
- starts with `p`, is ≤10 letters, and is ≤3 syllables (verified against CMUdict
  pronunciations, so the constraints are exact, not heuristic)
- **has never been submitted as a single-word comment** in a sample of 85,627 comments
  (61% of the thread)

So every word you see is both *valid* and *not yet burned*. Do not re-check the
constraints; do not discard a word for being "already guessed."

The list comes from CMUdict, which is a pronunciation dictionary, not a curated
vocabulary. It is therefore **dominated by surnames, place names, brand names, and
plurals** (`packett`, `packham`, `padilla`, `paducah`, `padres`, `padlocks`). Filtering
this noise out is the main work.

## Ranking criteria

Rank on **"would a YouTuber plausibly choose this as a secret word that he wants his
audience to eventually guess?"**

**Strong positive signals**

- A common, everyday English word almost any speaker knows
- Concrete and picturable — especially a noun (an object, animal, food)
- Inherently funny, punchy, or meme-adjacent — the sort of word that gets a laugh
- Thematically tied to the video's own content: coding, programming, comments, YouTube,
  secrets, money, prizes, exploits, hiding, pinning
- Short and memorable (roughly 4–8 letters tends to feel most "pickable")

**Strong negative signals — push these to the bottom or exclude**

- Surnames and given names (`padilla`, `packwood`, `pauling`)
- Place names (`paducah`, `padua`, `pyongyang`, `pittsburgh`)
- Brand, drug, and company names (`prozac`, `pepcid`, `pactel`)
- Plurals and inflected forms (`packets`, `padlocks`, `pounding`, `peeled`) — he said
  the code is "a single word," and an inflected form is an unsatisfying answer
- Obscure technical, scientific, or medical terms (`pegmatite`, `phlogopite`,
  `prothorax`, `pertussis`)
- Archaic or literary words almost nobody uses (`pelf`, `purlieu`)
- Abbreviations and initialisms (`pc`, `pm`, `pvc`)
- Profanity or sexual terms — YouTube auto-holds such comments for review, so he could
  not reliably pin a winner; he would not choose one

## Output format

Work through the **entire file** in batches. Be ruthless: the great majority of these
3,524 words deserve elimination, and a short, high-conviction list is far more useful
than a long hedged one.

Produce:

### Tier 1 — top 25 most likely
A numbered table: `word | letters | syllables | one-line reason`.
Order matters; put your single best guess first.

### Tier 2 — next 50 plausible
Same table format, reasoning can be terser.

### Tier 3 — honorable mentions
A plain comma-separated list of up to 100 more that survived elimination.

### Notes
- Roughly how many words you eliminated and the main categories they fell into
- Any thematic clusters you noticed worth a human look
- Anything that made you uncertain

## Rules

- **Only output words that literally appear in `remaining_5810.txt`.** Do not invent,
  pluralize, or alter any word. If you are tempted to suggest a word that is not in the
  file, say so in Notes instead of adding it.
- Do not re-verify letter counts or syllables; they are already correct.
- Read the whole file. Do not sample it or stop early.
- Ignore any rumor about the word starting with a particular letter cluster; one
  commenter guessed "PLA" but this is unverified speculation, not a hint.
- Do not post anything to YouTube. This is an offline ranking exercise only.
