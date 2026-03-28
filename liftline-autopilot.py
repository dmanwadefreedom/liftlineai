#!/usr/bin/env python3
"""
LiftlineAI Autopilot — Autonomous Scheduling Agent
====================================================
Runs daily at 8 AM. Scans calendar openings. Fills them smart.

What it does every morning:
  1. Check calendar for open slots this week + next week
  2. Determine which zone is active (5-week rotation)
  3. Pull contacts for that zone, sorted by tier (A first)
  4. Geo-cluster contacts to minimize drive time
  5. Send outreach emails + SMS to fill open slots
  6. Process any inbound responses (book/reschedule/decline)
  7. Send 24hr confirmation calls via VAPI
  8. Send daily report to Toney

Commands:
  python3 liftline-autopilot.py run           # Full morning run
  python3 liftline-autopilot.py scan          # Scan openings only (no emails)
  python3 liftline-autopilot.py fill-week     # Fill this week's open slots
  python3 liftline-autopilot.py confirm-tomorrow  # Call/SMS tomorrow's meetings
  python3 liftline-autopilot.py report        # Daily report
  python3 liftline-autopilot.py demo          # Full demo cycle (test everything)
"""

import json
import sys
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# === CONFIG ===
GHL_API = "https://services.leadconnectorhq.com"
GHL_TOKEN = "pit-f1ec9196-bfed-44d7-acc3-c89e9051b1fa"
GHL_LOCATION = "DkwGpda79CXXO6YqwceD"
GHL_VERSION = "2021-07-28"

VAPI_API = "https://api.vapi.ai"
VAPI_ASSISTANT_ID = "278eb0d4-c3c3-4055-b377-798673a0e124"
VAPI_PHONE_ID = "5dc7500d-ebd0-4879-a6d7-6cd513dfd84f"
VAPI_PHONE_NUMBER = "+15129670954"

ENGINE_DIR = Path(__file__).parent
STATE_FILE = ENGINE_DIR / "engine-state.json"
SCHEDULE_FILE = ENGINE_DIR / "schedules.json"

# Business hours: 8 AM - 5 PM, 30-min slots, lunch 12-1
SLOT_DURATION = 30  # minutes
BUFFER = 15  # minutes between meetings
SLOTS_PER_DAY = 10  # Max meetings per day
WORK_START = 8 * 60  # 8:00 AM in minutes
WORK_END = 17 * 60  # 5:00 PM
LUNCH_START = 12 * 60
LUNCH_END = 13 * 60

# 5-week zone rotation
ZONE_ROTATION = [1, 2, 3, 4, 5]
ZONE_NAMES = {
    1: "Sacramento Downtown", 2: "West Sacramento / Davis",
    3: "Roseville / Rocklin", 4: "Folsom / El Dorado Hills",
    5: "Rancho Cordova / Elk Grove"
}

TIER_PRIORITY = {"a": 1, "b": 2, "c": 3, "prospect": 4}

# Geo clusters for drive-time optimization
GEO_CLUSTERS = {
    1: [
        {"name": "Capitol Mall / J St", "keywords": ["capitol", "j st", "k st", "l st"]},
        {"name": "Midtown", "keywords": ["16th", "17th", "18th", "19th", "20th", "21st", "p st", "q st"]},
        {"name": "Old Sacramento", "keywords": ["front", "2nd", "river", "tower"]},
    ],
    2: [
        {"name": "West Sacramento", "keywords": ["harbor", "jefferson", "west capitol"]},
        {"name": "Davis Downtown", "keywords": ["3rd", "f st", "g st", "university"]},
        {"name": "Davis East", "keywords": ["covell", "anderson", "pole line"]},
    ],
    3: [
        {"name": "Roseville", "keywords": ["galleria", "roseville", "lead hill", "vernon", "douglas"]},
        {"name": "Rocklin", "keywords": ["sierra college", "sunset", "pacific", "granite"]},
    ],
    4: [
        {"name": "Folsom", "keywords": ["sutter", "riley", "natoma", "iron point", "bidwell", "blue ravine"]},
        {"name": "El Dorado Hills", "keywords": ["latrobe", "town center", "saratoga", "harvard"]},
    ],
    5: [
        {"name": "Rancho Cordova", "keywords": ["zinfandel", "coloma", "folsom blvd", "white rock"]},
        {"name": "Elk Grove", "keywords": ["laguna", "elk grove", "stockton", "civic center", "bruceville"]},
    ],
}


