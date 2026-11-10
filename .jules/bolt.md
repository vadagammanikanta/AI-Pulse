
## 2024-05-19 - Fast fuzzy matching with RapidFuzz
**Learning:** When using RapidFuzz for fuzzy string matching against a list of strings, manually lowercasing/stripping and iterating in Python is significantly slower than using `rapidfuzz.process.extractOne` or `extract` with `processor=rapidfuzz.utils.default_process`. `extractOne` delegates the iteration and preprocessing to C++, making it approximately 2.5x-3x faster.
**Action:** Use `rapidfuzz.process.extractOne` with the built-in processors instead of a manual loop for fuzzy deduplication in Python.
