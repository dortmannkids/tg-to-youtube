"""
Standalone TikTok upload via Playwright.
Called as subprocess: python3 tiktok_upload_pw.py <filepath> <description> <sessionid>
Exit 0 = success, 1 = failure.
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def dismiss_overlays(page):
    try:
        page.evaluate("""
            ['[data-test-id="overlay"]', '#react-joyride-portal', 'tiktok-cookie-banner'].forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });
        """)
    except Exception:
        pass

def upload(filepath: str, description: str, sessionid: str) -> bool:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        ctx.add_cookies([
            {"name": "sessionid", "value": sessionid, "domain": ".tiktok.com", "path": "/"},
            {"name": "sessionid_ss", "value": sessionid, "domain": ".tiktok.com", "path": "/"},
        ])
        page = ctx.new_page()

        print("Navigating to upload page...")
        page.goto("https://www.tiktok.com/creator-center/upload?lang=en", timeout=30000, wait_until="load")
        time.sleep(4)

        # Check if redirected to login
        if "login" in page.url:
            print(f"ERROR: Redirected to login — sessionid invalid. URL: {page.url}")
            browser.close()
            return False

        print(f"Upload page loaded: {page.url}")
        dismiss_overlays(page)
        time.sleep(2)

        # Upload file
        print("Uploading file...")
        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(filepath)
        time.sleep(5)

        dismiss_overlays(page)

        # Wait for video to process
        print("Waiting for video processing...")
        for _ in range(30):
            time.sleep(2)
            dismiss_overlays(page)
            # Check if upload finished (post button enabled or processing indicator gone)
            try:
                caption_el = page.locator("div[contenteditable='true']").first
                if caption_el.is_visible(timeout=1000):
                    break
            except Exception:
                pass

        dismiss_overlays(page)
        time.sleep(2)

        # Set description
        print(f"Setting description: {description}")
        try:
            caption_el = page.locator("div[contenteditable='true']").first
            caption_el.click(force=True)
            time.sleep(0.5)
            # Clear and type
            caption_el.evaluate("el => el.innerText = ''")
            caption_el.type(description, delay=30)
            time.sleep(1)
        except Exception as e:
            print(f"WARNING: Could not set description: {e}")

        dismiss_overlays(page)

        # Click Post to publish
        print("Clicking Post...")
        dismiss_overlays(page)
        try:
            post_btn = page.locator("button[data-e2e='post_video_button']")
            post_btn.click(timeout=15000)
        except Exception as e:
            print(f"WARNING: Post click failed: {e}")

        # After successful publish, TikTok shows "Posts N" in page header within ~2 seconds
        success = False
        for _ in range(15):
            time.sleep(1)
            try:
                header_text = page.locator("text=/Posts \\d+/").first.inner_text(timeout=500)
                import re
                n = int(re.search(r'\d+', header_text).group())
                if n > 0:
                    print(f"Success: header shows '{header_text}'")
                    success = True
                    break
            except Exception:
                pass

        print(f"Final URL: {page.url}")
        print(f"Success: {success}")

        browser.close()
        return success


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 tiktok_upload_pw.py <filepath> <description> <sessionid>")
        sys.exit(1)
    ok = upload(sys.argv[1], sys.argv[2], sys.argv[3])
    sys.exit(0 if ok else 1)
