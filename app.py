"""Entry point for Cloud Run. Keys come from environment variables only."""
import os
from coach import ui, config

if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
    print("WARNING: GOOGLE_API_KEY is not set; model calls will fail.")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

demo = ui.build_demo()

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2, max_size=20).launch(
        server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 8080)),
        share=False)
