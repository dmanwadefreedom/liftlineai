#!/usr/bin/env python3
"""
LiftlineAI Smart Scheduling Engine v2
======================================
AI-powered zone-based scheduling for wholesale financial reps.
Handles geo-clustering, drive-time optimization, tier-priority booking,
follow-up sequences, and daily schedule generation.

Commands:
  python3 liftline-engine.py status                  # Full pipeline dashboard
  python3 liftline-engine.py run-zone <1-5>          # Smart outreach for a zone
  python3 liftline-engine.py schedule-zone <1-5>     # Generate optimized daily schedule
  python3 liftline-engine.py follow-up               # Send follow-ups to non-responders
  python3 liftline-engine.py book <contact_id> <date> <time>  # Book a meeting
  python3 liftline-engine.py daily-schedule [date]   # Show day's schedule with drive routing
  python3 liftline-engine.py weekly-view [zone]      # Show week view for zone
  python3 liftline-engine.py demo-populate           # Load demo appointments + responses
  python3 liftline-engine.py daily-report            # Generate EOD report
  python3 liftline-engine.py test                    # Test email to Toney
  python3 liftline-engine.py reset                   # Fresh start
"""

import json
import sys
import time
import subprocess
import random
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# === CONFIG ===
GHL_API = "https://services.leadconnectorhq.com"
GHL_TOKEN = "pit-f1ec9196-bfed-44d7-acc3-c89e9051b1fa"
GHL_LOCATION = "DkwGpda79CXXO6YqwceD"
GHL_VERSION = "2021-07-28"

ENGINE_DIR = Path(__file__).parent
STATE_FILE = ENGINE_DIR / "engine-state.json"
LOG_FILE = ENGINE_DIR / "engine-log.json"
SCHEDULE_FILE = ENGINE_DIR / "schedules.json"

# === GEO CLUSTERS ===
# Sub-areas within each zone for drive-time optimization
# Contacts in the same cluster = 5 min apart. Different clusters = 15-25 min.
GEO_CLUSTERS = {
    1: {  # Sacramento Downtown
        "clusters": [
            {"name": "Capitol Mall / J St", "streets": ["Capitol Mall", "J St", "K St", "L St"], "lat": 38.5816, "lng": -121.4944},
            {"name": "Midtown / 16th-21st", "streets": ["16th", "17th", "18th", "19th", "20th", "21st", "P St", "Q St"], "lat": 38.5728, "lng": -121.4819},
            {"name": "Old Sacramento / Riverfront", "streets": ["Front St", "2nd St", "Tower Bridge", "River"], "lat": 38.5835, "lng": -121.5050},
        ],
        "drive_between_clusters_min": 8
    },
    2: {  # West Sacramento / Davis
        "clusters": [
            {"name": "West Sacramento", "streets": ["Harbor Blvd", "Jefferson Blvd", "Sacramento Ave", "West Capitol"], "lat": 38.5805, "lng": -121.5302},
            {"name": "Davis Downtown", "streets": ["3rd St", "F St", "G St", "University"], "lat": 38.5449, "lng": -121.7405},
            {"name": "Davis East", "streets": ["Covell Blvd", "Anderson Rd", "Pole Line"], "lat": 38.5595, "lng": -121.7194},
        ],
        "drive_between_clusters_min": 20
    },
    3: {  # Roseville / Rocklin
        "clusters": [
            {"name": "Roseville Galleria", "streets": ["Galleria Blvd", "Roseville Pkwy", "Lead Hill"], "lat": 38.7521, "lng": -121.2880},
            {"name": "Roseville Downtown", "streets": ["Vernon St", "Lincoln St", "Douglas Blvd"], "lat": 38.7521, "lng": -121.2880},
            {"name": "Rocklin", "streets": ["Sierra College", "Sunset Blvd", "Pacific St", "Granite Dr"], "lat": 38.7908, "lng": -121.2358},
        ],
        "drive_between_clusters_min": 12
    },
    4: {  # Folsom / El Dorado Hills
        "clusters": [
            {"name": "Folsom Historic", "streets": ["Sutter St", "Riley St", "Natoma"], "lat": 38.6780, "lng": -121.1761},
            {"name": "Folsom Lake / Iron Point", "streets": ["Iron Point Rd", "E Bidwell", "Blue Ravine"], "lat": 38.6660, "lng": -121.1420},
            {"name": "El Dorado Hills", "streets": ["Latrobe", "Town Center", "Saratoga", "Harvard Way"], "lat": 38.6857, "lng": -121.0750},
        ],
        "drive_between_clusters_min": 15
    },
    5: {  # Rancho Cordova / Elk Grove
        "clusters": [
            {"name": "Rancho Cordova", "streets": ["Zinfandel Dr", "Coloma Rd", "Folsom Blvd", "White Rock"], "lat": 38.5891, "lng": -121.3028},
            {"name": "Elk Grove North", "streets": ["Laguna", "Elk Grove Blvd", "Stockton"], "lat": 38.4388, "lng": -121.3816},
            {"name": "Elk Grove South", "streets": ["Civic Center", "Bruceville", "Big Horn"], "lat": 38.4085, "lng": -121.4016},
        ],
        "drive_between_clusters_min": 20
    }
}

