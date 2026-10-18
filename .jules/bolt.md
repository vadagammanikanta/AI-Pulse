## 2024-11-20 - Regex compilation in text processing
**Learning:** Compiling regex patterns for dynamic lists like settings keywords inside the loop of frequently called functions (e.g. `compute_feed_score` on `/feed` endpoints) introduces massive overhead. Pre-compiling to module scope gave 3x-10x speedups.
**Action:** Always check if `re.compile` or `re.sub` is being executed dynamically inside a hot path on configuration lists, and move compilation to module or class init level.
