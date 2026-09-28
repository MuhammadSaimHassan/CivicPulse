"""Idempotent seed: `python -m app.seed`.

Loads realistic complaints (Urdu-influenced English, as citizens actually
write them) spread across every category. Each row has a deterministic UUID
(uuid5 of its text), and the insert is ON CONFLICT (id) DO NOTHING — so
running the seed twice, or on every `docker compose up`, changes nothing the
second time.

Seed rows are triaged by RuleBasedTriage, not the LLM: seeding must never
spend API quota or depend on the network.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import build_engine, build_session_factory
from app.domain import Status
from app.providers.triage.rules import RuleBasedTriage
from app.repositories.complaint_repository import ComplaintRepository

log = logging.getLogger("civicpulse.seed")

SEED_NAMESPACE = uuid.UUID("6f1c3c8e-2b7a-4d7e-9a57-0c1e5a2b9f10")
SEED_EPOCH = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)

# (text, location, status)
SEED_COMPLAINTS: list[tuple[str, str, Status]] = [
    (
        "Burst water main flooding Street 12 since fajr, water entering ground floors. Please send team jaldi.",
        "Street 12, G-9/2, Islamabad",
        Status.open,
    ),
    (
        "Pani nahi aa raha for 4 days in our block, tanker mafia charging Rs 6000. No water for children.",
        "Block 7, Gulshan-e-Iqbal, Karachi",
        Status.in_progress,
    ),
    (
        "Pipe leak near the masjid, clean water wasting on road since last week.",
        "Near Jamia Masjid, Satellite Town, Rawalpindi",
        Status.open,
    ),
    (
        "Water supply line broken after road digging, dirty water coming in taps. Kids getting sick.",
        "Mohalla Islampura, Lahore",
        Status.open,
    ),
    (
        "Low water pressure every morning, motor bhi nahi chalti. Kindly consider checking the valve.",
        "Sector F-10/4, Islamabad",
        Status.resolved,
    ),
    (
        "Bijli ki taar gir gayi hai after the storm, live wire lying in the gali where children play.",
        "Gali 3, Dhok Kashmirian, Rawalpindi",
        Status.open,
    ),
    (
        "Transformer sparking since last night, loud blasts and smoke. Whole mohalla scared of fire.",
        "Model Colony, Malir, Karachi",
        Status.in_progress,
    ),
    (
        "Load shedding 10 hours daily in our area beyond the announced schedule, electricity outage at night.",
        "Sabzazar Block H, Lahore",
        Status.open,
    ),
    (
        "Voltage fluctuation has burned two fridges, please check the meter and transformer.",
        "Chaklala Scheme 3, Rawalpindi",
        Status.open,
    ),
    (
        "Electric pole leaning dangerously towards house after rain, danger for passersby.",
        "Street 21, I-8/2, Islamabad",
        Status.open,
    ),
    (
        "Gutter overflowing outside school gate, sewage water standing, kids walking through it daily.",
        "Government Boys School, Korangi 5, Karachi",
        Status.in_progress,
    ),
    (
        "Kachra not picked up for 2 weeks, garbage dump near market, bohat smell and mosquitoes.",
        "Liaquat Market, Rawalpindi",
        Status.open,
    ),
    (
        "Open manhole on main road, cover stolen. A motorcyclist already fell in yesterday.",
        "Main Double Road, Sector G-11, Islamabad",
        Status.open,
    ),
    (
        "Nala blocked with plastic bags, rain water plus sewage entering houses in low street.",
        "Nullah Lai side, Arya Mohalla, Rawalpindi",
        Status.open,
    ),
    (
        "Drain cleaning request for our street before monsoon, it is not urgent yet but please schedule.",
        "Street 5, Johar Town, Lahore",
        Status.resolved,
    ),
    (
        "Sewer line choked, dirty water coming back up in the washrooms of 20 houses.",
        "Orangi Town Sector 11, Karachi",
        Status.open,
    ),
    (
        "Huge pothole on the road near the chowk, rickshaws breaking axles, accident yesterday night.",
        "Committee Chowk, Rawalpindi",
        Status.open,
    ),
    (
        "Sarak toot gayi hai after the gas company digging, never repaired, dust everywhere.",
        "Street 14, Shadman, Lahore",
        Status.in_progress,
    ),
    (
        "Speed breaker without paint or sign, cars hitting it at night. Minor request: please paint it.",
        "Service Road, E-11/3, Islamabad",
        Status.open,
    ),
    (
        "Footpath broken and encroached by shops, elderly people walking on the main road.",
        "Saddar, Karachi",
        Status.rejected,
    ),
    (
        "Road carpeting left half done for three months, gravel flying into windscreens.",
        "Lehtrar Road, Tarlai, Islamabad",
        Status.open,
    ),
    (
        "Bridge railing collapsed on one side after truck hit it, danger for pedestrians at night.",
        "Nullah Bridge, Gulberg, Lahore",
        Status.open,
    ),
    (
        "Streetlight not working for a month, dark street, chori ho rahi hai at night.",
        "Street 9, Bahria Town Phase 4, Rawalpindi",
        Status.open,
    ),
    (
        "Khamba ki light band hai on the whole lane, women afraid to walk after maghrib.",
        "Lane 2, Defence Phase 2, Karachi",
        Status.in_progress,
    ),
    (
        "Street light bulb flickering on and off all night in front of house 42.",
        "Sector G-13/1, Islamabad",
        Status.resolved,
    ),
    (
        "Street lights on during the daytime, wastage of electricity. Kindly consider a timer.",
        "Canal Road service lane, Lahore",
        Status.open,
    ),
    (
        "All pole lights off on the park road, dark street, drug addicts sitting there at night.",
        "F-7 Markaz park road, Islamabad",
        Status.open,
    ),
    (
        "Stray dogs pack near the school gate, children scared, please do something.",
        "Township Block 4, Lahore",
        Status.open,
    ),
    (
        "Illegal construction blocking the gali, municipal permission not visible anywhere.",
        "Gulistan-e-Jauhar Block 13, Karachi",
        Status.rejected,
    ),
    (
        "Park grass not cut and swings broken, suggestion to repair before Eid.",
        "Sector I-10/1 community park, Islamabad",
        Status.open,
    ),
    (
        "Sewage mixing in drinking water pipe, pani mein badbu aur ganda rang. Many families ill.",
        "Lyari, Karachi",
        Status.open,
    ),
    (
        "Tree fell on electric wires in the storm, power outage in 3 streets since morning.",
        "Westridge 1, Rawalpindi",
        Status.in_progress,
    ),
    (
        "Garbage burning at the plot every evening, smoke entering homes, asthma patients suffering.",
        "Street 6, Model Town Extension, Lahore",
        Status.open,
    ),
    (
        "Loose manhole cover making loud noise and tilting when cars pass, request repair.",
        "Jinnah Avenue near Blue Area, Islamabad",
        Status.open,
    ),
]


def seed_rows() -> list[dict[str, object]]:
    rules = RuleBasedTriage()
    rows: list[dict[str, object]] = []
    for i, (text, location, status) in enumerate(SEED_COMPLAINTS):
        result = rules.triage(text, location)
        created = SEED_EPOCH + timedelta(hours=7 * i)
        rows.append(
            {
                "id": uuid.uuid5(SEED_NAMESPACE, text),
                "text": text,
                "location": location,
                "reporter_contact": None,
                "category": result.category,
                "priority": result.priority,
                "status": status,
                "ai_summary": result.summary,
                "triaged_by": "rules",
                "triage_latency_ms": 0,
                "created_at": created,
                "updated_at": created,
            }
        )
    return rows


def run() -> int:
    settings = get_settings()
    engine = build_engine(settings)
    try:
        with build_session_factory(engine)() as session:
            inserted = ComplaintRepository(session).insert_if_absent(seed_rows())
            session.commit()
    finally:
        engine.dispose()
    log.info("seed complete", extra={"inserted": inserted, "total_seed_rows": len(SEED_COMPLAINTS)})
    return inserted


if __name__ == "__main__":
    configure_logging(get_settings().log_level)
    run()
