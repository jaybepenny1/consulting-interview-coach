# Consulting Interview Coach (Google ADK, Gradio, Cloud Run)

Four agents (Coach, Researcher, Interviewer, Critic) that research a target firm, plan prep, run mock interviews and give feedback.
Built for the Agentic AI capstone, Milestone 2. See `docs/agent_reasons.md` and `docs/governance_note.md`.

## Run locally
```bash
pip install -r requirements.txt
cp .env.example .env      # then put your keys in .env, and load them: export $(grep -v '^#' .env | xargs)
python app.py             # open http://localhost:8080
python tests/test_offline.py   # dev smoke tests, no keys needed
```

## Deploy to Google Cloud Run (step by step)

**1. Make NEW keys** (never reuse keys that were pasted anywhere).
- Gemini: https://aistudio.google.com/apikey -> Create API key. Put it in a project that does NOT have billing, so the free-tier limits are a hard cost cap.
- Tavily: https://app.tavily.com -> create a new key, then delete the old one.

**2. Cloud project.** https://console.cloud.google.com -> new project (for example `coach-demo`). Link a billing account (needed even for the free tier of Cloud Run).
Claim your Google AI Pro credits at https://developers.google.com/program/my-benefits. Then Billing -> Budgets & alerts -> create a $5 budget with alerts (alerts notify; they do not stop spending).

**3. Open Cloud Shell** (the `>_` icon, top right of the console). Upload this folder (three-dot menu -> Upload) or `git clone` your repo, then `cd` into it.

**4. Turn on the services**
```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

**5. Store the keys in Secret Manager** (typing is hidden; nothing is saved in your shell history)
```bash
read -s -p "Gemini key: " K; echo; printf %s "$K" | gcloud secrets create gemini-key --data-file=-; unset K
read -s -p "Tavily key: " K; echo; printf %s "$K" | gcloud secrets create tavily-key --data-file=-; unset K
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**6. Deploy** (first build takes a few minutes; say yes if asked to create a repository)
```bash
gcloud run deploy coach --source . --region us-central1 --allow-unauthenticated \
  --max-instances 1 --min-instances 0 --concurrency 10 --memory 1Gi --cpu 1 --timeout 300 \
  --set-secrets GOOGLE_API_KEY=gemini-key:latest,TAVILY_API_KEY=tavily-key:latest
```
It prints a `https://coach-....run.app` link. Open it and test. `--max-instances 1` keeps every visitor on one instance (chat state is in memory) and bounds cost.

**7. Class day.** Remove the cold start for the demo, then put it back afterwards:
```bash
gcloud run services update coach --region us-central1 --min-instances 1   # before class
gcloud run services update coach --region us-central1 --min-instances 0   # after class
```

**8. Watch it.** Logs: `gcloud run services logs read coach --region us-central1 --limit 50`.
In Logs Explorer, filter `jsonPayload.event="injection_flag"` to collect classmates' injection attempts (raw material for Milestone III); also `ssrf_block`, `leak_blocked`, `cap_hit`, `gate_decision`.

**9. Shut down when finished**
```bash
gcloud run services delete coach --region us-central1
```
Then delete both API keys.

## Link on GitHub Pages
Push the repo, then Settings -> Pages -> Deploy from branch -> `main` and folder `/docs`. Edit `docs/index.html` and replace `CLOUD_RUN_URL` with your service link. GitHub Pages only hosts the landing page; the agent runs on Cloud Run.

## Safety limits (see `coach/config.py`)
700 output tokens per answer, 12 tool calls and 20 model calls per message, 30 messages per visitor, 300 per day overall, 1500 characters per message.
Only post the link in the Agent Arcade thread (classmates may try prompt injection there and nowhere else).
