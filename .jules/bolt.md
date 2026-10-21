## 2024-10-21 - Regex caching logic flaw

**Learning:** When combining overlapping keywords into a single regex or using maps based on normalized patterns, identical normalizations can overwrite each other, leading to logic bugs. Caching individual pattern compilation maintains logic correctly while still speeding up iterative operations by not having to recompile the string constantly.
**Action:** When caching repetitive string matching patterns, cache the pattern compilation itself per-item without altering the search algorithm's logic when identical normalizations could be present.
