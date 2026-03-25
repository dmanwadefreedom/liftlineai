# SESSION SAVE: LiftlineAI Build for Toney Sebra

> Last updated: 2026-03-26
> Session scope: CLIENT: TONEY / LIFTLINEAI
> Status: MVP in progress - core assets built, automation wiring NOT started

---

## CLIENT INFO

| Field | Value |
|-------|-------|
| Name | Toney Sebra |
| Email | toney@altawealthplans.com |
| WhatsApp | +19167996114 |
| Business | Alta Wealth Plans (rebranded to LiftlineAI) |
| Domain | LiftlineAI.com (GoDaddy - currently parked) |
| GoDaddy API Key | AZx6Gonn12c_KzndMn6DTL1tY6hN2bS852 |
| GoDaddy Secret | Mj2PHc3EiEKYJAuqgjx1Xd |
| Relationship | Freedom Code beta tester #1, The Fixer archetype |
| Personality | Organized, hates bouncing between topics, got burned by AIAA/Jordan Lee - trust matters |
| Quote | "I need a solid partner in the development side of things" |
| Separate tracks | Freedom Code course ($47) is SEPARATE from this AI build - never mix them |

---

## WHAT LIFTLINEAI IS

AI scheduling system for wholesale financial distribution reps.

**The industry:**
- Wholesalers sell insurance products (annuities), mutual funds, ETFs to financial ADVISORS (not retail investors)
- Advisors are the wholesaler's clients - warm, relationship-based
- Each rep has 150-500 advisors in their territory
- Each rep has $100K-$150K annual budget - $1,500/rep/month is nothing to them
- 20 reps = $30K/month revenue

**The problem:**
- Wholesalers waste 1-1.5 days/week on scheduling instead of selling
- Territory management is manual, inefficient
- No systematic way to prioritize high-value advisors

---

## SYSTEM ARCHITECTURE (3 LAYERS)

### Layer 1 - Email Scheduler (THE CORE - MOST IMPORTANT)
- Reads advisor database (currently Salesforce at firms)
- Territory divided into 5 zones, 20 cities
- 5-week rotation - back to same zone every 5 weeks
- Advisor segmentation:
  - A tier: $2M+ production
  - B tier: $1-2M production
  - C tier: Under $1M production
  - Prospect: No business yet
- 2 weeks before zone visit, system emails advisors to book meetings
- Priority: A clients first, B second, C third, 1-2 prospects per week
- Geography-aware - clusters meetings by location to minimize drive time
- All emails through Outlook (FINRA compliance - every message captured and auditable)
- Handles back-and-forth rescheduling

### Layer 2 - Voice Confirmation (VAPI)
- 24 hours before each meeting, AI calls the advisor
- Confirms appointment, handles rescheduling
- Updates calendar in real-time

### Layer 3 - Post-Meeting Follow-Up (BONUS ADD-ON)
- Rep speaks notes after meeting
- AI generates follow-up email through Outlook
- Voice notes to Salesforce integration

---

## TONEY'S REAL SCRIPTS (FROM HIM - USE THESE EXACTLY)

### A Client (Top tier, $2M+ production)
> "Hey [Name], it's [Your Name] - quick one for you. I've been spending a lot of time with some of the top advisors in the region, and a few consistent themes are coming up around how they're growing and positioning portfolios right now. I thought it'd be valuable to compare notes and also share a couple updates on where we're seeing flows and traction across our strategies. Do you have 20 minutes sometime next week - what does your schedule look like?"

### B Client (Mid tier, $1-2M)
> "Hi [Name], it's [Your Name]. I've been working with a number of advisors lately on some practice management and prospecting ideas that are working well right now, especially in this market environment. I thought it might be helpful to share a few of those and also get a sense for what you're focused on this year. Would you have 15 to 20 minutes sometime next week to connect?"

### Prospect (New)
> "Hi [Name], this is [Your Name] - I cover your area with [Firm]. I know we haven't connected before, but you came up as a highly regarded advisor in the territory and I wanted to introduce myself. I'd appreciate the opportunity to learn more about your practice and share how we're working with advisors in your space. Would you be open to a quick 15-minute intro call sometime next week?"

He also has email versions of each - slightly more formal.

---

## TARGET COMPANIES (RESEARCHED)

### Thornburg Investment Management (FIRST TARGET)
- $40-50B AUM
- HQ: Santa Fe, NM
- Employee-owned
- 15-25 external wholesalers
- Flagship: Income Builder Fund
- Products: munis, international value, SMAs

### Hartford Mutual Funds
- ~$130B AUM
- Sub-advisory model (Wellington)
- Pushing active ETFs

### Franklin Templeton
- ~$1.5T AUM
- Massive distribution
- Acquired Legg Mason + Putnam

### Blue Owl Capital
- ~$235B AUM
- Alternatives (private credit, GP stakes)
- Fastest growing

---

## ZONE STRUCTURE (Sacramento area for demo)

