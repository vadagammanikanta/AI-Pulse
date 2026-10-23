## 2025-02-27 - Regex compilation caching in hot paths
**Learning:** Re-compiling regular expressions within frequently called functions like `extract_matched_keywords` creates a measurable bottleneck during bulk operations like feed ranking.
**Action:** When a function runs in a tight loop and needs to evaluate text against a fixed set of regex patterns, cache the compiled `re.Pattern` objects globally (or on a class/object) to avoid repeated compilation overhead.
