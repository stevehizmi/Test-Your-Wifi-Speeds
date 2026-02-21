from __future__ import annotations

import re
import logging
import argparse
import json
from datetime import datetime
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _setup_driver(headless: bool) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
    s = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=s, options=opts)


def _numeric(text: str) -> float:
    """Extract first decimal/integer from a string."""
    match = re.search(r"[0-9]+(?:[.,][0-9]+)?", text)
    if not match:
        raise ValueError(f"No number found in: {text!r}")
    return float(match.group().replace(",", "."))


def _wait_for_nonzero(driver, locator, timeout=60) -> str:
    """Wait until an element exists and contains a non-zero number."""
    def _has_value(d):
        try:
            el = d.find_element(*locator)
            text = el.text.strip()
            val = _numeric(text)
            return text if val > 0 else False
        except Exception:
            return False

    return WebDriverWait(driver, timeout).until(_has_value)


def xfinity_test(driver) -> dict:
    log.info("Xfinity speed test starting...")
    driver.get("https://speedtest.xfinity.com/")

    start_btn = WebDriverWait(driver, 15).until(
        ec.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Start Test']"))
    )
    start_btn.click()

    log.info("Calculating download speed...")
    dl_text = _wait_for_nonzero(
        driver,
        (By.XPATH, "//dt[normalize-space()='Download speed']/following-sibling::dd"),
        timeout=60,
    )
    download = _numeric(dl_text)
    log.info("Download: %.1f Mbps", download)

    # Click "Show More" to expand the accordion that contains upload speed
    try:
        show_more = WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable((By.XPATH, "//p[normalize-space()='Show More']"))
        )
        show_more.click()
    except Exception:
        log.debug("Could not click 'Show More'; proceeding anyway")

    log.info("Calculating upload speed...")
    ul_text = _wait_for_nonzero(
        driver,
        (By.XPATH, "//dt[normalize-space()='Upload Speed']/following-sibling::dd"),
        timeout=60,
    )
    upload = _numeric(ul_text)
    log.info("Upload: %.1f Mbps", upload)

    return {"download": download, "upload": upload}


def fastdotcom_test(driver) -> dict:
    log.info("Fast.com speed test starting...")
    driver.get("https://fast.com/")

    log.info("Calculating download speed...")
    dl_text = _wait_for_nonzero(driver, (By.ID, "speed-value"), timeout=60)
    download = _numeric(dl_text)
    log.info("Download: %.1f Mbps", download)

    # Expand to show upload
    show_more = WebDriverWait(driver, 15).until(
        ec.element_to_be_clickable((By.ID, "show-more-details-link"))
    )
    show_more.click()

    log.info("Calculating upload speed...")
    ul_text = _wait_for_nonzero(driver, (By.ID, "upload-value"), timeout=60)
    upload = _numeric(ul_text)
    log.info("Upload: %.1f Mbps", upload)

    return {"download": download, "upload": upload}


def speedtestdotnet_test(driver) -> dict:
    log.info("Speedtest.net speed test starting...")
    driver.get("https://www.speedtest.net/")

    start_btn = WebDriverWait(driver, 15).until(
        ec.element_to_be_clickable((By.CSS_SELECTOR, "a.js-start-test"))
    )
    start_btn.click()

    log.info("Calculating download speed...")
    dl_text = _wait_for_nonzero(
        driver,
        (By.CSS_SELECTOR, "span.download-speed"),
        timeout=90,
    )
    download = _numeric(dl_text)
    log.info("Download: %.1f Mbps", download)

    log.info("Calculating upload speed...")
    ul_text = _wait_for_nonzero(
        driver,
        (By.CSS_SELECTOR, "span.upload-speed"),
        timeout=90,
    )
    upload = _numeric(ul_text)
    log.info("Upload: %.1f Mbps", upload)

    return {"download": download, "upload": upload}


ALL_TESTS = {
    "xfinity": ("Xfinity", xfinity_test),
    "fast": ("Fast.com", fastdotcom_test),
    "speedtest": ("Speedtest.net", speedtestdotnet_test),
}


def run_test(driver, name: str, label: str, test_fn) -> dict | None:
    try:
        result = test_fn(driver)
        log.info("%s complete — down: %.1f  up: %.1f", label, result["download"], result["upload"])
        return result
    except Exception as e:
        log.error("%s failed: %s", label, e)
        return None


def print_results(results: dict, summary: dict) -> None:
    sep = "=" * 50
    lines = [f"\n{sep}"]
    for key, label in [("xfinity", "Xfinity"), ("fast", "Fast.com"), ("speedtest", "Speedtest.net")]:
        if key not in results:
            continue
        r = results[key]
        lines.append(f" {label} Speed Test")
        lines.append(sep)
        if r is None:
            lines.append("  SKIPPED (test failed)")
        else:
            lines.append(f"  Download: {r['download']} Mbps")
            lines.append(f"  Upload:   {r['upload']} Mbps")
        lines.append(sep)

    if summary:
        lines.append(" SUMMARY")
        lines.append(sep)
        lines.append(f"  Average Download: {summary['download']:.1f} Mbps")
        lines.append(f"  Average Upload:   {summary['upload']:.1f} Mbps")
        lines.append(sep)
    else:
        lines.append("  No tests succeeded — no summary available.")
        lines.append(sep)

    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run WiFi speed tests across multiple sites.")
    parser.add_argument("--headless", action="store_true", help="Run Chrome without a visible window")
    parser.add_argument("--output", metavar="FILE", help="Save results as JSON to FILE")
    parser.add_argument(
        "--tests",
        default="xfinity,fast,speedtest",
        help="Comma-separated list of tests to run (xfinity, fast, speedtest). Default: all",
    )
    args = parser.parse_args()

    requested = [t.strip().lower() for t in args.tests.split(",")]
    unknown = [t for t in requested if t not in ALL_TESTS]
    if unknown:
        parser.error(f"Unknown test(s): {', '.join(unknown)}. Choose from: {', '.join(ALL_TESTS)}")

    log.info("Starting WiFi speed tests: %s", ", ".join(requested))
    driver = _setup_driver(args.headless)

    results = {}
    try:
        for key in requested:
            label, fn = ALL_TESTS[key]
            results[key] = run_test(driver, key, label, fn)
    finally:
        driver.quit()

    successful = {k: v for k, v in results.items() if v is not None}
    summary = {}
    if successful:
        summary = {
            "download": sum(v["download"] for v in successful.values()) / len(successful),
            "upload": sum(v["upload"] for v in successful.values()) / len(successful),
        }

    print_results(results, summary)

    if args.output:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": requested,
            "results": results,
            "summary": summary or None,
        }
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2)
        log.info("Results saved to %s", args.output)


if __name__ == "__main__":
    main()
