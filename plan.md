# Plan: Pre-Market Opportunity List Auto-Archiving

## Objective
Integrate automatic opportunity list archiving into the existing running containers. When the market is closed, the system should automatically save opportunity lists to `/data/archive/` with timestamps, making them available for review when the market opens.

## Requirements
1. **No external scheduling** - Everything runs inside the existing containers
2. **Automatic detection** - System detects when market is closed
3. **Dual format** - Save both JSON (machine-readable) and text (human-readable) files
4. **Archive organization** - Files saved with timestamps in `/data/archive/`
5. **Latest symlinks** - Create symlinks to latest files for easy access
6. **Logging** - All activity logged to stdout (visible in Docker logs)
7. **Non-breaking** - Must not interfere with existing functionality

## Current State Analysis

### Files Involved
- `stock_checker/market_scanner.py` - Contains `MarketScanner` class with `identify_best_opportunities()` method
- `stock_checker/intelligent_trader.py` - Uses `MarketScanner` and calls `identify_best_opportunities()`
- `stock_checker/paper_trader.py` - May use market scanning (needs verification)
- `requirements.txt` - Dependencies list

### Current Flow
1. `IntelligentTrader.scan_markets()` calls `scanner.identify_best_opportunities()`
2. `MarketScanner.identify_best_opportunities()` scans markets and returns results
3. Results are displayed but not persisted to archive

### Data Directory Structure
```
/data/
├── portfolio.json
├── trades.jsonl
├── stock_universe.json
├── stock_scan_history.json
└── entry_times.json
```

## Implementation Plan

### Phase 1: Add Dependencies
**File**: `requirements.txt`
- Add `pytz>=2023.3` for timezone handling (market hours detection)

**Risk**: Low - pytz is a standard library, well-tested
**Testing**: Verify installation in Docker container

### Phase 2: Add Market Hours Detection
**File**: `stock_checker/market_scanner.py`
**Location**: Add new method to `MarketScanner` class

**Method**: `is_market_closed() -> bool`
- Detects if US stock market is closed
- Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
- Returns `True` if:
  - Weekend (Saturday/Sunday)
  - Before 9:30 AM ET
  - After 4:00 PM ET
- Uses `pytz` for timezone conversion
- Graceful fallback if timezone detection fails (assume market might be open)

**Risk**: Medium - Timezone handling can be tricky
**Testing**: 
- Test during market hours (should return False)
- Test after market close (should return True)
- Test on weekends (should return True)
- Test timezone edge cases

### Phase 3: Add Archive Saving Functionality
**File**: `stock_checker/market_scanner.py`
**Location**: Add new methods to `MarketScanner` class

**Method 1**: `save_opportunities_to_archive(results: Dict, data_dir: str = "/data")`
- Creates `/data/archive/` directory if it doesn't exist
- Generates timestamped filenames: `opportunities_YYYYMMDD_HHMMSS.json` and `.txt`
- Saves JSON data (full results dict)
- Saves human-readable text report (via `_format_opportunities_report()`)
- Creates symlinks: `opportunities_latest.json` and `opportunities_latest.txt`
- Logs success/failure to stdout
- Returns tuple of (json_path, report_path) or (None, None) on error

**Method 2**: `_format_opportunities_report(results: dict) -> str`
- Formats results as human-readable text
- Includes summary statistics
- Lists top recommendations with details
- Lists crypto leaders with metrics
- Lists stock breakouts with sector info
- Returns formatted string

**Risk**: Low - File I/O operations, well-understood
**Testing**:
- Test directory creation
- Test file writing
- Test symlink creation
- Test error handling (permissions, disk full, etc.)

### Phase 4: Integrate Auto-Archiving
**File**: `stock_checker/market_scanner.py`
**Location**: Modify `identify_best_opportunities()` method

**Changes**:
- After building results dict (line ~442)
- Before returning results
- Check if market is closed: `if self.is_market_closed():`
- If closed, call `self.save_opportunities_to_archive(results)`
- No changes to return value or existing logic

**Risk**: Low - Only adds functionality, doesn't modify existing behavior
**Testing**:
- Verify existing functionality still works
- Verify archiving happens when market is closed
- Verify no archiving during market hours
- Verify results dict unchanged

