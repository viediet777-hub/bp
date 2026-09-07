"""
Gemini Link Checker (Google Gemini / JioGemini)
================================================
Links dalo — valid hai ya used hai pata chalega.

Usage:
  python gemini_checker.py              # interactive
  python gemini_checker.py links.txt    # file se
"""

import requests
import re
import sys
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
}

# Google ke subscription links ye hota hain
GOOGLE_GEMINI_PATTERNS = [
    "serviceactivation.google.com",
    "gemini.google.com",
    "one.google.com",
    "play.google.com",
]

# Jio ke links
JIO_PATTERNS = [
    "jio.com",
    "jiofinance",
    "jiopay",
    "looters.shop",
]


def detect_link_type(url):
    url_lower = url.lower()
    for pat in GOOGLE_GEMINI_PATTERNS:
        if pat in url_lower:
            return "google_gemini"
    for pat in JIO_PATTERNS:
        if pat in url_lower:
            return "jio"
    return "unknown"


def check_google_gemini(url):
    """Google Gemini links check karo — login page se判断"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        final_url = r.url
        status = r.status_code
        body = r.text
        body_lower = body.lower()

        if status == 404:
            return "DEAD", "Link expired/not found (404)"

        if status == 403:
            return "BLOCKED", "Blocked by Google (403)"

        # Google sign-in page redirect = link valid hai, login chahiye
        if "accounts.google.com" in final_url or "signin" in body_lower[:5000]:
            # Check for specific error messages
            if "not found" in body_lower or "doesn't exist" in body_lower:
                return "DEAD", "Link does not exist"
            if "already been redeemed" in body_lower or "already used" in body_lower:
                return "USED", "Already redeemed"
            if "expired" in body_lower and "link" in body_lower:
                return "USED", "Link expired"
            # Agar login page aa raha hai = link VALID hai
            return "FRESH", "Link valid — needs Google login to claim"

        if status == 200:
            # Check if it's a direct claim page
            if "claim" in body_lower or "subscribe" in body_lower or "premium" in body_lower:
                return "FRESH", "Link valid — can claim directly!"
            # Check for success indicators
            if "congratulations" in body_lower or "activated" in body_lower:
                return "USED", "Already activated"
            return "UNKNOWN", f"Status 200 — check manually (redirected to: {final_url[:60]})"

        return "ERROR", f"Status {status}"

    except requests.exceptions.Timeout:
        return "TIMEOUT", "Google server slow"
    except requests.exceptions.ConnectionError:
        return "CON_ERROR", "Connection failed"
    except Exception as e:
        return "ERROR", str(e)[:80]


def check_jio_link(url):
    """Jio/Gemini links check karo"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            text = r.text.lower()
            if "already been used" in text or "redeemed" in text or "expired" in text:
                return "USED", "Already used/redeemed"
            elif "claim" in text or "reward" in text or "cashback" in text:
                return "FRESH", "Valid — can claim!"
            return "UNKNOWN", "Status 200 — check manually"
        elif r.status_code == 404:
            return "DEAD", "Link expired (404)"
        return "ERROR", f"Status {r.status_code}"
    except Exception as e:
        return "ERROR", str(e)[:80]


def check_link(url):
    url = url.strip()
    if not url:
        return None, "Empty"

    link_type = detect_link_type(url)

    if link_type == "google_gemini":
        return check_google_gemini(url)
    elif link_type == "jio":
        return check_jio_link(url)
    else:
        # Unknown — try generic check
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return "UNKNOWN", "Unknown link type — check manually"
            elif r.status_code == 404:
                return "DEAD", "Not found (404)"
            return "ERROR", f"Status {r.status_code}"
        except Exception as e:
            return "ERROR", str(e)[:80]


def extract_links(text):
    return re.findall(r'https?://[^\s<>"]+', text)


def check_batch(links):
    print(f"\n🔍 Checking {len(links)} link(s)...\n")
    print("-" * 55)

    fresh = 0
    used = 0
    dead = 0
    unknown = 0
    errors = 0
    results = []

    for i, url in enumerate(links, 1):
        url = url.strip()
        if not url:
            continue

        link_type = detect_link_type(url)
        type_icon = {"google_gemini": "💎", "jio": "📱"}.get(link_type, "🔗")

        status, detail = check_link(url)
        if not status:
            continue

        if status == "FRESH":
            icon = "🟢"
            fresh += 1
        elif status == "USED":
            icon = "🔴"
            used += 1
        elif status == "DEAD":
            icon = "⚫"
            dead += 1
        elif status == "UNKNOWN":
            icon = "🟡"
            unknown += 1
        else:
            icon = "🟠"
            errors += 1

        print(f"  {icon} {type_icon} [{i}/{len(links)}] {status}")
        print(f"     {url[:70]}")
        print(f"     {detail}")
        print()

        results.append({"url": url, "status": status, "detail": detail, "type": link_type})

        if i < len(links):
            time.sleep(1)

    # Summary
    print("=" * 55)
    print("  📊 SUMMARY")
    print("=" * 55)
    print(f"  🟢 FRESH:    {fresh}")
    print(f"  🔴 USED:     {used}")
    print(f"  ⚫ DEAD:     {dead}")
    print(f"  🟡 UNKNOWN:  {unknown}")
    print(f"  🟠 ERRORS:   {errors}")
    print(f"  📱 TOTAL:    {len(links)}")
    print("=" * 55)

    if fresh > 0:
        save = input("\n💾 Save FRESH links to file? (y/n): ").strip().lower()
        if save == "y":
            fname = "fresh_links.txt"
            with open(fname, "a", encoding="utf-8") as f:
                for r in results:
                    if r["status"] == "FRESH":
                        f.write(f"{r['url']}\n")
            print(f"  ✅ Saved to {fname}")

    if unknown > 0:
        print("\n💡 UNKNOWN links = login required. Open in browser to check.")


def main():
    print("=" * 55)
    print("  🔍 GEMINI LINK CHECKER")
    print("  💎 Google Gemini | 📱 Jio | 🔗 Other")
    print("=" * 55)

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            links = extract_links(content)
            print(f"\n📁 {len(links)} links found in {filename}")
            check_batch(links)
        except FileNotFoundError:
            print(f"❌ File not found: {filename}")
        return

    print("\n📋 Options:")
    print("  1. Paste links (one per line)")
    print("  2. Paste single link")
    print("  3. Load from file")
    print("  4. Quit")

    while True:
        try:
            choice = input("\n👉 Choose (1-4): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if choice == "1":
            print("\n📋 Paste links (empty line to finish):")
            links = []
            while True:
                try:
                    line = input("  > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not line:
                    break
                found = extract_links(line)
                links.extend(found)
                if not found:
                    print("    ⚠️ No link found")
            if links:
                check_batch(links)

        elif choice == "2":
            try:
                url = input("\n🔗 Paste link: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            links = extract_links(url)
            if links:
                check_batch(links)
            else:
                print("  ❌ No valid link")

        elif choice == "3":
            try:
                filename = input("\n📁 File path: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                links = extract_links(content)
                print(f"  Found {len(links)} links")
                if links:
                    check_batch(links)
            except FileNotFoundError:
                print(f"  ❌ Not found: {filename}")

        elif choice == "4":
            print("Bye!")
            break
        else:
            print("  ❌ Invalid")


if __name__ == "__main__":
    main()
