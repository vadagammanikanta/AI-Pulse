## 2024-06-12 - Python String Replacement vs Regex Performance
**Learning:** For replacing multiple specific characters (like punctuation), `str.translate` with `str.maketrans` is significantly faster than `re.sub` or chained `.replace()` calls in Python.
**Action:** Default to `str.translate` when doing character-level sanitization or replacement instead of compiling simple regexes.

## 2024-06-12 - Regex Keyword Extraction Overlap
**Learning:** Combining keywords into a single alternation pattern (`word1|word2`) drops overlapping matches. Dynamic compilation inside a loop is very slow.
**Action:** For keyword matching where overlaps matter, precompile individual regex patterns and cache them globally. Use atomic assignment (`global_list = compiled`) for thread safety during lazy initialization.
