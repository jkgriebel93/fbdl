# Refactoring Opportunities

Based on a thorough analysis of the codebase (~4,700 lines across 9 modules).

## High Priority

### 1. Code Duplication

| Issue | Location 1 | Location 2 | Lines Affected |
|-------|-----------|-----------|----------------|
| Metadata XML generation | `base.py:783-799` | `nfl.py:268-299` | ~30 lines |
| File naming logic | `nfl.py:338-376` | `base.py:563-588` | ~50 lines |
| Browser retry logic | `draft_buzz.py:118-141` | `draft_buzz.py:1370-1397` | ~40 lines |

**Bug:** `self.errors = []` initialized twice at `nfl.py:98-99`

### 2. God Classes

**ProspectParserSoup** (`draft_buzz.py:260-856`)
- 503 lines, 27 methods
- Should split into:
  - `RatingExtractor`
  - `StatsParser`
  - `SkillsParser`
  - `ScoutingReportParser`

**NFLWeeklyDownloader** (`nfl.py:135-491`)
- Uses multiple inheritance (`BaseDownloader + NFLBaseIE`)
- Prefer composition over inheritance
- Extract: `FileNamer`, `GameExtractor`, `MetadataWriter`

### 3. Print Statements Instead of Logging

20+ locations use `print()` instead of proper logging:
- `base.py:502, 600`
- `nfl.py:354`
- `draft_buzz.py` (multiple)
- `fbcm.py` (multiple)

Should implement proper logging framework with levels, timestamps, and file output.

## Medium Priority

### 4. Large `base.py` (848 lines)

Split into separate modules:
```
fbcm/
  mappings.py          # Team abbreviations, position mappings (113 lines)
  downloaders/
    base_downloader.py # BaseDownloader class
  file_operations.py   # FileOperationsUtil class
  metadata.py          # MetaDataCreator class
```

### 5. Configuration Handling

`fbcm.py:191-223` has extensive dict unpacking that is error-prone:
```python
kwargs = {
    "output_directory": output_directory,
    "cookies_file": cookies_file,
    # ... 8 more lines ...
}
kwargs = apply_config_to_kwargs(config, "nfl_games", kwargs)

output_directory = kwargs.get("output_directory") or os.getcwd()
cookies_file = kwargs.get("cookies_file") or "cookies.txt"
# ... 9 more lines ...
```

**Recommendation:** Use a dataclass or typed config object.

### 6. Inconsistent Naming

| Location | Issue |
|----------|-------|
| `nfl.py:66` | `base_yt_ops` (misspelled) |
| `base.py:458` | `base_yt_opts` (correct) |
| Various | Inconsistent error handling patterns |

### 7. Magic Numbers/Strings

Hard-coded values scattered across classes:
- URLs: `nfl.py:53, 186`, `draft_buzz.py:216`
- Sleep values: `draft_buzz.py:387` (`uniform(3.5, 4.5)`)
- Viewport: `draft_buzz.py:78` (`{"width": 1920, "height": 1080}`)
- Slow motion: `draft_buzz.py:150` (`slow_mo=150`)

**Recommendation:** Move to constants or configuration.

## Lower Priority

### 8. Type Hint Gaps

Missing return types:
- `draft_buzz.py:237` - `_find_and_download_image()`
- `draft_buzz.py:412-422` - `_extract_games_and_snaps()`
- `fbcm.py:56` - `download_list()` parameters

### 9. Bare Exception Handlers

Replace with specific exceptions:
```python
# Bad (draft_buzz.py:211)
except Exception:
    pass

# Better
except (ConnectionError, TimeoutError) as e:
    logger.warning(f"Network error: {e}")
```

### 10. Missing Tests

No tests for:
- `draft_buzz.py` - scraping and parsing
- `word_gen.py` - document generation
- `models.py` - data validation
- Config loading and merging logic

## Existing TODO Comments

The codebase already acknowledges several issues:

| Location | TODO |
|----------|------|
| `nfl.py:27` | "This class requires a lot of work to leverage yt-dlp fully" |
| `base.py:531` | "Is this really the right place for directory_path?" |
| `base.py:550` | "Change this from print calls to logger invocations" |
| `base.py:573` | "Implement an actual logging config to make this nicer" |
| `base.py:750` | "There are multiple versions of this method. Consolidate" |
| `base.py:784` | "Consolidate this with the same method from NFLWeeklyDownloader" |
| `draft_buzz.py:173` | "Returning both text_content and page.content is a temporary kludge" |
| `fbcm.py:184` | "Ensure jellyfin isn't running..it borks the post processing" |

## Suggested Phased Approach

### Phase 1 (Critical)
1. Extract metadata generation to shared class
2. Implement proper logging instead of print statements
3. Add browser retry logic abstraction
4. Fix the duplicate `self.errors = []` bug

### Phase 2 (High)
1. Split `ProspectParserSoup` into focused parsers
2. Refactor `FileOperationsUtil` responsibilities
3. Remove multiple inheritance from `NFLWeeklyDownloader`
4. Extract file naming logic to separate class

### Phase 3 (Medium)
1. Create configuration dataclass instead of dict unpacking
2. Move mappings to separate module
3. Add comprehensive logging configuration
4. Improve test coverage