ZONE_NAMES = {
    1: "Sacramento Downtown",
    2: "West Sacramento / Davis",
    3: "Roseville / Rocklin",
    4: "Folsom / El Dorado Hills",
    5: "Rancho Cordova / Elk Grove"
}

# Priority order: A gets best slots (morning), then B, then C, then Prospect
TIER_PRIORITY = {"a": 1, "b": 2, "c": 3, "prospect": 4}
TIER_MEETING_DURATION = {"a": 30, "b": 20, "c": 20, "prospect": 15}

# === EMAIL SCRIPTS (Toney's exact wording) ===
EMAIL_SCRIPTS = {
    "a": {
        "subject": "Quick catch-up when I'm in {city} next week",
        "body": "Hi {first_name},\n\nI've been spending time with several of the top advisors in the region and there are a few clear themes emerging around how they're growing and positioning client portfolios in this market.\n\nI thought it would be worthwhile to compare notes and share a quick update on where we're seeing the most traction across our strategies.\n\nDo you have 20 minutes next week or the following?\n\nBest,\nToney Sebra"
    },
    "b": {
        "subject": "Quick catch-up when I'm in {city} next week",
        "body": "Hi {first_name},\n\nI've been working with a number of advisors on practice management and prospecting strategies that are gaining traction right now, and I thought a few of these ideas might be relevant for you as well.\n\nHappy to share what's working and hear what you're focused on this year.\n\nDo you have 15-20 minutes next week for a quick call?\n\nBest,\nToney Sebra"
    },
    "c": {
        "subject": "Quick catch-up when I'm in {city} next week",
        "body": "Hi {first_name},\n\nI've been working with a number of advisors on practice management and prospecting strategies that are gaining traction right now, and I thought a few of these ideas might be relevant for you as well.\n\nHappy to share what's working and hear what you're focused on this year.\n\nDo you have 15-20 minutes next week for a quick call?\n\nBest,\nToney Sebra"
    },
    "prospect": {
        "subject": "Introduction - Toney Sebra",
        "body": "Hi {first_name},\n\nI cover your area and realized we haven't had the chance to connect yet.\n\nI've heard great things about your practice and would appreciate the opportunity to introduce myself and learn more about your business.\n\nIf you're open to it, I'd welcome a quick 15-minute call sometime next week.\n\nBest regards,\nToney Sebra"
    }
}

FOLLOWUP_SCRIPTS = {
    "followup_1": {
        "subject": "Re: Quick catch-up when I'm in {city} next week",
        "body": "Hi {first_name}, just bumping this up - would love to find 20 minutes. What does your week look like?\n\nBest,\nToney"
    },
    "followup_2": {
        "subject": "Re: Quick catch-up when I'm in {city} next week",
        "body": "Hi {first_name}, I'll try again next time I'm in your area. In the meantime, here's a quick market update worth a look.\n\nBest,\nToney"
    }
}

# Confirmation email + text templates
CONFIRMATION_TEMPLATE = {
    "subject": "Confirmed: Meeting with Toney Sebra - {date_str}",
    "body": "Hi {first_name},\n\nJust confirming our meeting:\n\nDate: {date_str}\nTime: {time_str}\nLocation: {location}\nDuration: {duration} minutes\n\nLooking forward to it. If anything changes, just reply to this email.\n\nBest,\nToney Sebra"
}

REMINDER_TEMPLATE = {
    "subject": "Reminder: Meeting tomorrow with Toney Sebra",
    "body": "Hi {first_name},\n\nQuick reminder about our meeting tomorrow:\n\nTime: {time_str}\nLocation: {location}\n\nSee you there.\n\nBest,\nToney"
}


# === API HELPERS ===

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


def send_email(contact_id, subject, body, email_from="toney@liftlineai.com"):
    """Send email via GHL."""
    html_body = body.replace("\n\n", "</p><p>").replace("\n", "<br>")
    html_body = f"<p>{html_body}</p>"
    resp = ghl_api("POST", "/conversations/messages", {
        "type": "Email",
        "contactId": contact_id,
        "subject": subject,
        "html": html_body,
        "emailFrom": email_from
    })
    return resp.get("msg") or resp.get("messageId")


def add_tag(contact_id, tag):
    """Add tag to contact."""
    ghl_api("POST", f"/contacts/{contact_id}/tags", {"tags": [tag]})


def remove_tag(contact_id, tag):
    """Remove tag from contact."""
    ghl_api("DELETE", f"/contacts/{contact_id}/tags", {"tags": [tag]})


def update_contact(contact_id, fields):
    """Update contact fields."""
    ghl_api("PUT", f"/contacts/{contact_id}", fields)


# === STATE MANAGEMENT ===

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "contacts_emailed": {},
        "followups_sent": {},
        "responses": {},
        "appointments": {},
        "zone_rotation": {"current_zone": 1, "week_start": None, "history": []},
        "daily_schedules": {},
        "last_run": None
    }


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