### Phase 5: Update Imports
**File**: `stock_checker/market_scanner.py`
**Location**: Top of file

**Add imports**:
```python
import json
from pathlib import Path
from datetime import time as dt_time
import pytz
```

**Risk**: Low - Standard library imports
**Testing**: Verify no import errors

## Implementation Steps (Sequential)

1. **Step 1**: Update `requirements.txt`
   - Add `pytz>=2023.3`
   - Verify format matches existing entries

2. **Step 2**: Add imports to `market_scanner.py`
   - Add `json`, `Path`, `dt_time`, `pytz`
   - Place with existing imports

3. **Step 3**: Implement `is_market_closed()` method
   - Add after `__init__` method
   - Test logic carefully
   - Add error handling

4. **Step 4**: Implement `_format_opportunities_report()` method
   - Add as private method
   - Format matches existing print statements style
   - Test with sample data

5. **Step 5**: Implement `save_opportunities_to_archive()` method
   - Add after `_format_opportunities_report()`
   - Handle all edge cases
   - Test file operations

6. **Step 6**: Modify `identify_best_opportunities()` method
   - Add auto-archiving check at end (before return)
   - Minimal change - just 2-3 lines
   - Preserve all existing functionality

7. **Step 7**: Test integration
   - Run existing tests
   - Test during market hours (no archive)
   - Test after market close (archive created)
   - Verify Docker logs show archive messages
   - Verify files in `/data/archive/`

## Testing Strategy

### Unit Tests
- Test `is_market_closed()` with various times/dates
- Test `_format_opportunities_report()` with sample data
- Test `save_opportunities_to_archive()` with mock file system

### Integration Tests
- Test full flow: `identify_best_opportunities()` → auto-archive
- Test with `IntelligentTrader` running
- Verify no performance impact

### Manual Testing
1. Start container with `IntelligentTrader`
2. Wait for market scan (or trigger manually)
3. During market hours: Verify no archive created
4. After market close: Verify archive created
5. Check `/data/archive/` directory contents
6. Verify symlinks work
7. Verify log output

## Risk Mitigation

### Risk 1: Timezone Issues
- **Mitigation**: Use `pytz` library (standard, well-tested)
- **Fallback**: If timezone detection fails, assume market might be open (safer)

### Risk 2: File System Errors
- **Mitigation**: Wrap file operations in try/except
- **Fallback**: Log error, continue execution (don't break main flow)

### Risk 3: Breaking Existing Functionality
- **Mitigation**: Minimal changes, only additions
- **Testing**: Run existing tests, verify no regressions

### Risk 4: Performance Impact
- **Mitigation**: Archive only when market closed (infrequent)
- **Testing**: Measure scan time before/after

### Risk 5: Disk Space
- **Mitigation**: Files are small (JSON + text)
- **Future**: Could add cleanup of old archives (not in scope)

## Success Criteria

1. ✅ When market is closed, opportunity lists are automatically saved
2. ✅ Files saved to `/data/archive/` with timestamps
3. ✅ Both JSON and text formats available
4. ✅ Symlinks to latest files work
5. ✅ All activity logged to stdout
6. ✅ No impact on existing functionality
7. ✅ No manual intervention required

## Rollback Plan

If issues arise:
1. Revert changes to `market_scanner.py` (remove new methods and modifications)
2. Revert `requirements.txt` (remove pytz)
3. Rebuild Docker image
4. Restart containers

## Future Enhancements (Out of Scope)

- Cleanup old archive files (keep last N days)
- Compress old archives
- Add archive metadata/index file
- Support for other markets (European, Asian)
- Email notifications when archive created

## Files to Modify

1. `requirements.txt` - Add pytz dependency
2. `stock_checker/market_scanner.py` - Add 3 new methods, modify 1 method, add imports

## Estimated Impact

- **Lines of code added**: ~150-200 lines
- **Files modified**: 2 files
- **Breaking changes**: None
- **Performance impact**: Negligible (only when market closed)
- **Dependencies added**: 1 (pytz)

## Approval Checklist

- [x] Plan reviewed
- [x] Dependencies acceptable
- [x] Testing strategy approved
- [x] Risk mitigation acceptable
- [x] Ready for implementation

