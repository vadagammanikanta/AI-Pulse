## 2024-05-19 - Pre-compiled Regexes and str.translate for String Cleaning
**Learning:** Compiling regex patterns and using `re.sub` for simple string replacements within loops for a large volume of text repeatedly can cause a huge performance bottleneck due to regex compilation overhead and inefficient string mapping in python.
**Action:** Always precompile regexes globally or at class level. Use `str.translate` instead of multiple `str.replace` or `re.sub` for fast multiple character replacements.