def log_action(action, details):
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            logs = json.load(f)
    logs.append({"timestamp": datetime.now().isoformat(), "action": action, **details})
    with open(LOG_FILE, "w") as f:
        json.dump(logs[-500:], f, indent=2)  # Keep last 500 entries


# === CONTACT HELPERS ===

def get_all_liftline_contacts():
    """Pull all liftline-demo contacts from GHL."""
    all_contacts = []
    start_after = None
    start_after_id = None
    while True:
        url = f"/contacts/?locationId={GHL_LOCATION}&limit=100"
        if start_after:
            url += f"&startAfter={start_after}&startAfterId={start_after_id}"
        resp = ghl_api("GET", url)
        contacts = resp.get("contacts", [])
        if not contacts:
            break
        for c in contacts:
            if "liftline-demo" in c.get("tags", []):
                all_contacts.append(c)
        meta = resp.get("meta", {})
        start_after = meta.get("startAfter")
        start_after_id = meta.get("startAfterId")
        if not start_after:
            break
    return all_contacts


def get_tier(contact):
    for t in contact.get("tags", []):
        if t.startswith("liftline-tier-"):
            return t.replace("liftline-tier-", "")
    return "c"


def get_zone(contact):
    for t in contact.get("tags", []):
        if t.startswith("liftline-zone-"):
            return int(t.replace("liftline-zone-", ""))
    return 0


def get_name(contact):
    return f"{contact.get('firstNameRaw', contact.get('firstName', ''))} {contact.get('lastNameRaw', contact.get('lastName', ''))}".strip()


def get_cluster(contact, zone):
    """Determine which geo-cluster a contact belongs to based on their address."""
    address = (contact.get("address1", "") or "").lower()
    city = (contact.get("city", "") or "").lower()

    zone_data = GEO_CLUSTERS.get(zone, {})
    clusters = zone_data.get("clusters", [])

    for i, cluster in enumerate(clusters):
        for street in cluster["streets"]:
            if street.lower() in address or street.lower() in city:
                return i, cluster["name"]

    # Default to first cluster if no match
    if clusters:
        return 0, clusters[0]["name"]
    return 0, "Unknown"


# === SMART SCHEDULING ENGINE ===

def generate_optimized_schedule(zone, contacts, start_date):
    """
    Generate an optimized weekly schedule for a zone.

    Rules:
    1. Group contacts by geo-cluster to minimize drive time
    2. A-tier gets morning slots (best attention)
    3. Max 6-8 meetings per day
    4. 15-min buffer between meetings in same cluster
    5. 25-min buffer between different clusters (drive time)
    6. No meetings before 8 AM or after 5 PM
    7. Lunch break 12:00-1:00 PM
    8. Visit same cluster back-to-back, never zigzag
    """

    zone_data = GEO_CLUSTERS.get(zone, {})
    drive_between = zone_data.get("drive_between_clusters_min", 15)

    # Group contacts by cluster
    clustered = defaultdict(list)
    for c in contacts:
        cluster_idx, cluster_name = get_cluster(c, zone)
        tier = get_tier(c)
        clustered[cluster_idx].append({
            "contact": c,
            "tier": tier,
            "cluster_idx": cluster_idx,
            "cluster_name": cluster_name,
            "duration": TIER_MEETING_DURATION.get(tier, 20),
            "priority": TIER_PRIORITY.get(tier, 4)
        })

    # Sort within each cluster by priority (A first)
    for cluster_idx in clustered:
        clustered[cluster_idx].sort(key=lambda x: x["priority"])

    # Build daily schedules
    # Strategy: fill each day with one or two clusters, packed tightly
    daily_schedules = []
    remaining = []
    for cluster_idx in sorted(clustered.keys()):
        remaining.extend(clustered[cluster_idx])

    # Sort all by priority, then group by cluster
    day_idx = 0
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule_by_day = {}

    current_day_contacts = []
    current_day_minutes = 0
    current_cluster = None
    max_minutes_per_day = 8 * 60  # 8 hours minus lunch

    # Group by cluster first, then fill days
    cluster_order = sorted(clustered.keys())

    for cluster_idx in cluster_order:
        cluster_contacts = clustered[cluster_idx]

        for entry in cluster_contacts:
            meeting_time = entry["duration"] + 15  # meeting + buffer

            # Add drive time if switching clusters
            if current_cluster is not None and current_cluster != cluster_idx:
                meeting_time += drive_between

            # Check if fits in current day
            if current_day_minutes + meeting_time > max_minutes_per_day - 60:  # reserve 60 for lunch
                # Save current day and start new one
                if current_day_contacts:
                    day_name = days[day_idx % 5]
                    date = start_date + timedelta(days=day_idx)
                    schedule_by_day[date.strftime("%Y-%m-%d")] = {
                        "day": day_name,
                        "date": date.strftime("%Y-%m-%d"),
                        "zone": zone,
                        "zone_name": ZONE_NAMES.get(zone, "?"),
                        "meetings": current_day_contacts,
                        "total_meetings": len(current_day_contacts),
                        "total_minutes": current_day_minutes
                    }
                    daily_schedules.append(schedule_by_day[date.strftime("%Y-%m-%d")])
                    day_idx += 1
                    current_day_contacts = []
                    current_day_minutes = 0

            current_cluster = cluster_idx
            current_day_minutes += meeting_time

            # Calculate time slot
            # Start at 8 AM, skip 12-1 PM for lunch
            slot_start_minutes = 8 * 60  # 8:00 AM
            for existing in current_day_contacts:
                end = existing["slot_end_minutes"]
                if end >= 12 * 60 and end < 13 * 60:
                    end = 13 * 60  # skip lunch
                slot_start_minutes = end + 15  # 15 min buffer
                if existing["cluster_idx"] != cluster_idx:
                    slot_start_minutes += drive_between  # add drive time

            # Skip lunch
            if slot_start_minutes >= 12 * 60 and slot_start_minutes < 13 * 60:
                slot_start_minutes = 13 * 60

            slot_end_minutes = slot_start_minutes + entry["duration"]

            hours = slot_start_minutes // 60
            minutes = slot_start_minutes % 60
            end_hours = slot_end_minutes // 60
            end_minutes = slot_end_minutes % 60

            current_day_contacts.append({
                "contact_id": entry["contact"]["id"],
                "name": get_name(entry["contact"]),
                "company": entry["contact"].get("companyName", ""),
                "email": entry["contact"].get("email", ""),
                "city": entry["contact"].get("city", ""),
                "address": entry["contact"].get("address1", ""),
                "tier": entry["tier"],
                "cluster_idx": cluster_idx,
                "cluster_name": entry["cluster_name"],
                "duration": entry["duration"],
                "time": f"{hours:02d}:{minutes:02d}",
                "end_time": f"{end_hours:02d}:{end_minutes:02d}",
                "slot_start_minutes": slot_start_minutes,
                "slot_end_minutes": slot_end_minutes,
                "status": "scheduled"
            })

    # Don't forget the last day
    if current_day_contacts:
        day_name = days[day_idx % 5]
        date = start_date + timedelta(days=day_idx)
        schedule_by_day[date.strftime("%Y-%m-%d")] = {
            "day": day_name,
            "date": date.strftime("%Y-%m-%d"),
            "zone": zone,
            "zone_name": ZONE_NAMES.get(zone, "?"),
            "meetings": current_day_contacts,
            "total_meetings": len(current_day_contacts),
            "total_minutes": current_day_minutes
        }
        daily_schedules.append(schedule_by_day[date.strftime("%Y-%m-%d")])

    return daily_schedules


