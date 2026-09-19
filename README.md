# SDR Voice + SMS Agent (DronaHQ + Twilio)

This is the **Voice SDR Agent** and **Conversation/SMS Agent** channel for the
Inter Guild Buildathon 2026 "Autonomous SDR" build. It is a standalone
service, meant to plug into the team's main control plane as one of its
outreach channels (alongside LinkedIn and email).

## What this is

- **Voice SDR Agent**: dispatches outbound calls through a DronaHQ Voice
  Agent (DronaHQ handles the live conversation — qualifying, objection
  handling, escalation — per the agent's instructions configured in Studio).
  This service's job is orchestration: which leads to call, in what batch,
  with what per-call context, and recording the outcome.
- **Conversation Agent (SMS)**: sends the opening SMS via Twilio, and for
  every reply, asks a DronaHQ Agent (via its Webhook Trigger) what to say
  next and what to do (keep going / escalate to a human / stop / the lead
  wants a meeting).

DronaHQ is the decision-making brain for both channels. Twilio is the
telephony/SMS carrier. This service is the custom-engineered glue that
connects a dataset of leads to both of those, tracks state, and exposes
webhooks so the two systems can talk to each other and to this service.

## Architecture

```
                    ┌─────────────────────────┐
   dummy_leads.csv  │                         │
   (or control-plane│   sdr-voice-sms-agent   │
    API later)  ───▶│   (this service)        │
                    │                         │
                    └───────┬─────────┬───────┘
                            │         │
              dispatch call │         │ send SMS / read reply
                            ▼         ▼
                 ┌────────────────┐ ┌──────────┐
                 │ DronaHQ Voice  │ │  Twilio  │
                 │ Agent (SIP     │ │  SMS API │
                 │ trunk → Twilio)│ │          │
                 └───────┬────────┘ └────┬─────┘
                         │ pre/post-call  │ inbound SMS webhook
                         │ webhooks       │
                         ▼                ▼
                 ┌─────────────────────────────┐
                 │  this service's /webhooks    │
                 │  routes -> update state.json │
                 └──────────────┬──────────────┘
                                │
                                ▼
                 for each reply: POST to a DronaHQ
                 "Conversation Agent" Webhook Trigger
                 -> { message, action, lead_status }
```

## Why it's built this way (per the buildathon rubric)

- DronaHQ is genuinely load-bearing: it makes every voice-conversation and
  reply-handling decision. This service does not generate sales messages
  itself — it always asks DronaHQ's agents.
- The engineering underneath DronaHQ (this repo) is real, custom code:
  the campaign loop, the lead store, the webhook wiring between Twilio and
  DronaHQ, and mock-mode fallbacks for safe testing.
- It's designed to be called by (or plug into) the team's control plane as
  one channel of the multi-channel SDR, not a standalone demo.

## Setup

### 1. Install dependencies

Run this yourself in a normal PowerShell window (this project was scaffolded
through a bridged filesystem that can't reliably run `npm install` itself):

```powershell
cd C:\Users\ADMIN\Documents\sdr-buildathon
# if a node_modules folder already exists from a failed attempt, remove it first:
Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
npm install
```

### 2. Configure environment

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in real values as you get them (see "Getting DronaHQ credentials"
below). Everything works in **mock mode** with the placeholders left as-is
— nothing real gets sent or called until you fill in real credentials.

### 3. Getting DronaHQ credentials

1. Sign up / log in at https://agents.dronahq.com/
2. **Voice Agent**: create a Voice Agent, write its system prompt/instructions
   (qualify the lead, handle objections, offer to book a demo, escalate to a
   human if asked), and connect a phone number via SIP trunking to your
   Twilio number — Voice Agent → SIP Trunks → Add SIP Trunk (needs a Twilio
   Elastic SIP Trunk with a credential list; see Twilio Console → Elastic SIP
   Trunking). Publish the agent and copy its **Agent ID**.
3. Under the Voice Agent's **Webhooks**, set:
   - Pre-webhook (GET): `{PUBLIC_BASE_URL}/webhooks/dronahq/precall`
   - Post-webhook (POST): `{PUBLIC_BASE_URL}/webhooks/dronahq/postcall`
4. **Conversation Agent**: create a plain Agent whose job is "given a lead's
   context and their SMS reply (or blank for the first message), decide the
   next SMS to send and what to do." Add a **Webhook Trigger** to it, set its
   response type to Standard with this JSON Schema:
   ```json
   {
     "type": "object",
     "properties": {
       "message": { "type": "string" },
       "action": { "type": "string", "enum": ["send", "escalate", "stop", "book_meeting"] },
       "reason": { "type": "string" },
       "lead_status": { "type": "string" }
     },
     "required": ["message", "action", "lead_status"]
   }
   ```
   Copy the generated webhook URL and its api-key.
5. Go to **Developer → API Keys**, create a key scoped to Voice Agent (and
   Agent, if separate), and note your account's API host shown there.
6. Paste all of the above into `.env`.

### 4. Twilio

You already have a Twilio trial account. Get, from the Twilio Console:
`Account SID`, `Auth Token`, and your trial phone number. Put them in `.env`.
Trial accounts can generally only message/call numbers you've verified in
the console — verify your own phone there for real testing.

## Testing — do this in order

### A. Mock mode (no credentials needed) — do this first

This proves the whole pipeline works before anything touches a real phone.

```powershell
npm run test:sms
npm run test:voice
```

You should see `[MOCK]` log lines showing what would be sent/dialed for the
first 3 dummy leads, and `data\state.json` will appear with their saved
state. Open it and confirm each lead has a `sms_status` / `voice_status`
and a decision from the (mocked) DronaHQ agent.

### B. Run the server and hit it like the control plane would

```powershell
npm start
```

In another PowerShell window:

```powershell
# trigger SMS outreach for the whole dummy dataset
curl -X POST http://localhost:3000/api/campaigns/demo/sms/start

# trigger voice outreach for the whole dummy dataset
curl -X POST http://localhost:3000/api/campaigns/demo/voice/start

# check status
curl http://localhost:3000/api/campaigns/demo/status
curl http://localhost:3000/api/campaigns/demo/events
```

Still mock mode if you haven't filled in `.env` — safe to run repeatedly.

### C. Expose it publicly (needed for real Twilio/DronaHQ webhooks)

Twilio and DronaHQ both need to reach back into this service over the
internet, so during real testing run a tunnel:

```powershell
npx ngrok http 3000
```

Copy the `https://....ngrok-free.app` URL into `.env` as `PUBLIC_BASE_URL`,
and use `{that url}/webhooks/twilio/sms` etc. when configuring Twilio/DronaHQ
webhook fields (see setup steps above).

### D. Real SMS test (one real number first)

1. Fill in real Twilio credentials in `.env`.
2. Edit `data/dummy_leads.csv` and replace ONE row's phone number with your
   own verified number, keep the rest as dummy/mock.
3. In Twilio Console, set your number's inbound SMS webhook to
   `{PUBLIC_BASE_URL}/webhooks/twilio/sms`.
4. Restart the server (`npm start`), then:
   ```powershell
   curl -X POST http://localhost:3000/api/campaigns/demo/sms/start
   ```
5. You should receive a real text. Reply to it from your phone — the reply
   should hit `/webhooks/twilio/sms`, get sent to the DronaHQ conversation
   agent (mock or real depending on `.env`), and you should receive a
   follow-up text.

### E. Real voice test (one real number first)

1. Fill in real DronaHQ voice credentials + finish the SIP trunk/Twilio
   number setup in DronaHQ Studio (Setup step 3 above).
2. Same as above — put your own verified number in one CSV row.
3. ```powershell
   curl -X POST http://localhost:3000/api/campaigns/demo/voice/start
   ```
4. You should receive a real call from your DronaHQ Voice Agent. After it
   ends, check `data/state.json` — the lead's `voice_status` should be
   `completed` with an outcome/transcript from the post-call webhook.

## Folder structure

```
sdr-buildathon/
├── src/
│   ├── config.js          # env loading + mock/live detection
│   ├── server.js          # Express app entrypoint
│   ├── agents/
│   │   ├── voiceSdrAgent.js       # dispatch calls, pre/post-call context
│   │   └── conversationAgent.js   # SMS opener + reply handling
│   ├── dronahq/client.js  # DronaHQ Voice dispatch + Webhook Trigger calls
│   ├── twilio/client.js   # Twilio SMS send
│   ├── routes/
│   │   ├── campaigns.js   # POST .../sms/start, .../voice/start, status
│   │   └── webhooks.js    # Twilio inbound SMS, DronaHQ pre/post-call
│   └── state/
│       ├── store.js       # JSON-file lead/event store (swap for real DB)
│       └── leads.js       # CSV loader
├── data/
│   ├── dummy_leads.csv    # synthetic test dataset
│   └── state.json         # generated at runtime, gitignored
├── scripts/
│   ├── testSms.js         # mock-safe end-to-end SMS test
│   └── testVoice.js       # mock-safe end-to-end voice test
└── .env.example
```

## Known limitations / next steps

- `data/state.json` is a flat file, fine for a 51-hour demo; swap for the
  team's shared DB/CRM so the control plane sees the same lead state.
- The dummy CSV numbers are synthetic and not real phone numbers — replace
  with your own verified number(s) before any live test (Twilio trial
  accounts require verified destinations anyway).
- No retry/backoff yet on DronaHQ or Twilio API failures — add before
  relying on this for the live demo.
- Campaign registry in `routes/campaigns.js` is a hardcoded stub; wire it to
  the control plane's real campaign objects so pausing a campaign there
  actually stops this service from contacting its leads.
