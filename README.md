# Test-Your-Wifi-Speeds

Sequentially runs three speed test websites (Xfinity, Fast.com, Speedtest.net) and reports
averaged download/upload speeds. Uses dynamic waits so it finishes as quickly as your connection
allows rather than burning fixed sleep timers.

## Setup

```bash
pip3 install -r requirements.txt
```

## Usage

```bash
# Basic run (opens a browser window)
python3 test-wifi.py

# Run without a visible browser window
python3 test-wifi.py --headless

# Save results to a JSON file
python3 test-wifi.py --output results.json

# Run only specific tests
python3 test-wifi.py --tests fast
python3 test-wifi.py --tests xfinity,speedtest

# Combine options
python3 test-wifi.py --headless --output results.json --tests fast,speedtest
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--headless` | Run Chrome without a visible window |
| `--output FILE` | Write results as JSON to FILE |
| `--tests LIST` | Comma-separated subset of `xfinity`, `fast`, `speedtest` (default: all three) |

## Output

Results are printed to the terminal with per-site download/upload speeds and an averaged summary.

With `--output`, a JSON file is also written:

```json
{
  "timestamp": "2025-01-15T10:30:00.123456",
  "tests_run": ["xfinity", "fast", "speedtest"],
  "results": {
    "xfinity":   { "download": 250.3, "upload": 20.1 },
    "fast":      { "download": 248.0, "upload": 19.8 },
    "speedtest": { "download": 252.1, "upload": 20.5 }
  },
  "summary": { "download": 250.1, "upload": 20.1 }
}
```

If a test fails, its entry is `null` and it is excluded from the summary average.

## Notes

- A typical full run (all three tests) takes 60–90 seconds depending on connection speed.
- All waits are dynamic — results are captured as soon as they appear rather than after a fixed delay.
- Individual test failures are logged and skipped; the remaining tests still run.