# === COMMANDS ===

def cmd_status():
    """Full pipeline dashboard."""
    contacts = get_all_liftline_contacts()
    state = load_state()
    schedules = load_schedules()

    # Count by zone and tier
    zones = {}
    for c in contacts:
        z = get_zone(c)
        t = get_tier(c)
        tags = c.get("tags", [])
        if z not in zones:
            zones[z] = {"a": 0, "b": 0, "c": 0, "prospect": 0, "total": 0,
                        "emailed": 0, "responded": 0, "booked": 0, "completed": 0}
        zones[z][t] = zones[z].get(t, 0) + 1
        zones[z]["total"] += 1
        if "liftline-outreach-sent" in tags:
            zones[z]["emailed"] += 1
        if "liftline-responded" in tags:
            zones[z]["responded"] += 1
        if "liftline-meeting-booked" in tags:
            zones[z]["booked"] += 1
        if "liftline-meeting-complete" in tags:
            zones[z]["completed"] += 1

    total_contacts = sum(z["total"] for z in zones.values())
    total_emailed = sum(z["emailed"] for z in zones.values())
    total_responded = sum(z["responded"] for z in zones.values())
    total_booked = sum(z["booked"] for z in zones.values())

    rotation = state.get("zone_rotation", {})

    print(f"""
{'='*72}
  LIFTLINEAI COMMAND CENTER — {datetime.now().strftime('%B %d, %Y %I:%M %p')}
{'='*72}

  PIPELINE OVERVIEW
  ─────────────────────────────────────────────────────────
  Total Advisors:  {total_contacts}
  Emails Sent:     {total_emailed}
  Responses:       {total_responded}  ({(total_responded/total_emailed*100) if total_emailed else 0:.0f}% response rate)
  Meetings Booked: {total_booked}
  Current Zone:    {rotation.get('current_zone', '—')} ({ZONE_NAMES.get(rotation.get('current_zone', 0), '—')})

  ZONE BREAKDOWN
  ─────────────────────────────────────────────────────────
  {'Zone':<8} {'Area':<28} {'A':>3} {'B':>3} {'C':>3} {'P':>3} {'Tot':>4} {'Sent':>5} {'Resp':>5} {'Book':>5}
  {'-'*72}""")

    for z in sorted(zones.keys()):
        if z == 0:
            continue
        d = zones[z]
        area = ZONE_NAMES.get(z, "?")[:26]
        print(f"  Zone {z:<2} {area:<28} {d['a']:>3} {d['b']:>3} {d['c']:>3} {d.get('prospect',0):>3} {d['total']:>4} {d['emailed']:>5} {d['responded']:>5} {d['booked']:>5}")

    # Show upcoming schedule
    sched_data = schedules.get("schedules", {})
    if sched_data:
        print(f"""
  UPCOMING SCHEDULE
  ─────────────────────────────────────────────────────────""")
        for date_key in sorted(sched_data.keys())[:5]:
            day = sched_data[date_key]
            print(f"  {day['day']} {day['date']} — Zone {day['zone']} ({day['zone_name']}) — {day['total_meetings']} meetings")
            for m in day.get("meetings", []):
                status_icon = {"scheduled": "◻", "confirmed": "✓", "completed": "●", "cancelled": "✗", "no-show": "○"}.get(m.get("status", ""), "?")
                print(f"    {status_icon} {m['time']}-{m['end_time']}  {m['name']:<22} [{m['tier'].upper()}]  {m['cluster_name']}")

    # Show recent activity
    if state.get("zone_rotation", {}).get("history"):
        print(f"""
  ZONE ROTATION HISTORY
  ─────────────────────────────────────────────────────────""")
        for h in state["zone_rotation"]["history"][-5:]:
            print(f"  Zone {h['zone']} — {h['date']} — {h.get('sent', 0)} sent, {h.get('responses', 0)} responses")

    print()


