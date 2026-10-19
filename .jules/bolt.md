## 2024-05-15 - [Ranker Performance Improvement]
**Learning:** Compiling identical regular expressions for static inputs (e.g., matching known keywords) inside deeply nested loops or heavily called utility functions (like `extract_matched_keywords` in ranker) introduces significant CPU overhead.
**Action:** Always precompile regular expressions for static configurations/patterns at module initialization instead of inside the function execution block.
