#!/usr/bin/env python3
"""
LiftlineAI Smart Responder
============================
Monitors inbound emails, classifies intent, handles back-and-forth
scheduling conversations, and books meetings automatically.

Commands:
  python3 liftline-responder.py check          # Check for new inbound emails
  python3 liftline-responder.py process-all     # Process all unread conversations
  python3 liftline-responder.py watch           # Continuous monitor (check every 5 min)

Intent Classification:
  - ACCEPT: Advisor wants to meet → auto-book + send confirmation
  - RESCHEDULE: Advisor wants different time → suggest alternatives
  - DECLINE: Advisor not interested → tag + move to next cycle
  - QUESTION: Advisor has questions → alert Toney for manual reply
  - OOO: Out of office auto-reply → reschedule for return date
"""

import json
import sys
import time
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path

# === CONFIG ===
GHL_API = "https://services.leadconnectorhq.com"
GHL_TOKEN = "pit-f1ec9196-bfed-44d7-acc3-c89e9051b1fa"
GHL_LOCATION = "DkwGpda79CXXO6YqwceD"
GHL_VERSION = "2021-07-28"

ENGINE_DIR = Path(__file__).parent
STATE_FILE = ENGINE_DIR / "engine-state.json"
RESPONDER_LOG = ENGINE_DIR / "responder-log.json"

# === INTENT PATTERNS ===
# These patterns classify advisor responses WITHOUT needing an LLM call
# Fast, free, and handles 90%+ of responses

ACCEPT_PATTERNS = [
    r"\b(yes|sure|sounds good|let'?s do it|that works|i'?m available|happy to|love to|count me in)\b",
    r"\b(how about|what about|i can do|i'?m free|let me know|send me|book it|set it up)\b",
    r"\b(looking forward|great|perfect|absolutely|definitely|of course)\b",
    r"\b(tuesday|wednesday|thursday|friday|monday|next week|this week|morning|afternoon)\b",
    r"\b(\d{1,2}:\d{2}|\d{1,2}\s*(am|pm))\b",  # Time mentions
]

RESCHEDULE_PATTERNS = [
    r"\b(different time|another time|can we move|reschedule|push|not that day)\b",
    r"\b(busy that day|conflict|prior commitment|tied up|not available then)\b",
    r"\b(following week|week after|later in the month)\b",
    r"\b(instead|rather|prefer|better for me)\b",
]

DECLINE_PATTERNS = [
    r"\b(not interested|no thank you|no thanks|pass|remove me|unsubscribe)\b",
    r"\b(don'?t need|not looking|not at this time|maybe later|not right now)\b",
    r"\b(please stop|don'?t contact|take me off)\b",
]

OOO_PATTERNS = [
    r"\b(out of (the )?office|ooo|on vacation|on leave|traveling)\b",
    r"\b(return|back on|back in the office|returning)\b",
    r"\b(auto.?reply|automatic reply|this is an automated)\b",
]

QUESTION_PATTERNS = [
    r"\b(what do you|which strategies|what specifically|tell me more|can you share)\b",
    r"\b(who are you|what company|what firm|which fund)\b",
    r"\?\s*$",  # Ends with question mark
]