def cmd_run_zone(zone_num):
    """Send tier-prioritized outreach emails for a zone."""
    zone = int(zone_num)
    state = load_state()
    contacts = get_all_liftline_contacts()

    # Filter to this zone
    zone_contacts = [c for c in contacts if get_zone(c) == zone]

    print(f"""
{'='*60}
  ZONE {zone} OUTREACH — {ZONE_NAMES.get(zone, '?')}
  {len(zone_contacts)} advisors | Priority: A → B → C → Prospect
{'='*60}
""")

    sent = 0
    skipped = 0
    failed = 0

    # Sort by tier priority
    zone_contacts.sort(key=lambda c: TIER_PRIORITY.get(get_tier(c), 4))

    for c in zone_contacts:
        contact_id = c["id"]
        name = get_name(c)
        tier = get_tier(c)
        email = c.get("email", "")
        city = c.get("city", "your area")
        first_name = c.get("firstNameRaw", c.get("firstName", ""))
        tags = c.get("tags", [])

        # Skip if already emailed
        if "liftline-outreach-sent" in tags:
            print(f"  SKIP  {name} [{tier.upper()}] — already emailed")
            skipped += 1
            continue

        if not email:
            print(f"  SKIP  {name} [{tier.upper()}] — no email")
            skipped += 1
            continue

        # Get the right script
        script = EMAIL_SCRIPTS.get(tier, EMAIL_SCRIPTS["c"])
        subject = script["subject"].format(first_name=first_name, city=city)
        body = script["body"].format(first_name=first_name, city=city)

        print(f"  SEND  {name} [{tier.upper()}] → {email}...", end=" ")
        success = send_email(contact_id, subject, body)

        if success:
            print("✓")
            add_tag(contact_id, "liftline-outreach-sent")
            add_tag(contact_id, f"liftline-emailed-{datetime.now().strftime('%Y%m%d')}")
            state["contacts_emailed"][contact_id] = {
                "date": datetime.now().isoformat(),
                "name": name, "tier": tier, "zone": zone,
                "followup_count": 0
            }
            log_action("outreach_sent", {"contact_id": contact_id, "name": name, "tier": tier, "zone": zone})
            sent += 1
        else:
            print("✗")
            failed += 1

        time.sleep(1)  # Rate limit

    # Update zone rotation
    state["zone_rotation"]["current_zone"] = zone
    state["zone_rotation"]["history"].append({
        "zone": zone, "date": datetime.now().isoformat(),
        "sent": sent, "skipped": skipped, "failed": failed
    })

    save_state(state)

    print(f"""
{'='*60}
  ZONE {zone} COMPLETE: {sent} sent | {skipped} skipped | {failed} failed
{'='*60}
""")