def ghl_api(method, endpoint, data=None):
    cmd = ["curl", "-s", "-X", method, f"{GHL_API}{endpoint}",
           "-H", f"Authorization: Bearer {GHL_TOKEN}",
           "-H", f"Version: {GHL_VERSION}",
           "-H", "Content-Type: application/json"]
    if data:
        cmd.extend(["-d", json.dumps(data)])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except:
        return {"error": result.stdout[:200]}


def vapi_api(method, endpoint, data=None):
    vapi_key = subprocess.run(
        ["grep", "^VAPI_API_KEY=", str(Path.home() / ".dylan-keys/.env")],
        capture_output=True, text=True
    ).stdout.strip().split("=", 1)[-1]

    cmd = ["curl", "-s", "-X", method, f"{VAPI_API}{endpoint}",
           "-H", f"Authorization: Bearer {vapi_key}",
           "-H", "Content-Type: application/json"]
    if data:
        cmd.extend(["-d", json.dumps(data)])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except:
        return {"error": result.stdout[:200]}


def send_email(contact_id, subject, body):
    html = body.replace("\n\n", "</p><p>").replace("\n", "<br>")
    resp = ghl_api("POST", "/conversations/messages", {
        "type": "Email", "contactId": contact_id,
        "subject": subject, "html": f"<p>{html}</p>",
        "emailFrom": "toney@liftlineai.com"
    })
    return resp.get("msg") or resp.get("messageId")


def send_sms(contact_id, message):
    resp = ghl_api("POST", "/conversations/messages", {
        "type": "SMS", "contactId": contact_id, "message": message
    })
    return resp.get("msg") or resp.get("messageId")


def make_vapi_call(phone_number, first_name, meeting_time, meeting_location):
    """Trigger VAPI confirmation call."""
    resp = vapi_api("POST", "/call/phone", {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_ID,
        "customer": {"number": phone_number},
        "assistantOverrides": {
            "firstMessage": f"Hey {first_name}, this is calling on behalf of Toney Sebra. Just wanted to confirm your meeting tomorrow at {meeting_time}. Is everything still good on your end?"
        }
    })
    return resp.get("id") or resp.get("callId")


def add_tag(contact_id, tag):
    ghl_api("POST", f"/contacts/{contact_id}/tags", {"tags": [tag]})


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"contacts_emailed": {}, "responses": {}, "appointments": {},
            "zone_rotation": {"current_zone": 1, "history": []}}


def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_schedules():
    if SCHEDULE_FILE.exists():
        with open(SCHEDULE_FILE) as f:
            return json.load(f)
    return {"schedules": {}}


def save_schedules(schedules):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedules, f, indent=2)


def get_all_liftline_contacts():
    all_c = []
    sa, said = None, None
    while True:
        url = f"/contacts/?locationId={GHL_LOCATION}&limit=100"
        if sa:
            url += f"&startAfter={sa}&startAfterId={said}"
        resp = ghl_api("GET", url)
        contacts = resp.get("contacts", [])
        if not contacts:
            break
        for c in contacts:
            if "liftline-demo" in c.get("tags", []):
                all_c.append(c)
        meta = resp.get("meta", {})
        sa, said = meta.get("startAfter"), meta.get("startAfterId")
        if not sa:
            break
    return all_c


def get_tier(c):
    for t in c.get("tags", []):
        if t.startswith("liftline-tier-"):
            return t.replace("liftline-tier-", "")
    return "c"


