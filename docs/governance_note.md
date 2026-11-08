# Governance note: Consulting Interview Coach (Milestone 2)

**Accountable person:** Jaybe Penny (jaybepenny@gmail.com). One named owner for what this agent does and for shutting it down.

**Data read and stored, and where.** The agent reads only what a visitor types, plus public web pages the Researcher fetches. Nothing real
is connected: no email, payments, deletions or company data. Visitor messages are sent to Google's Gemini API, and search queries to
Tavily. A visitor's profile, firm brief, plan, stories and practice history are stored as small files in a per-visitor folder on the
Cloud Run instance's temporary disk (not a database). They are erased by the "Delete my data" button, after 24 hours of inactivity (swept when the next visitor arrives),
or when the instance restarts. Cloud Logging keeps event records (who/what/when, tool names, sizes); the text of a message is
logged only when it trips the injection detector (first 300 characters). API keys live in Google Secret Manager and reach the app as
environment variables, never in the UI, repo or recording.

**Human gate.** The action is `save_brief` (the Researcher saving the firm brief). It sits between the Researcher's web research and the
Coach building a plan from the saved brief. Before it runs, the chat shows an approval card with the tool name and the full, exact
arguments (the whole brief text with its source links) and Approve / Reject buttons; the text box is locked until the visitor decides.
Reject saves nothing. The brief is also machine-checked first: it must cite only URLs the tools actually returned.

**What a stranger can and cannot make the agent do.** They can chat, run mock interviews, and make the Researcher search and read public
web pages. They cannot read other visitors' data, make the agent fetch internal or private addresses (private, loopback and cloud
metadata addresses and non-web schemes are blocked, including after redirects), get the answer key (instructions plus an output filter),
change the agent's rules, or obtain keys. Spend is capped: 700 output tokens per answer, 12 tool calls and 20 model calls per message,
30 messages per visitor, 300 messages per day across everyone, one instance. These guards are pattern-based and are not guarantees;
Milestone III will test them with the injection attempts collected from the logs.