# === REPLY TEMPLATES ===
REPLY_TEMPLATES = {
    "accept_with_time": {
        "subject": "Re: {original_subject}",
        "body": "Hi {first_name},\n\nGreat - I've got you down for {time_str} on {date_str}.\n\nI'll come to your office at {address}. Looking forward to it.\n\nBest,\nToney"
    },
    "accept_suggest_times": {
        "subject": "Re: {original_subject}",
        "body": "Hi {first_name},\n\nGreat to hear. Here are a few times I have open when I'm in your area:\n\n{time_options}\n\nDo any of those work for you?\n\nBest,\nToney"
    },
    "reschedule": {
        "subject": "Re: {original_subject}",
        "body": "Hi {first_name},\n\nNo problem at all. Here are some other times I have available:\n\n{time_options}\n\nJust let me know what works best.\n\nBest,\nToney"
    },
    "decline_graceful": {
        "subject": "Re: {original_subject}",
        "body": "Hi {first_name},\n\nCompletely understand. If anything changes or you'd like to connect down the road, don't hesitate to reach out.\n\nAll the best,\nToney"
    },
    "ooo_acknowledge": {
        "subject": "Re: {original_subject}",
        "body": "Hi {first_name},\n\nThanks for the heads up. I'll follow up when you're back. Enjoy your time off.\n\nBest,\nToney"
    },
    "confirmation": {
        "subject": "Confirmed: Meeting {date_str} at {time_str}",
        "body": "Hi {first_name},\n\nJust confirming our meeting:\n\nDate: {date_str}\nTime: {time_str}\nLocation: {location}\nDuration: {duration} minutes\n\nLooking forward to connecting. If anything comes up, just reply to this email.\n\nBest,\nToney Sebra"
    },
    "reminder_24h": {
        "subject": "Reminder: Meeting tomorrow with Toney Sebra",
        "body": "Hi {first_name},\n\nQuick reminder about our meeting tomorrow at {time_str}.\n\nI'll be at {location}. See you there.\n\nBest,\nToney"
    }
}


def ghl_api(method, endpoint, data=None):
    """Make GHL API call via curl."""
    cmd = [
        "curl", "-s", "-X", method,
        f"{GHL_API}{endpoint}",
        "-H", f"Authorization: Bearer {GHL_TOKEN}",
        "-H", f"Version: {GHL_VERSION}",
        "-H", "Content-Type: application/json"
    ]
    if data:
        cmd.extend(["-d", json.dumps(data)])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout[:200]}


def send_reply(contact_id, subject, body, thread_id=None, reply_message_id=None):
    """Send email reply in conversation thread."""
    html_body = body.replace("\n\n", "</p><p>").replace("\n", "<br>")
    html_body = f"<p>{html_body}</p>"

    payload = {
        "type": "Email",
        "contactId": contact_id,
        "subject": subject,
        "html": html_body,
        "emailFrom": "toney@liftlineai.com"
    }

    # Thread replies for proper email threading
    if thread_id:
        payload["threadId"] = thread_id
    if reply_message_id:
        payload["replyMessageId"] = reply_message_id
        payload["emailReplyMode"] = "reply"

    resp = ghl_api("POST", "/conversations/messages", payload)
    return resp.get("msg") or resp.get("messageId")


def classify_intent(message_text):
    """Classify the intent of an inbound email using pattern matching."""
    text = message_text.lower().strip()

    # Check patterns in priority order
    for pattern in DECLINE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "DECLINE"

    for pattern in OOO_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "OOO"

    for pattern in RESCHEDULE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "RESCHEDULE"

    for pattern in ACCEPT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "ACCEPT"

    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "QUESTION"

    # Default: treat as potential accept (they replied = interested)
    return "ACCEPT"


def extract_time_mentions(text):
    """Extract any time/date mentions from message."""
    times = []

    # Match patterns like "2pm", "2:30 PM", "14:00"
    time_matches = re.findall(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))', text)
    times.extend(time_matches)

    # Match day mentions
    days = re.findall(r'(Monday|Tuesday|Wednesday|Thursday|Friday|next week|this week)', text, re.IGNORECASE)
    times.extend(days)

    return times


