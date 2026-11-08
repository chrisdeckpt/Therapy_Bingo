# Rounds: a diagnostic reasoning game

Players see 16 clinical findings and sort them into 4 diagnoses. They get 4 mistakes. Each solved
group is revealed in its difficulty color with a short teaching point. Plain HTML, CSS, and
JavaScript, with no build step and no dependencies.

## Running it

Browsers won't let a page opened by double-click read `puzzles.json`, so serve the folder:

```bash
cd 03-rounds-game
python3 -m http.server 8000
# open http://localhost:8000
```

If you do open `index.html` directly, the page shows a file picker so you can load
`puzzles.json` by hand.

To share it with students, upload the folder to any static host (GitHub Pages, Netlify, a school
web server) as is.

**Direct links to a puzzle:** add `#<puzzle id>` to the URL, for example `http://localhost:8000/#shoulder`.

## How to play

- Click 4 findings and press **Submit** (or Enter).
- "One away…" means 3 of your 4 belong together.
- After 4 wrong guesses the game ends and shows every group with its teaching point.
- Use the **Puzzle** menu to switch puzzles, or **Next puzzle** after a round.

## Authoring new puzzles

All content lives in `puzzles.json`. You never need to edit the code. To add a puzzle, append an
object to the `"puzzles"` array:

```json
{
  "id": "knee",                       // unique, no spaces; used in the URL (#knee)
  "title": "The swollen knee",        // shown in the puzzle menu
  "topic": "Knee differential",       // optional subtitle
  "groups": [
    {
      "name": "ACL tear",             // the diagnosis revealed when the group is solved
      "difficulty": 1,                // 1 = easiest (yellow), 2 green, 3 blue, 4 = hardest (purple)
      "items": ["Positive Lachman", "Pivot shift", "Pop at injury", "Hemarthrosis within 2 h"],
      "explanation": "Teaching point shown after the group is revealed."
    }
    // ...exactly 4 groups in total
  ]
}
```

(JSON doesn't allow `//` comments. They're only here to explain the fields, so leave them out of your file.)

### Rules the game checks on load

- Every puzzle has a unique `id` and a `title`.
- Exactly **4 groups**, each with exactly **4 items**.
- No item appears twice in one puzzle (case-insensitive).
- `difficulty` is 1, 2, 3, or 4.

If something breaks a rule, the page lists the exact problems instead of loading a broken puzzle.
A missing comma or quote shows up as a "JSON syntax error". Pasting the file into
https://jsonlint.com shows the line.

### Tips for good puzzles

- **Use red herrings.** The best puzzles have findings that seem to fit two diagnoses. For example,
  "symptoms ease with sitting" (stenosis) versus a disc patient who is worse sitting.
- **Set difficulty by how distinctive the group is,** not by how rare the condition is.
- **Keep items short,** under about 40 characters, so they fit on phone-sized tiles.
- **Keep explanations to 2–3 sentences** and focus on *why* the findings point to that diagnosis.
- **Cite the clusters you rely on** (Laslett, Sutlive, Park, HINTS, and so on) so students can look them up.

## Files

| File | Purpose |
|---|---|
| `index.html` | Page structure |
| `styles.css` | Layout and colors (light/dark aware). Group colors are `--d1`…`--d4` |
| `game.js` | Game logic, puzzle loading, and validation |
| `puzzles.json` | The question bank, with 3 sample puzzles |