| Zone | Area |
|------|------|
| Zone 1 | Sacramento Downtown |
| Zone 2 | West Sacramento / Davis |
| Zone 3 | Roseville / Rocklin |
| Zone 4 | Folsom / El Dorado Hills |
| Zone 5 | Rancho Cordova / Elk Grove |

---

## WHAT'S BUILT (WITH FILE PATHS)

### 1. VAPI Voice Agent
- **ID:** 278eb0d4-c3c3-4055-b377-798673a0e124
- **Name:** "LiftlineAI - Wholesale Scheduler (Demo)"
- **Voice:** Priya (ElevenLabs ID: lxYfHSkYm1EzQzGhdbfc), eleven_turbo_v2_5, speed 0.95, stability 0.5, similarity 0.8
- **Brain:** claude-haiku-4-5-20251001 (Anthropic provider)
- **Transcriber:** AssemblyAI
- **Settings:** 30s silence timeout, 300s max duration, background sound off
- **End call phrases:** "goodbye", "have a good day", "take care"
- **System prompt:** Full wholesale scheduling assistant with tier-based scripts, objection handling, scheduling flow, compliance rules
- **Backups:**
  - ~/dylan-hq/backups/vapi/alta-wealth-demo-278eb0d4-20260325.json (v1)
  - ~/dylan-hq/backups/vapi/liftline-demo-278eb0d4-20260326-v2.json (v2 - latest)
- **NO phone number assigned yet** - needs one for demo calls

### 2. Landing Page
- **File:** ~/Documents/LiftlineAI/demo-landing-page.html
- **Description:** Premium dark SaaS page with "Test the AI" section
- **Phone number placeholder:** Not assigned yet - needs VAPI phone number

### 3. System Overview / Pitch Deck
- **File:** ~/Documents/LiftlineAI/liftline-system-overview.html
- **Description:** 7-section presentation covering problem, solution, flow, compliance, ROI, Thornburg-specific pitch, next steps

### 4. Email Scripts + SOPs
- **File:** ~/Documents/LiftlineAI/email-agent-scripts-sops.html
- **Description:** 7 email scripts, 7 SOPs, system architecture diagram, implementation timeline

### 5. Client Dashboard
- **File (full):** ~/Documents/LiftlineAI/toney-dashboard.html (contains secrets - NEVER deploy publicly)
- **File (public):** ~/Documents/LiftlineAI/toney-dashboard-public.html (safe version)

### 6. GHL Mock Advisors
- **Location:** Dylan's GHL (location ID: 0rTH6E3MWkHn5cjPmzLt)
- **Tags used:** liftline-zone-X, liftline-tier-X, liftline-demo, liftline-advisor
- **Status:** 21 of 50 loaded
  - Zone 1: 10/10 complete
  - Zone 2: 10/10 complete
  - Zone 3: 1/10 (Christopher Morgan only)
  - Zone 4: 0/10
  - Zone 5: 0/10

### 7. GitHub Pages
- **URL:** https://dmanwadefreedom.github.io/liftlineai/
- **Repo:** github.com/dmanwadefreedom/liftlineai
- **Branch:** main
- **Remote:** origin https://github.com/dmanwadefreedom/liftlineai.git
- **Git log:** Single commit: `620345c LiftlineAI - initial deploy: landing page, system overview, scripts/SOPs, dashboard`
- **Status:** Needs index.html for GitHub Pages to serve correctly

### 8. Local Git Repo
- **Path:** ~/Documents/LiftlineAI/
- **Files committed:**
  - demo-landing-page.html
  - email-agent-scripts-sops.html
  - liftline-system-overview.html
  - toney-dashboard-public.html
  - toney-dashboard.html

### 9. Client Files Directory
- **Path:** ~/Documents/Elevated AI/Client Files/toney/
- **Status:** Directory exists but is EMPTY - no files copied there yet

---

## WHAT'S NOT BUILT YET

### High Priority (Next session)
- [ ] Remaining 29 GHL contacts (zones 3-5) - 9 more in zone 3, 10 each in zones 4 and 5
- [ ] index.html for GitHub Pages (so dmanwadefreedom.github.io/liftlineai/ actually loads)
- [ ] VAPI phone number assignment for demo calls
- [ ] Email scheduling workflow in GHL (the actual automation)

### Medium Priority
- [ ] Google Calendar zone mapping
- [ ] Daily EOD report system
- [ ] GHL white-label sub-account for Toney
- [ ] LiftlineAI.com deployment (domain parked on GoDaddy, needs DNS pointing)
- [ ] Master system prompt for duplicatable agent per company

### Lower Priority / Phase 2
- [ ] Salesforce integration (see integration research below)
- [ ] Layer 2: Voice confirmation calls (VAPI phone number needed first)
- [ ] Layer 3: Post-meeting follow-up system
- [ ] Voice notes to Salesforce

---

## SALESFORCE / OUTLOOK INTEGRATION RESEARCH (HONEST ASSESSMENT)

