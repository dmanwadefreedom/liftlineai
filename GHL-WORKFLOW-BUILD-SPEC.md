# LiftlineAI - GHL Workflow Build Spec
## Build this in GHL Workflow Builder tomorrow

---

## WORKFLOW 1: "LiftlineAI - Zone Scheduling (A Clients)"

**Trigger:** Manual trigger OR Tag Added = "liftline-run-zone-1" (change per zone)

**Filter Step 1:** Contact has tag "liftline-tier-a" AND "liftline-zone-1"

**Action: Send Email**
- From Name: Toney Sebra
- Subject: Quick catch-up when I'm in {{contact.city}} next week
- Body:
```
Hi {{contact.first_name}},

I've been spending time with several of the top advisors in the region and there are a few clear themes emerging around how they're growing and positioning client portfolios in this market.

I thought it would be worthwhile to compare notes and share a quick update on where we're seeing the most traction across our strategies.

Do you have 20 minutes next week or the following?

Best,
Toney Sebra
Thornburg Investment Management
```

**Wait:** 3 days

**IF/ELSE:** Contact replied?
- YES -> Add tag "liftline-responded", trigger Workflow 4 (Response Handler)
- NO -> Send Follow-Up #1

**Follow-Up #1:**
- Subject: Re: Quick catch-up when I'm in {{contact.city}} next week
- Body:
```
Hi {{contact.first_name}}, just bumping this up - would love to find 20 minutes. What does your week look like?

Best,
Toney
```

**Wait:** 4 days

**IF/ELSE:** Contact replied?
- YES -> Add tag "liftline-responded", trigger Workflow 4
- NO -> Send Follow-Up #2

**Follow-Up #2:**
- Subject: Re: Quick catch-up when I'm in {{contact.city}} next week
- Body:
```
Hi {{contact.first_name}}, I'll try again next time I'm in your area. In the meantime, here's a quick market update worth a look.

Best,
Toney
```

**Add tag:** "liftline-cycle-complete-zone1"

---

## WORKFLOW 2: "LiftlineAI - Zone Scheduling (B Clients)"

Same structure as Workflow 1 but:
- Filter: tag "liftline-tier-b" AND "liftline-zone-1"
- Different email script (B client version):

**Email:**
```
Hi {{contact.first_name}},

I've been working with a number of advisors on practice management and prospecting strategies that are gaining traction right now, and I thought a few of these ideas might be relevant for you as well.

Happy to share what's working and hear what you're focused on this year.

Do you have 15-20 minutes next week for a quick call?

Best,
Toney Sebra
Thornburg Investment Management
```

---

## WORKFLOW 3: "LiftlineAI - Zone Scheduling (Prospects)"

Same structure but:
- Filter: tag "liftline-tier-prospect" AND "liftline-zone-1"
- Different email script (Prospect version):

**Email:**
```
Hi {{contact.first_name}},

I cover your area with Thornburg Investment Management and realized we haven't had the chance to connect yet.

I've heard great things about your practice and would appreciate the opportunity to introduce myself and learn more about your business.

If you're open to it, I'd welcome a quick 15-minute call sometime next week.

Best regards,
Toney Sebra
Thornburg Investment Management
```

---

## WORKFLOW 4: "LiftlineAI - Response Handler"

**Trigger:** Tag Added = "liftline-responded"

**Action: Internal Notification**
- Send email to toney@altawealthplans.com
- Subject: LiftlineAI - {{contact.first_name}} {{contact.last_name}} responded
- Body: "{{contact.first_name}} {{contact.last_name}} at {{contact.company_name}} ({{contact.city}}, Tier: check tags) replied to your scheduling email. Check GHL conversations to see their response and book the meeting."

**Action: Add to GHL Calendar**
- Create task: "Follow up with {{contact.first_name}} {{contact.last_name}} - schedule meeting"
- Due: Tomorrow
- Assigned to: Toney

---

## WORKFLOW 5: "LiftlineAI - Daily Report"

**Trigger:** Schedule - Every day at 5:00 PM Pacific

**Action: Send Email to Toney**
- To: toney@altawealthplans.com
- Subject: LiftlineAI Daily Report - {{date}}
- Body: (use GHL custom values or webhook to n8n to generate)
```
Daily Scheduling Report

Emails Sent Today: [count]
Responses Received: [count]
Meetings Booked: [count]
Follow-Ups Sent: [count]

Tomorrow's Schedule:
[List of confirmed meetings with times and locations]

Action Needed:
[Any responses that need manual review]

Calendar Status: [X/Y slots filled for current zone]
```

Note: This needs a webhook to an external service (n8n) to dynamically pull counts. For demo, use a static template.

---

## WORKFLOW 6: "LiftlineAI - Confirmation Call (24hr)"

**Trigger:** Appointment scheduled in GHL Calendar

**Wait:** Until 24 hours before appointment

**Action: VAPI Call**
- Webhook to VAPI API: POST https://api.vapi.ai/call/phone
- Assistant: 278eb0d4-c3c3-4055-b377-798673a0e124
- Phone: {{contact.phone}}
- Override firstMessage with: "Hey {{contact.first_name}}, this is calling on behalf of Toney Sebra at Thornburg. Just wanted to confirm your meeting tomorrow. Everything still good on your end?"

---

## HOW TO TEST TOMORROW

1. Open GHL > Workflows > Create "LiftlineAI - Zone 1 A Clients"
2. Build Workflow 1 from the spec above
3. Add trigger: Manual
4. Run it on the liftline-demo contacts
5. Michael Chen (A-tier, Zone 1) has toney@altawealthplans.com as email
6. Toney receives the scheduling email in his inbox
7. He replies - GHL captures the response
8. Response Handler notifies Toney and creates a task
9. DONE - the demo works

## DUPLICATE PER ZONE

To run Zone 2: duplicate the workflow, change the filter tag from "liftline-zone-1" to "liftline-zone-2". Same scripts, different contacts. That's it.

## DUPLICATE PER COMPANY

To run for Hartford instead of Thornburg: duplicate all workflows, change:
- "Thornburg Investment Management" to "Hartford Funds"
- Product mentions in scripts
- Toney's name to the wholesaler's name
- The master-agent-prompt.md has the full variable table