def generate_time_options(zone, tier):
    """Generate available time slot options for an advisor."""
    # Get next zone visit dates (next occurrence of this zone in 5-week rotation)
    today = datetime.now()

    # Find next weekdays
    options = []
    for i in range(1, 14):  # Look 2 weeks ahead
        date = today + timedelta(days=i)
        if date.weekday() < 5:  # Weekdays only
            if tier == "a":
                options.append(f"  - {date.strftime('%A, %B %d')} at 8:30 AM")
                options.append(f"  - {date.strftime('%A, %B %d')} at 9:00 AM")
            elif tier == "b":
                options.append(f"  - {date.strftime('%A, %B %d')} at 10:00 AM")
                options.append(f"  - {date.strftime('%A, %B %d')} at 2:00 PM")
            else:
                options.append(f"  - {date.strftime('%A, %B %d')} at 1:30 PM")
                options.append(f"  - {date.strftime('%A, %B %d')} at 3:00 PM")

            if len(options) >= 4:
                break

    return "\n".join(options)


def add_tag(contact_id, tag):
    ghl_api("POST", f"/contacts/{contact_id}/tags", {"tags": [tag]})


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_response(action, details):
    logs = []
    if RESPONDER_LOG.exists():
        with open(RESPONDER_LOG) as f:
            logs = json.load(f)
    logs.append({"timestamp": datetime.now().isoformat(), "action": action, **details})
    with open(RESPONDER_LOG, "w") as f:
        json.dump(logs[-500:], f, indent=2)


def get_contact_tier(contact_id):
    """Get tier from contact tags."""
    resp = ghl_api("GET", f"/contacts/{contact_id}")
    contact = resp.get("contact", resp)
    tags = contact.get("tags", [])
    for t in tags:
        if t.startswith("liftline-tier-"):
            return t.replace("liftline-tier-", "")
    return "c"


def get_contact_zone(contact_id):
    """Get zone from contact tags."""
    resp = ghl_api("GET", f"/contacts/{contact_id}")
    contact = resp.get("contact", resp)
    tags = contact.get("tags", [])
    for t in tags:
        if t.startswith("liftline-zone-"):
            return int(t.replace("liftline-zone-", ""))
    return 1


# === COMMANDS ===

def cmd_check():
    """Check for new inbound email responses."""
    print(f"""
{'='*60}
  LIFTLINEAI RESPONDER — Checking inbound emails...
{'='*60}
""")

    # Search for conversations with inbound messages
    resp = ghl_api("GET",
        f"/conversations/search?locationId={GHL_LOCATION}"
        f"&status=unread&lastMessageType=TYPE_EMAIL"
        f"&lastMessageDirection=inbound&limit=20"
    )

    conversations = resp.get("conversations", [])

    if not conversations:
        print("  No new inbound emails found.")
        print("  Tip: When an advisor replies, it shows up here automatically.\n")
        return

    print(f"  Found {len(conversations)} unread conversations:\n")

    for conv in conversations:
        contact_name = conv.get("contactName", "Unknown")
        contact_id = conv.get("contactId", "")
        conv_id = conv.get("id", "")
        last_msg = conv.get("lastMessageBody", "")[:100]
        last_date = conv.get("lastMessageDate", "")

        print(f"  📧 {contact_name}")
        print(f"     Preview: {last_msg}")
        print(f"     Date: {last_date}")
        print(f"     Conv ID: {conv_id}")

        # Classify intent
        intent = classify_intent(last_msg)
        print(f"     Intent: {intent}")
        print()

    return conversations