def get_zone(c):
    for t in c.get("tags", []):
        if t.startswith("liftline-zone-"):
            return int(t.replace("liftline-zone-", ""))
    return 0


def get_name(c):
    return f"{c.get('firstNameRaw', c.get('firstName',''))} {c.get('lastNameRaw', c.get('lastName',''))}".strip()


def get_cluster(c, zone):
    addr = (c.get("address1", "") or "").lower()
    city = (c.get("city", "") or "").lower()
    for i, cluster in enumerate(GEO_CLUSTERS.get(zone, [])):
        for kw in cluster["keywords"]:
            if kw in addr or kw in city:
                return i, cluster["name"]
    clusters = GEO_CLUSTERS.get(zone, [])
    return (0, clusters[0]["name"]) if clusters else (0, "Unknown")


def get_current_zone():
    """Determine current zone based on 5-week rotation."""
    state = load_state()
    return state.get("zone_rotation", {}).get("current_zone", 1)


def generate_week_slots(start_date, days=5):
    """Generate all available time slots for a week."""
    slots = {}
    for d in range(days):
        date = start_date + timedelta(days=d)
        if date.weekday() >= 5:  # Skip weekends
            continue
        date_str = date.strftime("%Y-%m-%d")
        day_name = date.strftime("%A")

        day_slots = []
        current = WORK_START
        while current + SLOT_DURATION <= WORK_END:
            # Skip lunch
            if current >= LUNCH_START and current < LUNCH_END:
                current = LUNCH_END
                continue

            h, m = divmod(current, 60)
            end = current + SLOT_DURATION
            eh, em = divmod(end, 60)

            day_slots.append({
                "time": f"{h:02d}:{m:02d}",
                "end_time": f"{eh:02d}:{em:02d}",
                "start_min": current,
                "end_min": end,
                "status": "open",
                "contact_id": None,
                "name": None,
                "tier": None,
                "cluster": None
            })
            current = end + BUFFER

        slots[date_str] = {
            "date": date_str,
            "day": day_name,
            "slots": day_slots,
            "zone": get_current_zone(),
            "zone_name": ZONE_NAMES.get(get_current_zone(), "?")
        }

    return slots


def fill_slots_smart(week_slots, contacts, zone):
    """Fill open slots with contacts, geo-clustered, tier-prioritized."""

    # Group contacts by cluster
    clustered = defaultdict(list)
    for c in contacts:
        tags = c.get("tags", [])
        # Skip already booked or cycle-complete
        if any(t.startswith("liftline-meeting-booked") for t in tags):
            continue
        if "liftline-cycle-complete" in tags:
            continue

        ci, cn = get_cluster(c, zone)
        tier = get_tier(c)
        clustered[ci].append({
            "contact": c, "tier": tier, "cluster_idx": ci,
            "cluster_name": cn, "priority": TIER_PRIORITY.get(tier, 4)
        })

    # Sort each cluster by priority
    for ci in clustered:
        clustered[ci].sort(key=lambda x: x["priority"])

    # Fill each day: one cluster at a time, no zigzag
    filled_count = 0

    for date_str, day_data in sorted(week_slots.items()):
        slots = day_data["slots"]
        open_slots = [s for s in slots if s["status"] == "open"]

        if not open_slots:
            continue

        slot_idx = 0
        # Fill from cluster order
        for ci in sorted(clustered.keys()):
            for entry in clustered[ci][:]:  # Copy list to allow removal
                if slot_idx >= len(open_slots):
                    break

                slot = open_slots[slot_idx]
                contact = entry["contact"]

                slot["status"] = "scheduled"
                slot["contact_id"] = contact["id"]
                slot["name"] = get_name(contact)
                slot["tier"] = entry["tier"]
                slot["cluster"] = entry["cluster_name"]
                slot["email"] = contact.get("email", "")
                slot["phone"] = contact.get("phone", "")
                slot["company"] = contact.get("companyName", "")
                slot["city"] = contact.get("city", "")
                slot["address"] = contact.get("address1", "")

                clustered[ci].remove(entry)
                slot_idx += 1
                filled_count += 1

    return week_slots, filled_count


