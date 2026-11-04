## 2025-02-18 - Fast string replacement
**Learning:** For simple character mapping/stripping in Python, `str.translate` with `str.maketrans` is significantly (~15x) faster than `re.sub()`.
**Action:** Replace `re.sub(pattern, " ", text)` with `text.translate(_CLEAN_TRANS)` for basic character sanitization.