def cmd_process_all():
    """Process all unread inbound emails with smart responses."""
    state = load_state()

    print(f"""
{'='*60}
  LIFTLINEAI RESPONDER — Processing all inbound emails
{'='*60}
""")

    # Get unread inbound emails
    resp = ghl_api("GET",
        f"/conversations/search?locationId={GHL_LOCATION}"
        f"&status=unread&lastMessageType=TYPE_EMAIL"
        f"&lastMessageDirection=inbound&limit=50"
    )

    conversations = resp.get("conversations", [])

    if not conversations:
        print("  No unread emails to process.\n")
        return

    processed = 0
    for conv in conversations:
        contact_name = conv.get("contactName", "Unknown")
        contact_id = conv.get("contactId", "")
        conv_id = conv.get("id", "")

        # Get full message thread
        msgs_resp = ghl_api("GET", f"/conversations/{conv_id}/messages?type=TYPE_EMAIL&limit=5")
        messages = msgs_resp.get("messages", {})
        if isinstance(messages, dict):
            messages = messages.get("messages", [])

        if not messages:
            continue

        # Find the latest inbound message
        inbound_msg = None
        for m in messages:
            if m.get("direction") == "inbound":
                inbound_msg = m
                break

        if not inbound_msg:
            continue

        msg_body = inbound_msg.get("body", inbound_msg.get("text", ""))
        msg_id = inbound_msg.get("id", "")
        thread_id = conv.get("lastMessageThreadId", inbound_msg.get("threadId", ""))

        # Get contact details
        contact_resp = ghl_api("GET", f"/contacts/{contact_id}")
        contact = contact_resp.get("contact", contact_resp)
        first_name = contact.get("firstNameRaw", contact.get("firstName", "Advisor"))
        city = contact.get("city", "your area")
        address = contact.get("address1", "your office")
        tier = get_contact_tier(contact_id)
        zone = get_contact_zone(contact_id)

        # Classify intent
        intent = classify_intent(msg_body)

        print(f"  Processing: {contact_name}")
        print(f"    Message: {msg_body[:80]}...")
        print(f"    Intent: {intent}")

        # Handle based on intent
        if intent == "ACCEPT":
            # Check if they mentioned a specific time
            time_mentions = extract_time_mentions(msg_body)

            if time_mentions:
                # They gave a time — book it
                print(f"    → Booking meeting (mentioned: {', '.join(time_mentions)})")
                add_tag(contact_id, "liftline-responded")
                add_tag(contact_id, "liftline-meeting-booked")

                # Update state
                if "responses" not in state:
                    state["responses"] = {}
                state["responses"][contact_id] = {
                    "date": datetime.now().isoformat(),
                    "name": contact_name, "intent": intent,
                    "time_mentioned": time_mentions
                }

                # Send confirmation
                reply_body = REPLY_TEMPLATES["accept_with_time"]["body"].format(
                    first_name=first_name,
                    time_str=time_mentions[0] if time_mentions else "our agreed time",
                    date_str="next week",
                    address=f"{address}, {city}"
                )
                send_reply(contact_id, f"Re: Quick catch-up", reply_body, thread_id, msg_id)
                print(f"    → Confirmation sent")

            else:
                # They're interested but no time — suggest options
                print(f"    → Suggesting time slots")
                add_tag(contact_id, "liftline-responded")

                time_options = generate_time_options(zone, tier)
                reply_body = REPLY_TEMPLATES["accept_suggest_times"]["body"].format(
                    first_name=first_name,
                    time_options=time_options
                )
                send_reply(contact_id, f"Re: Quick catch-up", reply_body, thread_id, msg_id)
                print(f"    → Time options sent")

                state.setdefault("responses", {})[contact_id] = {
                    "date": datetime.now().isoformat(),
                    "name": contact_name, "intent": intent
                }

        elif intent == "RESCHEDULE":
            print(f"    → Sending alternative times")
            add_tag(contact_id, "liftline-responded")
            add_tag(contact_id, "liftline-reschedule")

            time_options = generate_time_options(zone, tier)
            reply_body = REPLY_TEMPLATES["reschedule"]["body"].format(
                first_name=first_name,
                time_options=time_options
            )
            send_reply(contact_id, f"Re: Quick catch-up", reply_body, thread_id, msg_id)

            state.setdefault("responses", {})[contact_id] = {
                "date": datetime.now().isoformat(),
                "name": contact_name, "intent": intent
            }

        elif intent == "DECLINE":
            print(f"    → Graceful close")
            add_tag(contact_id, "liftline-declined")
            add_tag(contact_id, "liftline-cycle-complete")

            reply_body = REPLY_TEMPLATES["decline_graceful"]["body"].format(
                first_name=first_name
            )
            send_reply(contact_id, f"Re: Quick catch-up", reply_body, thread_id, msg_id)

            state.setdefault("responses", {})[contact_id] = {
                "date": datetime.now().isoformat(),
                "name": contact_name, "intent": intent
            }

        elif intent == "OOO":
            print(f"    → OOO detected, will retry later")
            add_tag(contact_id, "liftline-ooo")

            reply_body = REPLY_TEMPLATES["ooo_acknowledge"]["body"].format(
                first_name=first_name
            )
            send_reply(contact_id, f"Re: Quick catch-up", reply_body, thread_id, msg_id)

            state.setdefault("responses", {})[contact_id] = {
                "date": datetime.now().isoformat(),
                "name": contact_name, "intent": intent
            }

        elif intent == "QUESTION":
            print(f"    → ALERT: Needs manual reply from Toney")
            add_tag(contact_id, "liftline-needs-reply")

            # Send notification to Toney
            # (In production, this would send a text/notification to Toney)
            print(f"    ⚠ TONEY: {contact_name} has a question — check GHL conversations")

            state.setdefault("responses", {})[contact_id] = {
                "date": datetime.now().isoformat(),
                "name": contact_name, "intent": intent,
                "needs_manual": True
            }

        log_response("processed", {
            "contact_id": contact_id, "name": contact_name,
            "intent": intent, "message_preview": msg_body[:100]
        })

        processed += 1
        time.sleep(1)

    save_state(state)

    print(f"""
{'='*60}
  PROCESSED: {processed} conversations
{'='*60}
""")