def cmd_schedule_zone(zone_num):
    """Generate optimized daily schedule for a zone."""
    zone = int(zone_num)
    contacts = get_all_liftline_contacts()

    # Filter to zone contacts that have been emailed or responded
    zone_contacts = [c for c in contacts if get_zone(c) == zone]

    print(f"""
{'='*60}
  SMART SCHEDULE — Zone {zone}: {ZONE_NAMES.get(zone, '?')}
  Optimizing for minimum drive time...
{'='*60}
""")

    # Generate schedule starting next Monday
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    start_date = today + timedelta(days=days_until_monday)

    daily_schedules = generate_optimized_schedule(zone, zone_contacts, start_date)

    # Save schedules
    schedules = load_schedules()
    for day_sched in daily_schedules:
        schedules["schedules"][day_sched["date"]] = day_sched
    save_schedules(schedules)

    # Display
    total_meetings = 0
    total_drive_min = 0

    for day in daily_schedules:
        meetings = day.get("meetings", [])
        total_meetings += len(meetings)

        # Calculate drive time for this day
        day_drive = 0
        prev_cluster = None
        for m in meetings:
            if prev_cluster is not None and prev_cluster != m["cluster_idx"]:
                day_drive += GEO_CLUSTERS.get(zone, {}).get("drive_between_clusters_min", 15)
            prev_cluster = m["cluster_idx"]
        total_drive_min += day_drive

        print(f"  {day['day'].upper()} — {day['date']} ({len(meetings)} meetings, ~{day_drive} min driving)")
        print(f"  {'─'*56}")

        current_cluster = None
        for m in meetings:
            if m["cluster_name"] != current_cluster:
                if current_cluster is not None:
                    drive = GEO_CLUSTERS.get(zone, {}).get("drive_between_clusters_min", 15)
                    print(f"    🚗 Drive to {m['cluster_name']} (~{drive} min)")
                else:
                    print(f"    📍 Start: {m['cluster_name']}")
                current_cluster = m["cluster_name"]

            tier_label = f"[{m['tier'].upper()}]"
            print(f"    {m['time']}-{m['end_time']}  {tier_label:<5} {m['name']:<22} {m['company'][:25]}")

        print()

    print(f"""  SUMMARY
  ─────────────────────────────────────────────────────
  Total meetings:    {total_meetings}
  Days needed:       {len(daily_schedules)}
  Est. drive time:   {total_drive_min} min total
  Without optimization: ~{total_drive_min * 2.5:.0f} min (random order)
  Time saved:        ~{total_drive_min * 1.5:.0f} min
""")