### What works
- GHL has native Outlook 2-way email sync + calendar sync (this works)
- Direct Salesforce API: OAuth connected app, full CRUD, 100K+ daily calls on Enterprise
- Microsoft Graph API: can send email as user, read/write calendar

### What doesn't work (yet)
- GHL has NO native Salesforce integration (GHL positions itself as Salesforce replacement)
- Zapier/Make.com can bridge GHL to Salesforce but it's basic (contact sync, event-based, not real-time)

### The deal breaker
- Financial firms probably WON'T give a startup API access to their Salesforce or Outlook without SOC 2, security questionnaires, vendor review (4-12 weeks minimum)
- Need a champion inside the firm to push it through

### Realistic path forward
1. GHL as primary CRM
2. Use native Outlook sync
3. Manual Salesforce CSV import/export
4. Don't try to integrate directly into corporate Salesforce until there's traction and compliance creds
5. DJ (CISSP-ISSMP certified) can help with compliance verification when needed

---

## PRODUCT ARCHITECTURE DECISION

- GHL white-label agency model recommended
- Toney gets agency account
- Each company = sub-account
- Each wholesaler = user login
- Custom dashboard at LiftlineAI.com pulls from GHL API
- Company-specific AI prompts per sub-account
- Add-ons: voice confirmation, post-meeting follow-up, voice notes to Salesforce
- Dylan gets build fee + ~20% revenue share

---

## TONEY'S FULL APP PIPELINE (5 PRODUCTS)

1. **AI Auto Scheduler (THIS BUILD)** - email booking with Outlook + Salesforce
2. **Voice-to-Email Follow-Up** - speak notes, AI generates follow-up email
3. **Monthly Wrap-Up Report** - pulls financial data, sends monthly summary
4. **Realtor Version** - same system for RE. Buddy has 2nd largest RE coaching biz in country + national speaking circuit
5. **Logistics Prospecting** - DoD, US currency transport, sports/entertainment, tradeshows

---

## EMAILS SENT TO TONEY

1. **"Where we stand - clear version"** - personal track, Freedom Code, quiz explanation (in Gmail drafts)
2. **"Tonight - Voice Agent Build (Action Steps)"** - updated with his real answers (in Gmail drafts)
3. **WhatsApp questions sent via JARVIS** - BROKE - sent AI confusion messages instead of actual content

---

## FATHOM TRANSCRIPTS (Toney calls)

| Date | Session |
|------|---------|
| 2026-03-02 | Quiz session |
| 2026-03-10 | Freedom Code Day 1 |
| 2026-03-24 | AI app build session (in Gmail) |

---

## KEY RELATIONSHIPS & CONTEXT

- Shane (Dylan's wife) noted the Freedom Code course benefits aren't clear enough
- Toney's buddy has the 2nd largest RE coaching biz in the country + national speaking circuit = MASSIVE distribution potential for Realtor version
- Conor and Akshaya are PARTNERS, not clients - Toney is a client
- Freedom Code and AI build are TWO SEPARATE TRACKS - never mix them in conversations with Toney

---

## RESUME INSTRUCTIONS FOR NEXT SESSION

1. State scope: **CLIENT: TONEY / LIFTLINEAI**
2. Read this file first: `~/Documents/LiftlineAI/SESSION-SAVE-LIFTLINEAI.md`
3. Check GHL for current contact count (may have changed): search tag `liftline-demo`
4. Priority tasks in order:
   a. Finish remaining 29 GHL mock advisors (zones 3-5)
   b. Create index.html for GitHub Pages deployment
   c. Wire up email scheduling workflow in GHL
   d. Get VAPI phone number assigned for demo
5. Do NOT touch: Dylan's other client systems, JARVIS, OpenClaw, any other GHL locations
6. Keys location: `~/.dylan-keys/.env` (grep only, never source)
7. GHL Location ID (Dylan's): `0rTH6E3MWkHn5cjPmzLt`

---

## FILE INVENTORY

```
~/Documents/LiftlineAI/
  demo-landing-page.html          # Landing page with "Test the AI" section
  email-agent-scripts-sops.html   # 7 scripts + 7 SOPs + architecture
  liftline-system-overview.html   # 7-section pitch deck
  toney-dashboard.html            # Full dashboard (HAS SECRETS - never deploy public)
  toney-dashboard-public.html     # Safe dashboard version
  SESSION-SAVE-LIFTLINEAI.md      # THIS FILE
  .git/                           # Repo: dmanwadefreedom/liftlineai

~/dylan-hq/backups/vapi/
  alta-wealth-demo-278eb0d4-20260325.json    # VAPI backup v1
  liftline-demo-278eb0d4-20260326-v2.json    # VAPI backup v2 (latest)

~/Documents/Elevated AI/Client Files/toney/  # Empty - nothing copied here yet
```

---

## PRICING MODEL

| Metric | Value |
|--------|-------|
| Per rep/month | $1,500 |
| Rep annual budget | $100K-$150K |
| 20 reps target | $30K/month |
| Dylan's cut | Build fee + ~20% revenue share |