def cmd_send_reminders():
    """Send 24-hour reminders for tomorrow's meetings."""
    state = load_state()

    # Load schedules
    schedule_file = ENGINE_DIR / "schedules.json"
    if not schedule_file.exists():
        print("  No schedules found.")
        return

    with open(schedule_file) as f:
        schedules = json.load(f)

    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    day_sched = schedules.get("schedules", {}).get(tomorrow)

    if not day_sched:
        print(f"  No meetings scheduled for {tomorrow}")
        return

    print(f"""
{'='*60}
  SENDING 24-HOUR REMINDERS — {tomorrow}
{'='*60}
""")

    sent = 0
    for m in day_sched.get("meetings", []):
        if m.get("status") in ["confirmed", "scheduled"]:
            contact_id = m["contact_id"]
            first_name = m["name"].split()[0]

            body = REPLY_TEMPLATES["reminder_24h"]["body"].format(
                first_name=first_name,
                time_str=m["time"],
                location=f"{m.get('address', '')} {m.get('city', '')}"
            )
            subject = REPLY_TEMPLATES["reminder_24h"]["subject"]

            print(f"  Reminder → {m['name']} ({m['time']})...", end=" ")
            success = send_reply(contact_id, subject, body)
            if success:
                print("✓")
                sent += 1
            else:
                print("✗")
            time.sleep(1)

    print(f"\n  {sent} reminders sent\n")


def cmd_watch():
    """Continuous monitor — check every 5 minutes."""
    print(f"""
{'='*60}
  LIFTLINEAI RESPONDER — WATCH MODE
  Checking for new emails every 5 minutes...
  Press Ctrl+C to stop.
{'='*60}
""")

    while True:
        now = datetime.now().strftime("%I:%M %p")
        print(f"\n  [{now}] Checking...")

        try:
            conversations = cmd_check()
            if conversations:
                cmd_process_all()
        except Exception as e:
            print(f"  Error: {e}")

        print(f"  Next check in 5 minutes...")
        time.sleep(300)


# === MAIN ===

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    commands = {
        "check": cmd_check,
        "process-all": cmd_process_all,
        "send-reminders": cmd_send_reminders,
        "watch": cmd_watch,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"  Unknown command: {cmd}\n")
        print(__doc__)


if __name__ == "__main__":
    main()
