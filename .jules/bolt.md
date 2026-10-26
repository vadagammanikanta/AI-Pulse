## 2024-05-18 - Optimized Regex Keyword Matching
**Learning:** In Python, dynamic creation and compilation of regular expressions inside a loop, especially on hot paths like feed ranking, leads to significant overhead. Precompiling them lazily into a cached list avoids this overhead, as the memory notes suggest avoiding single alternations due to overlapping match drops.
**Action:** When extracting multiple keywords using regexes on every item iteration, always precompile the expressions once and cache them. Use lazy initialization with atomic assignment.
