# Why more than one agent? (Week 9 four reasons)

**Claim: reason 2, permission isolation.** The system has four agents (Coach, Researcher, Interviewer, Critic) because
the work needs three different sets of powers that should never sit in one place:

| Agent | Can do | Cannot do |
|---|---|---|
| Researcher | search the web, fetch public pages, write the firm brief (only after a human approves the exact text) | see the answer keys, run interviews, grade |
| Interviewer | read the case answer key, run the session | use the network, save briefs or profiles |
| Critic | read the transcript and the answer key, write graded results to memory | use the network, run interviews |
| Coach | talk to the candidate, save profile, plan and stories | use the network, see any answer key |

Why it matters here: the Researcher reads untrusted web pages, which can contain prompt injection. If that same agent also held the
answer key or the ability to change the candidate's profile, a malicious page could try to make it leak or overwrite them.
Splitting the powers means a hijacked Researcher still has no answer key and no way to run or grade interviews, and its one write
(the brief) needs a human click. `tests/test_offline.py` checks the split: network tools appear only on the Researcher, answer-key
tools only on the Interviewer and Critic, and the Coach has neither.

**Not claimed**
- Reason 1, context isolation: the Interviewer needs the whole dialogue, so its context is not kept separate. Not claimed.
- Reason 3, parallel breadth: the agents run one at a time. Not claimed.
- Reason 4, team ownership: one person owns everything. Not claimed.

**What changed from Milestone 1:** the earlier build had six agents. The Planner and Writer did not pass the test (same tools
and permissions as the Coach, no isolation benefit), so they were folded into the Coach.