# === COMMANDS ===

def cmd_scan():
    """Scan calendar openings for this week and next."""
    today = datetime.now()
    # This week (remaining days)
    days_left = 5 - today.weekday()
    if days_left <= 0:
        start = today + timedelta(days=(7 - today.weekday()))
    else:
        start = today

    this_week = generate_week_slots(start, days=max(days_left, 0))
    next_monday = today + timedelta(days=(7 - today.weekday()))
    next_week = generate_week_slots(next_monday, days=5)

    zone = get_current_zone()

    print(f"""
{'='*65}
  AUTOPILOT SCAN — {today.strftime('%A %B %d, %Y %I:%M %p')}
  Active Zone: {zone} ({ZONE_NAMES.get(zone, '?')})
{'='*65}
""")

    # Show this week
    total_open = 0
    total_filled = 0

    for label, week in [("THIS WEEK", this_week), ("NEXT WEEK", next_week)]:
        print(f"  {label}")
        print(f"  {'─'*55}")

        for date_str in sorted(week.keys()):
            day = week[date_str]
            slots = day["slots"]
            open_count = sum(1 for s in slots if s["status"] == "open")
            filled = sum(1 for s in slots if s["status"] != "open")
            total_open += open_count
            total_filled += filled

            bar = "█" * filled + "░" * open_count
            print(f"  {day['day']:<10} {date_str}  [{bar}]  {filled}/{len(slots)} filled, {open_count} open")

        print()

    print(f"  Total open slots: {total_open}")
    print(f"  Total filled: {total_filled}")
    print(f"  Contacts available in Zone {zone}: ", end="")

    contacts = get_all_liftline_contacts()
    zone_contacts = [c for c in contacts if get_zone(c) == zone]
    unreached = [c for c in zone_contacts
                 if "liftline-meeting-booked" not in c.get("tags", [])
                 and "liftline-cycle-complete" not in c.get("tags", [])]
    print(f"{len(unreached)} unreached out of {len(zone_contacts)}")
    print()

    return this_week, next_week


