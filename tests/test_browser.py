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
    ctx.add_init_script("""
      window.__said = [];
      Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
        speak: function (u) { window.__said.push(u.text); }, cancel: function () {}, getVoices: function () { return []; } } });
      window.SpeechSynthesisUtterance = function (t) { this.text = t; };
    """)
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
    # layout: camera panel sits beside the chat (top of the right column), examples are below it
    chat_box = pg.locator(".bubble-wrap, [aria-label='chatbot conversation'], .chatbot").first.bounding_box()
    cam_top = pg.locator("#cam-box").bounding_box()
    ex_top = pg.get_by_text("Try an example").bounding_box()
    assert cam_top["y"] < ex_top["y"] and chat_box["y"] <= cam_top["y"] <= chat_box["y"] + chat_box["height"], (chat_box, cam_top, ex_top)
    print("OK   layout: the camera panel is next to the chat box, above the examples and quick actions")
    # club plug sits right under the "Speak your answer" recorder (above the Transcribed note), opens in a new tab
    plug = pg.locator("#club-plug a")
    assert plug.get_attribute("href") == "https://www.consultingclubgsu.com/" and plug.get_attribute("target") == "_blank"
    pl, vc = pg.locator("#club-plug").bounding_box(), pg.locator("#voice").bounding_box()
    assert pl["y"] >= vc["y"] + vc["height"] - 5, (pl, vc)
    assert pl["y"] < pg.get_by_text("Messages left in this session").bounding_box()["y"]
    assert pl["y"] > chat_box["y"] + chat_box["height"], "plug must no longer sit right under the chat"
    print("OK   Consulting Club plug sits under the voice recorder and links to the club site in a new tab")
    assert pg.locator("input[type=file]").count() == 0, "no file upload control may exist"
    print("OK   there is no file-upload control anywhere on the page")
    # webcam (browser only)
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
    note = pg.get_by_text("Transcribed. Check the text").bounding_box()
    pl = pg.locator("#club-plug").bounding_box()
    assert pl["y"] + pl["height"] <= note["y"] + 2, (pl, note)
    print("OK   after a recording, the plug is between the recorder and the 'Transcribed. Check the text' note")
    # approval card: readable (no sideways scrolling), site-name links, exact text one click away
    box.fill("Bain ACI, 10 days, beginner"); box.press("Enter")
    pg.wait_for_selector("#gate-text", state="visible", timeout=30000)
    pg.wait_for_function("document.querySelector('#gate-text').innerText.includes('Approval needed')", timeout=30000)
    g = pg.evaluate("(() => { const e = document.querySelector('#gate-text'); return {sw: e.scrollWidth, cw: e.clientWidth, txt: e.innerText}; })()")
    assert g["sw"] <= g["cw"] + 2, g
    assert pg.locator("#gate-text a", has_text="bain.com").count() >= 1
    pg.locator("#gate-text summary").click()
    assert "https://www.bain.com/careers/x" in pg.locator("#gate-text").inner_text()
    g2 = pg.evaluate("(() => { const e = document.querySelector('#gate-text'); return [e.scrollWidth, e.clientWidth]; })()")
    assert g2[0] <= g2[1] + 2, g2
    pg.screenshot(path=str(shots / "gate.png"), full_page=True)
    print("OK   approval card: no sideways scrolling, links shown as site names, exact text with full links on demand")
    # approve -> document appears in the view-only dropdown, with a working download
    pg.get_by_role("button", name="Approve and save").click()
    pg.wait_for_function("document.querySelector('#doc-view') && document.querySelector('#doc-view').innerText.includes('Interview Format')", timeout=40000)
    assert pg.locator("#doc-view a", has_text="bain.com").count() >= 1
    with pg.expect_download() as dl:
        pg.locator("a.dl-btn").click()
    d = dl.value
    saved = Path(d.path()).read_text()
    assert d.suggested_filename == "firm-brief.md" and "https://www.bain.com/careers/x" in saved
    print("OK   documents: the approved brief appears in the dropdown viewer and downloads with its full links")
    # read aloud: off by default, speaks only when switched on; links and tables are not read out
    assert pg.evaluate("window.__said.length") == 0
    hist = [{"role": "assistant", "content": "old"},
            {"role": "assistant", "content": '<span class="who who-coach">Coach</span>\n\nHello **there**. See [Bain](https://www.bain.com/x) now.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nDone.'}]
    pg.evaluate("window.__said.length = 0; window.__spoken = 1")
    pg.evaluate("(h) => window.coachSpeak(h, true)", hist)
    said = " ".join(pg.evaluate("window.__said"))
    assert "Hello there." in said and "http" not in said and "|" not in said and "Bain" in said, said
    pg.evaluate("window.__said.length = 0")
    pg.evaluate("(h) => window.coachSpeak(h, false)", hist + [{"role": "assistant", "content": "c"}])
    assert pg.evaluate("window.__said.length") == 0
    pg.locator("#speak-toggle input[type=checkbox]").check()
    box.fill("Hi again"); box.press("Enter")
    pg.evaluate("(() => { const o = window.coachSpeak; window.__calls = []; window.coachSpeak = function (h, on) { window.__calls.push(JSON.stringify([h && h.length, on, h && h.slice(-1)[0]]).slice(0, 400)); return o(h, on); }; })()")
    box.fill("Hi once more"); box.press("Enter")
    try:
        pg.wait_for_function("window.__said.length > 0", timeout=20000)
    except Exception:
        print("DEBUG calls:", pg.evaluate("window.__calls"), "spoken idx:", pg.evaluate("window.__spoken"))
        raise
    print("OK   read aloud: silent when off; when on it speaks new replies, without links or table rows")
    pg.screenshot(path=str(shots / "page.png"), full_page=True)
    assert not errors, errors
    b.close()
demo.close()
print("BROWSER TEST OK; screenshot:", shots / "page.png")
