
## 2023-10-25 - Caching Eager Evaluation Anti-Pattern
**Learning:** Using `dict.setdefault(key, expensive_call())` in Python still eagerly evaluates `expensive_call()` on every single iteration, even if the key exists. This defeats the purpose of the cache and actually hurts performance.
**Action:** Use standard `if not item in cache` or a one-time global variable initialization block instead to properly implement lazy evaluation caching.

## 2023-10-25 - Thread-Safe Lazy Initialization
**Learning:** Lazy initialization that modifies a global list using `.append()` inside an `if not list:` block is unsafe in concurrent environments (like a FastAPI web server), as race conditions on startup can cause multiple threads to append to the list simultaneously, duplicating entries.
**Action:** Build the fully initialized list locally and then assign it back to the global variable in a single step (e.g., `global_list = [...]`).