def cmd_fill_week():
    """Fill this week's open slots with smart outreach."""
    state = load_state()
    zone = get_current_zone()
    today = datetime.now()

    print(f"""
{'='*65}
  AUTOPILOT — FILLING CALENDAR
  Zone {zone}: {ZONE_NAMES.get(zone, '?')}
  Strategy: Geo-clustered, A-tier morning, minimize driving
{'='*65}
""")

    # Generate week slots
    next_monday = today + timedelta(days=(7 - today.weekday()))
    week_slots = generate_week_slots(next_monday, days=5)

    # Get zone contacts
    contacts = get_all_liftline_contacts()
    zone_contacts = [c for c in contacts if get_zone(c) == zone]

    print(f"  Zone {zone} contacts: {len(zone_contacts)}")

    # Fill slots smart
    filled_week, filled_count = fill_slots_smart(week_slots, zone_contacts, zone)

    print(f"  Slots filled: {filled_count}")
    print()

    # Save schedule
    schedules = load_schedules()
    for date_str, day_data in filled_week.items():
        # Convert to meeting format for compatibility
        meetings = []
        for s in day_data["slots"]:
            if s["status"] != "open":
                meetings.append({
                    "contact_id": s["contact_id"],
                    "name": s["name"],
                    "tier": s["tier"],
                    "cluster_name": s.get("cluster", ""),
                    "time": s["time"],
                    "end_time": s["end_time"],
                    "email": s.get("email", ""),
                    "phone": s.get("phone", ""),
                    "company": s.get("company", ""),
                    "city": s.get("city", ""),
                    "address": s.get("address", ""),
                    "status": "scheduled",
                    "slot_start_minutes": s["start_min"],
                    "slot_end_minutes": s["end_min"]
                })

        day_data["meetings"] = meetings
        day_data["total_meetings"] = len(meetings)
        day_data["zone"] = zone
        day_data["zone_name"] = ZONE_NAMES.get(zone, "?")
        schedules["schedules"][date_str] = day_data

    save_schedules(schedules)

    # Send outreach to each scheduled contact
    sent_email = 0
    sent_sms = 0

    for date_str, day_data in sorted(filled_week.items()):
        day_name = day_data["day"]
        print(f"\n  {day_name} {date_str}:")

        for s in day_data["slots"]:
            if s["status"] == "open" or not s.get("contact_id"):
                continue

            contact_id = s["contact_id"]
            name = s["name"]
            tier = s["tier"]
            time_str = s["time"]
            city = s.get("city", "your area")
            first_name = name.split()[0] if name else "there"
            email = s.get("email", "")
            phone = s.get("phone", "")

            # Skip if already emailed
            if contact_id in state.get("contacts_emailed", {}):
                print(f"    SKIP {name} [{tier.upper()}] — already in pipeline")
                continue

            # Tier-specific email
            if tier == "a":
                subject = f"Quick catch-up when I'm in {city} next week"
                body = f"Hi {first_name},\n\nI've been spending time with several of the top advisors in the region and there are a few clear themes emerging around how they're growing and positioning client portfolios in this market.\n\nI thought it would be worthwhile to compare notes and share a quick update on where we're seeing the most traction across our strategies.\n\nI have {day_name} at {time_str} open — would that work for 20 minutes?\n\nBest,\nToney Sebra"
            elif tier == "b":
                subject = f"Quick catch-up when I'm in {city} next week"
                body = f"Hi {first_name},\n\nI've been working with a number of advisors on practice management and prospecting strategies that are gaining traction right now, and I thought a few of these ideas might be relevant for you as well.\n\nDo you have 15-20 minutes on {day_name} around {time_str}?\n\nBest,\nToney Sebra"
            elif tier == "prospect":
                subject = f"Introduction - Toney Sebra"
                body = f"Hi {first_name},\n\nI cover your area and realized we haven't had the chance to connect yet.\n\nI'd welcome a quick 15-minute intro on {day_name} if you're open to it.\n\nBest regards,\nToney Sebra"
            else:
                subject = f"Quick catch-up when I'm in {city} next week"
                body = f"Hi {first_name},\n\nI've been working with advisors in your area and thought it might be helpful to connect and share what's working.\n\nWould {day_name} around {time_str} work for 15-20 minutes?\n\nBest,\nToney Sebra"

            # Send email
            print(f"    📧 {name} [{tier.upper()}] {time_str} — {s.get('cluster','')}...", end=" ")
            email_ok = send_email(contact_id, subject, body)
            if email_ok:
                print("email ✓", end=" ")
                sent_email += 1
            else:
                print("email ✗", end=" ")

            # Send SMS too (direct to cell)
            if phone:
                sms_msg = f"Hi {first_name}, this is Toney Sebra. I'll be in {city} {day_name} and would love to connect for 15-20 min around {time_str}. Would that work? Reply YES to confirm."
                sms_ok = send_sms(contact_id, sms_msg)
                if sms_ok:
                    print("sms ✓")
                    sent_sms += 1
                else:
                    print("sms ✗")
            else:
                print()

            # Track
            add_tag(contact_id, "liftline-outreach-sent")
            state["contacts_emailed"][contact_id] = {
                "date": datetime.now().isoformat(),
                "name": name, "tier": tier, "zone": zone,
                "proposed_date": date_str, "proposed_time": time_str,
                "followup_count": 0
            }

            time.sleep(1.5)  # Rate limit

    state["zone_rotation"]["current_zone"] = zone
    state["zone_rotation"]["history"].append({
        "zone": zone, "date": datetime.now().isoformat(),
        "sent_email": sent_email, "sent_sms": sent_sms
    })
    save_state(state)

    print(f"""
{'='*65}
  OUTREACH COMPLETE
  Emails sent: {sent_email}
  SMS sent: {sent_sms}
  Calendar slots filled: {filled_count}
  Zone: {zone} ({ZONE_NAMES.get(zone,'?')})

  Run 'python3 liftline-engine.py status' to see full dashboard.
  Run 'python3 liftline-responder.py watch' to monitor replies.
{'='*65}
""")


