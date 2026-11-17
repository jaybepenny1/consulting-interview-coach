"""Optional: drives the real page in headless Chromium with a FAKE camera and microphone.
Needs `pip install playwright && playwright install chromium`. Not part of the graded harness."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coach import config
config.DATA_DIR = Path(tempfile.mkdtemp(prefix="brtest_")) / "d"
config.MIN_SECONDS_BETWEEN_CALLS = 0
import test_offline as t
from coach import ui, runtime
from playwright.sync_api import sync_playwright

async def fake_tr(data, mime):
    return f"spoken answer ({len(data)} bytes, {mime})"

demo = ui.build_demo(runtime.Hub(model=t.build(), transcriber=fake_tr))
demo.queue()
_, url, _ = demo.launch(prevent_thread_lock=True, server_name="127.0.0.1", server_port=7871, share=False, quiet=True, **ui.LAUNCH_KWARGS)
shots = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    ctx = b.new_context(viewport={"width": 1320, "height": 1500}, permissions=["camera", "microphone"])
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url); pg.wait_for_selector("#hero")
    assert pg.locator(".who-coach").count() >= 1, "agent color chip was stripped from the chat"
    # chat round trip
    box = pg.get_by_placeholder("Type a message, or a command like /case operations")
    box.fill("Hi"); box.press("Enter")
    pg.wait_for_function("document.body.innerText.includes('COACH welcome')", timeout=20000)
    print("OK   page loads, themed header present, chat round trip works")
    # webcam (browser only)
    pg.get_by_text("Record yourself on camera").click()
    pg.wait_for_selector("#cam-start", state="visible")
    pg.click("#cam-start")
    pg.wait_for_function("document.getElementById('cam-stop').disabled === false", timeout=15000)
    pg.wait_for_timeout(1500)
    pg.click("#cam-stop")
    pg.wait_for_function("(document.getElementById('cam-play').src || '').startsWith('blob:')", timeout=15000)
    assert pg.locator("#cam-dl").is_visible() and pg.get_attribute("#cam-dl", "href").startswith("blob:")
    print("OK   webcam: records, plays back from a blob: URL in the tab, download link shown")
    # microphone -> transcription -> text box
    pg.locator("#voice").get_by_role("button", name="Record", exact=True).click()
    pg.wait_for_timeout(2500)
    pg.locator("#voice").get_by_role("button", name="Stop", exact=True).locator("visible=true").first.click()
    pg.wait_for_function("Array.from(document.querySelectorAll('textarea')).some(x => x.value.includes('spoken answer'))", timeout=20000)
    val = pg.evaluate("Array.from(document.querySelectorAll('textarea')).map(x => x.value).find(v => v.includes('spoken answer'))")
    print("OK   microphone: recording transcribed into the message box ->", val)
    pg.screenshot(path=str(shots / "page.png"), full_page=True)
    assert not errors, errors
    b.close()
demo.close()
print("BROWSER TEST OK; screenshot:", shots / "page.png")