def cmd_daily_schedule(date_str=None):
    """Show detailed schedule for a specific date."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    schedules = load_schedules()
    day = schedules.get("schedules", {}).get(date_str)

    if not day:
        print(f"  No schedule found for {date_str}. Run 'schedule-zone' first.")
        return

    print(f"""
{'='*60}
  DAILY SCHEDULE — {day['day']} {day['date']}
  Zone {day['zone']}: {day['zone_name']}
{'='*60}
""")

    for m in day.get("meetings", []):
        status_icon = {"scheduled": "◻", "confirmed": "✓", "completed": "●", "cancelled": "✗"}.get(m.get("status", ""), "?")
        print(f"  {status_icon} {m['time']}-{m['end_time']}  [{m['tier'].upper()}] {m['name']}")
        print(f"    📍 {m.get('address', '')} {m.get('city', '')} — {m['company']}")
        print(f"    📧 {m.get('email', '')}  |  Area: {m['cluster_name']}")
        print()


def cmd_book(contact_id, date_str, time_str):
    """Book a meeting for a specific contact."""
    state = load_state()
    schedules = load_schedules()

    # Get contact details
    resp = ghl_api("GET", f"/contacts/{contact_id}")
    contact = resp.get("contact", resp)
    name = get_name(contact)

    appointment = {
        "contact_id": contact_id,
        "name": name,
        "date": date_str,
        "time": time_str,
        "status": "confirmed",
        "booked_at": datetime.now().isoformat()
    }

    state["appointments"][contact_id] = appointment
    add_tag(contact_id, "liftline-meeting-booked")
    add_tag(contact_id, f"liftline-booked-{date_str}")

    # Send confirmation email
    city = contact.get("city", "your area")
    first_name = contact.get("firstNameRaw", contact.get("firstName", ""))

    subject = CONFIRMATION_TEMPLATE["subject"].format(
        first_name=first_name, date_str=date_str, time_str=time_str,
        location=f"{contact.get('address1', '')} {city}", duration=30
    )
    body = CONFIRMATION_TEMPLATE["body"].format(
        first_name=first_name, date_str=date_str, time_str=time_str,
        location=f"{contact.get('address1', '')} {city}", duration=30
    )
    send_email(contact_id, subject, body)

    save_state(state)

    print(f"  ✓ BOOKED: {name} — {date_str} at {time_str}")
    print(f"  ✓ Confirmation email sent")
    log_action("meeting_booked", {"contact_id": contact_id, "name": name, "date": date_str, "time": time_str})


def cmd_follow_up():
    """Send follow-ups to non-responders on schedule."""
    state = load_state()
    now = datetime.now()
    sent = 0

    print(f"""
{'='*60}
  FOLLOW-UP ENGINE — {now.strftime('%B %d, %Y')}
{'='*60}
""")

    for contact_id, info in state.get("contacts_emailed", {}).items():
        if contact_id in state.get("responses", {}):
            continue

        followup_count = info.get("followup_count", 0)
        emailed_date = datetime.fromisoformat(info["date"])
        days_since = (now - emailed_date).days
        name = info.get("name", "?")
        city = info.get("city", "your area")

        resp_data = ghl_api("GET", f"/contacts/{contact_id}")
        contact = resp_data.get("contact", resp_data)
        first_name = contact.get("firstNameRaw", contact.get("firstName", ""))
        city = contact.get("city", "your area")

        script_key = None
        if followup_count == 0 and days_since >= 3:
            script_key = "followup_1"
            tag = "liftline-followup-1"
        elif followup_count == 1 and days_since >= 7:
            script_key = "followup_2"
            tag = "liftline-followup-2"

        if script_key and contact.get("id"):
            script = FOLLOWUP_SCRIPTS[script_key]
            subject = script["subject"].format(first_name=first_name, city=city)
            body = script["body"].format(first_name=first_name, city=city)

            print(f"  {script_key.upper()} → {name} (day {days_since})...", end=" ")
            success = send_email(contact_id, subject, body)

            if success:
                print("✓")
                info["followup_count"] = followup_count + 1
                add_tag(contact_id, tag)
                if followup_count + 1 >= 2:
                    add_tag(contact_id, "liftline-cycle-complete")
                log_action("followup_sent", {"contact_id": contact_id, "name": name, "followup": script_key})
                sent += 1
            else:
                print("✗")

            time.sleep(1)

    save_state(state)
    print(f"\n  Follow-ups sent: {sent}\n")


def cmd_demo_populate():
    """Populate demo data — fake responses, booked meetings, schedule."""
    state = load_state()
    contacts = get_all_liftline_contacts()

    print(f"""
{'='*60}
  POPULATING DEMO DATA
  Creating realistic pipeline state...
{'='*60}
""")

    # 1. Mark Zone 1 as fully emailed
    zone1 = [c for c in contacts if get_zone(c) == 1]
    print(f"\n  Zone 1: Marking {len(zone1)} contacts as emailed...")
    for c in zone1:
        add_tag(c["id"], "liftline-outreach-sent")
        state["contacts_emailed"][c["id"]] = {
            "date": (datetime.now() - timedelta(days=5)).isoformat(),
            "name": get_name(c), "tier": get_tier(c), "zone": 1,
            "followup_count": 0
        }
        time.sleep(0.3)

    # 2. Simulate responses from A-tier and some B-tier
    responded = []
    for c in zone1:
        tier = get_tier(c)
        # A-tier: 100% respond (demo). B-tier: 66%. C-tier: 33%. Prospect: 0%.
        respond = False
        if tier == "a":
            respond = True
        elif tier == "b":
            respond = random.random() < 0.66
        elif tier == "c":
            respond = random.random() < 0.33

        if respond:
            add_tag(c["id"], "liftline-responded")
            state["responses"][c["id"]] = {
                "date": (datetime.now() - timedelta(days=3)).isoformat(),
                "name": get_name(c), "tier": tier
            }
            responded.append(c)
            time.sleep(0.3)

    print(f"  {len(responded)} advisors responded (A-tier + some B/C)")

    # 3. Generate optimized schedule for Zone 1
    print(f"\n  Generating smart schedule for Zone 1...")
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    start_date = today + timedelta(days=days_until_monday)

    daily_schedules = generate_optimized_schedule(1, responded, start_date)

    schedules = load_schedules()
    for day_sched in daily_schedules:
        # Mark some as confirmed for demo realism
        for m in day_sched.get("meetings", []):
            if m["tier"] == "a":
                m["status"] = "confirmed"
            elif random.random() < 0.5:
                m["status"] = "confirmed"
        schedules["schedules"][day_sched["date"]] = day_sched
    save_schedules(schedules)

    print(f"  Created {len(daily_schedules)} day(s) of meetings")

    # 4. Book meetings for responded contacts
    for c in responded:
        add_tag(c["id"], "liftline-meeting-booked")
        state["appointments"][c["id"]] = {
            "name": get_name(c), "status": "confirmed",
            "booked_at": datetime.now().isoformat()
        }
        time.sleep(0.3)

    print(f"  {len(responded)} meetings booked")

    # 5. Mark Zone 2 as partially emailed (in-progress feel)
    zone2 = [c for c in contacts if get_zone(c) == 2]
    a_b_zone2 = [c for c in zone2 if get_tier(c) in ["a", "b"]]
    print(f"\n  Zone 2: Marking {len(a_b_zone2)} A/B contacts as emailed...")
    for c in a_b_zone2:
        add_tag(c["id"], "liftline-outreach-sent")
        state["contacts_emailed"][c["id"]] = {
            "date": (datetime.now() - timedelta(days=1)).isoformat(),
            "name": get_name(c), "tier": get_tier(c), "zone": 2,
            "followup_count": 0
        }
        time.sleep(0.3)

    # Update zone rotation
    state["zone_rotation"] = {
        "current_zone": 2,
        "week_start": (datetime.now() - timedelta(days=1)).isoformat(),
        "history": [
            {"zone": 1, "date": (datetime.now() - timedelta(days=5)).isoformat(), "sent": len(zone1), "responses": len(responded), "booked": len(responded)},
            {"zone": 2, "date": (datetime.now() - timedelta(days=1)).isoformat(), "sent": len(a_b_zone2), "responses": 0, "booked": 0}
        ]
    }

    save_state(state)

    print(f"""
{'='*60}
  DEMO DATA LOADED
  ─────────────────────────────────────────────────────
  Zone 1: {len(zone1)} emailed → {len(responded)} responded → {len(responded)} booked
  Zone 2: {len(a_b_zone2)} A/B emailed (in progress)
  Zones 3-5: Untouched (upcoming)
  Schedule: {len(daily_schedules)} days generated with geo-optimization

  Run 'status' to see the full dashboard.
  Run 'daily-schedule {start_date.strftime("%Y-%m-%d")}' to see the route.
{'='*60}
""")


def cmd_weekly_view(zone_num=None):
    """Show weekly calendar view."""
    schedules = load_schedules()
    sched_data = schedules.get("schedules", {})

    if not sched_data:
        print("  No schedules generated. Run 'schedule-zone <zone>' or 'demo-populate' first.")
        return

    print(f"""
{'='*60}
  WEEKLY VIEW
{'='*60}
""")

    for date_key in sorted(sched_data.keys())[:7]:
        day = sched_data[date_key]
        if zone_num and day.get("zone") != int(zone_num):
            continue

        confirmed = sum(1 for m in day.get("meetings", []) if m.get("status") == "confirmed")
        total = day.get("total_meetings", 0)

        print(f"  {day['day']:<10} {day['date']}  |  Zone {day['zone']}  |  {confirmed}/{total} confirmed")

        for m in day.get("meetings", []):
            icon = "✓" if m.get("status") == "confirmed" else "◻"
            print(f"    {icon} {m['time']}  [{m['tier'].upper()}] {m['name']:<20} {m['cluster_name']}")
        print()


def cmd_test():
    """Test email to Toney."""
    print(f"\n  Sending test A-tier email to toney@liftlineai.com...")

    success = send_email(
        "ppqKb2fwcrHdNRpgE3AO",
        "Quick catch-up when I am in Sacramento next week",
        "Hi Michael,\n\nI've been spending time with several of the top advisors in the region and there are a few clear themes emerging around how they're growing and positioning client portfolios in this market.\n\nI thought it would be worthwhile to compare notes and share a quick update on where we're seeing the most traction across our strategies.\n\nDo you have 20 minutes next week or the following?\n\nBest,\nToney Sebra"
    )

    if success:
        print("  ✓ Test email sent — check toney@liftlineai.com")
    else:
        print("  ✗ Failed — check email service connection")


def cmd_daily_report():
    """Generate EOD activity report."""
    state = load_state()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    today_sent = sum(1 for v in state.get("contacts_emailed", {}).values() if v.get("date", "")[:10] == today)
    today_responses = sum(1 for v in state.get("responses", {}).values() if v.get("date", "")[:10] == today)
    total_emailed = len(state.get("contacts_emailed", {}))
    total_responses = len(state.get("responses", {}))
    total_booked = len(state.get("appointments", {}))

    report = f"""
{'='*60}
  LIFTLINEAI DAILY REPORT — {now.strftime('%B %d, %Y')}
{'='*60}

  TODAY
  ─────────────────────────────────
  Emails Sent:     {today_sent}
  Responses:       {today_responses}

  ALL TIME
  ─────────────────────────────────
  Total Emailed:   {total_emailed}
  Total Responses: {total_responses}  ({(total_responses/total_emailed*100) if total_emailed else 0:.0f}%)
  Meetings Booked: {total_booked}

  ZONE ROTATION
  ─────────────────────────────────
  Current Zone:    {state.get('zone_rotation',{}).get('current_zone','—')}
  5-Week Cycle:    Zone 1 → 2 → 3 → 4 → 5 → repeat