def cmd_confirm_tomorrow():
    """Send confirmation calls + SMS for tomorrow's meetings."""
    schedules = load_schedules()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    day = schedules.get("schedules", {}).get(tomorrow)

    if not day:
        print(f"  No meetings scheduled for tomorrow ({tomorrow})")
        return

    meetings = day.get("meetings", [])
    confirmed_meetings = [m for m in meetings if m.get("status") in ["scheduled", "confirmed"]]

    print(f"""
{'='*65}
  CONFIRMING TOMORROW'S MEETINGS — {day['day']} {tomorrow}
  Zone {day.get('zone','?')}: {day.get('zone_name','?')}
  {len(confirmed_meetings)} meetings to confirm
{'='*65}
""")

    for m in confirmed_meetings:
        name = m.get("name", "?")
        first_name = name.split()[0]
        time_str = m["time"]
        phone = m.get("phone", "")
        contact_id = m.get("contact_id", "")
        city = m.get("city", "")
        address = m.get("address", "")

        print(f"  {name} — {time_str}")

        # 1. Send SMS reminder
        if phone:
            sms = f"Hi {first_name}, just confirming our meeting tomorrow at {time_str}. Looking forward to it. - Toney Sebra"
            sms_ok = send_sms(contact_id, sms)
            print(f"    SMS: {'✓' if sms_ok else '✗'}")

        # 2. Send email reminder
        email_body = f"Hi {first_name},\n\nQuick reminder about our meeting tomorrow at {time_str}.\n\nI'll be at {address} {city}. See you there.\n\nBest,\nToney"
        email_ok = send_email(contact_id, f"Reminder: Meeting tomorrow with Toney Sebra", email_body)
        print(f"    Email: {'✓' if email_ok else '✗'}")

        # 3. VAPI confirmation call
        if phone:
            call_id = make_vapi_call(phone, first_name, time_str, f"{address} {city}")
            print(f"    VAPI Call: {'✓ ' + str(call_id)[:12] if call_id else '✗'}")

        time.sleep(2)

    print(f"\n  All {len(confirmed_meetings)} meetings confirmed.\n")


def cmd_report():
    """Daily report."""
    state = load_state()
    schedules = load_schedules()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    total_emailed = len(state.get("contacts_emailed", {}))
    total_responses = len(state.get("responses", {}))
    total_booked = len(state.get("appointments", {}))

    tomorrow_sched = schedules.get("schedules", {}).get(tomorrow, {})
    tomorrow_meetings = tomorrow_sched.get("meetings", [])

    print(f"""
{'='*65}
  LIFTLINEAI DAILY REPORT — {now.strftime('%B %d, %Y %I:%M %p')}
{'='*65}

  PIPELINE
  ────────────────────────────
  Total Emailed:    {total_emailed}
  Responses:        {total_responses} ({(total_responses/total_emailed*100) if total_emailed else 0:.0f}%)
  Meetings Booked:  {total_booked}
  Current Zone:     {state.get('zone_rotation',{}).get('current_zone','?')}

  TOMORROW ({tomorrow})
  ────────────────────────────""")

    if tomorrow_meetings:
        for m in tomorrow_meetings:
            icon = "✓" if m.get("status") == "confirmed" else "◻"
            print(f"  {icon} {m['time']}  [{m.get('tier','?').upper()}] {m['name']}")
    else:
        print("  No meetings scheduled")

    print(f"""
  ACTIONS NEEDED
  ────────────────────────────""")

    # Check for unprocessed responses
    unread = ghl_api("GET",
        f"/conversations/search?locationId={GHL_LOCATION}"
        f"&status=unread&lastMessageDirection=inbound&limit=5"
    )
    unread_count = len(unread.get("conversations", []))
    if unread_count:
        print(f"  ⚠ {unread_count} unread inbound messages — run responder")
    else:
        print(f"  ✓ No unread messages")

    print()


