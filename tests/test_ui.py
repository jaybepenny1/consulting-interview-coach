"""Starts the real Gradio server with a scripted model and drives it through gradio_client."""
import sys, asyncio, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coach import config
config.DATA_DIR = Path(tempfile.mkdtemp(prefix="uitest_")) / "d"
config.MIN_SECONDS_BETWEEN_CALLS = 0
import test_offline as t   # runs offline checks first (also installs the mocks)
from coach import ui, runtime
from gradio_client import Client

demo = ui.build_demo(runtime.Hub(model=t.build()))
demo.queue(default_concurrency_limit=2)
_, url, _ = demo.launch(prevent_thread_lock=True, server_name="127.0.0.1", share=False, quiet=True)
c = Client(url, verbose=False)
r = c.predict(message="Hi", history=[], api_name="/respond")
print("client got", len(r[0]), "chat messages")
assert any("COACH welcome" in str(m) for m in r[0])
demo.close()
print("UI SERVER TEST OK")

demo2 = ui.build_demo(runtime.Hub(model=t.build()))
demo2.queue()
_, url2, _ = demo2.launch(prevent_thread_lock=True, server_name="127.0.0.1", server_port=7861, share=False, quiet=True)
c2 = Client(url2, verbose=False)
c2.predict(message="Hi", history=[], api_name="/respond")
r = c2.predict(message="Bain ACI, 10 days, beginner", history=[], api_name="/respond")
gate_text, left = r[4], r[5]
assert "Approval needed" in gate_text and "save_brief" in gate_text and "https://www.bain.com/careers/x" in gate_text
assert r[3].get("interactive") is False
print("GATE CARD OK (visible, exact args shown, textbox locked); counter:", left)
demo2.close()
