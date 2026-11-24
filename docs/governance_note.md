# Governance note: Consulting Interview Coach (updated for Milestone 3)

**Accountable person:** Jaybe Penny (jaybepenny@gmail.com). One named owner for what this agent does and for shutting it down.

**Data read and stored, and where.** The agent reads only what a visitor types, plus public web pages the Researcher fetches. Nothing real
is connected: no email, payments, deletions or company data. Visitor messages are sent to Google's Gemini API, and search queries to
Tavily. A spoken answer is recorded in the browser, sent to Gemini to be turned into text, and the recording is deleted from the server as soon as it has been read; the visitor edits the text before sending. Webcam recordings stay in the visitor's browser tab and are never uploaded. A visitor's profile, firm brief, plan, stories and practice history are stored as small files in a per-visitor folder on the
Cloud Run instance's temporary disk (not a database). They are erased by the "Delete my data" button, after 24 hours of inactivity (swept when the next visitor arrives),
or when the instance restarts. Cloud Logging keeps event records (who/what/when, tool names, sizes); the text of a message is
logged only when it trips the injection detector (first 300 characters). API keys live in Google Secret Manager and reach the app as
environment variables, never in the UI, repo or recording.

**Human gate.** The action is `save_brief` (the Researcher saving the firm brief). It sits between the Researcher's web research and the
Coach building a plan from the saved brief. Before it runs, the chat shows an approval card with the tool name and the full, exact
arguments (the whole brief text with its source links) and Approve / Reject buttons; the text box is locked until the visitor decides.
Reject saves nothing. The brief is also machine-checked first: it must cite only URLs the tools actually returned.

**What a stranger can and cannot make the agent do.** They can chat (typed or spoken), run and stop mock interviews, and make the Researcher search the web and read the pages its own search returned. They cannot read other visitors' data, make the agent open a URL it did not get from its own search (so it cannot be told to send data to an address), make it display an image from a URL it chose, make the agent fetch internal or private addresses (private, loopback and cloud
metadata addresses and non-web schemes are blocked, including after redirects), get the answer key (instructions plus an output filter),
change the agent's rules, or obtain keys. Spend is capped: 1,500 output tokens per answer, 20 tool calls and 30 model calls per message,
30 messages per visitor, 300 messages per day across everyone, one instance. These guards are pattern-based and are not guarantees;
Milestone III will test them with the injection attempts collected from the logs.

**Interface update (Milestone III).** (1) *Read replies aloud* uses the visitor's own browser text-to-speech; the reply text is not sent to any speech service, and it is off by default. (2) *My documents* is view-only: a dropdown limited to the visitor's own firm brief, prep plan and story bank (fixed names, no typed paths), cleaned the same way as chat replies (images and active HTML removed). The download link is built inside the page, so no file is served from the server, and the interface has no file-upload control. (3) The approval card now shows the brief as readable text with links displayed as the site name; the exact text with full links is one click away, so what is saved is still fully visible before approval. The site name is computed from the real URL, never from the model's label. (4) A line under the voice recorder links to the GSU Consulting Club website (opens in a new tab; no data is sent).