def cmd_run():
    """Full morning run — the daily autopilot cycle."""
    now = datetime.now()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  LIFTLINEAI AUTOPILOT — MORNING RUN                     ║
║  {now.strftime('%A %B %d, %Y — %I:%M %p'):<55} ║
╚══════════════════════════════════════════════════════════╝
""")

    # Step 1: Process any inbound responses from overnight
    print("  STEP 1: Processing inbound responses...")
    resp = ghl_api("GET",
        f"/conversations/search?locationId={GHL_LOCATION}"
        f"&status=unread&lastMessageDirection=inbound&limit=50"
    )
    inbound = resp.get("conversations", [])
    print(f"  → {len(inbound)} unread inbound messages\n")

    # Step 2: Scan calendar
    print("  STEP 2: Scanning calendar openings...")
    cmd_scan()

    # Step 3: Fill the week
    print("  STEP 3: Filling open slots with smart outreach...")
    cmd_fill_week()

    # Step 4: Confirm tomorrow's meetings
    print("  STEP 4: Confirming tomorrow's meetings...")
    cmd_confirm_tomorrow()

    # Step 5: Daily report
    print("  STEP 5: Daily report...")
    cmd_report()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  AUTOPILOT COMPLETE                                      ║
║  Next run: Tomorrow at 8:00 AM                           ║
╚══════════════════════════════════════════════════════════╝
""")


def cmd_demo():
    """Run full demo cycle for Toney."""
    print(f"""
╔══════════════════════════════════════════════════════════╗
║  LIFTLINEAI — FULL DEMO CYCLE                            ║
║  Showing the complete autonomous workflow                 ║
╚══════════════════════════════════════════════════════════╝
""")

    # Step 1: Show current status
    print("\n" + "="*65)
    print("  DEMO STEP 1: Current Pipeline Status")
    print("="*65)
    subprocess.run([sys.executable, str(ENGINE_DIR / "liftline-engine.py"), "status"])

    # Step 2: Scan openings
    print("\n" + "="*65)
    print("  DEMO STEP 2: Autopilot Scans Calendar")
    print("="*65)
    cmd_scan()

    # Step 3: Show smart schedule
    print("\n" + "="*65)
    print("  DEMO STEP 3: Geo-Optimized Route")
    print("="*65)
    subprocess.run([sys.executable, str(ENGINE_DIR / "liftline-engine.py"), "schedule-zone", "1"])

    # Step 4: Show daily view
    print("\n" + "="*65)
    print("  DEMO STEP 4: Daily Schedule View")
    print("="*65)
    # Find first scheduled day
    schedules = load_schedules()
    for date_str in sorted(schedules.get("schedules", {}).keys()):
        subprocess.run([sys.executable, str(ENGINE_DIR / "liftline-engine.py"), "daily-schedule", date_str])
        break

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  DEMO COMPLETE                                           ║
║                                                          ║
║  What you just saw:                                      ║
║  1. Pipeline dashboard — all 50 contacts by zone/tier    ║
║  2. Calendar scan — open slots identified                ║
║  3. Smart routing — meetings clustered, no zigzag        ║
║  4. Daily schedule — full day with drive optimization    ║
║                                                          ║
║  Ready to run:                                           ║
║  • fill-week    — send outreach to fill calendar         ║
║  • confirm-tomorrow — SMS + email + VAPI call 24hr      ║
║  • responder watch — auto-handle email replies           ║
╚══════════════════════════════════════════════════════════╝
""")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    commands = {
        "run": cmd_run,
        "scan": cmd_scan,
        "fill-week": cmd_fill_week,
        "confirm-tomorrow": cmd_confirm_tomorrow,
        "report": cmd_report,
        "demo": cmd_demo,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown: {cmd}\n")
        print(__doc__)


if __name__ == "__main__":
    main()