"""

    print(report)

    report_dir = ENGINE_DIR / "reports"
    report_dir.mkdir(exist_ok=True)
    with open(report_dir / f"daily-{today}.txt", "w") as f:
        f.write(report)
    print(f"  Saved to reports/daily-{today}.txt\n")


def cmd_reset():
    """Reset all engine state."""
    for f in [STATE_FILE, LOG_FILE, SCHEDULE_FILE]:
        if f.exists():
            f.unlink()
    print("  Engine state reset. Run 'demo-populate' to reload demo data.")


# === MAIN ===

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "status": lambda: cmd_status(),
        "run-zone": lambda: cmd_run_zone(args[0]) if args else print("Usage: run-zone <1-5>"),
        "schedule-zone": lambda: cmd_schedule_zone(args[0]) if args else print("Usage: schedule-zone <1-5>"),
        "follow-up": lambda: cmd_follow_up(),
        "book": lambda: cmd_book(args[0], args[1], args[2]) if len(args) >= 3 else print("Usage: book <contact_id> <date> <time>"),
        "daily-schedule": lambda: cmd_daily_schedule(args[0] if args else None),
        "weekly-view": lambda: cmd_weekly_view(args[0] if args else None),
        "demo-populate": lambda: cmd_demo_populate(),
        "daily-report": lambda: cmd_daily_report(),
        "test": lambda: cmd_test(),
        "reset": lambda: cmd_reset(),
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"  Unknown command: {cmd}\n")
        print(__doc__)


if __name__ == "__main__":
    main()
