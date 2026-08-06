from __future__ import annotations

from datetime import datetime, timedelta, timezone

from application.pulse_feed import build_pulse_feed, score_signal
from models import Company, CompanySignal


def _signal(
    *,
    company: Company,
    title: str,
    confidence: float,
    hours_ago: float,
    source_type: str = "news_media",
) -> CompanySignal:
    now = datetime.now(timezone.utc)
    return CompanySignal(
        company_id=company.id,
        company=company,
        url=f"https://example.test/{title}",
        canonical_url=f"https://example.test/{title}",
        domain="example.test",
        source_type=source_type,
        confidence=confidence,
        title=title,
        last_seen_at=now - timedelta(hours=hours_ago),
        first_seen_at=now - timedelta(hours=hours_ago),
    )


def test_score_prefers_fresh_high_confidence_monitoring():
    monitoring = Company(name="Mon", tier="monitoring", priority="high")
    candidate = Company(name="Cand", tier="candidate", priority="low")
    hot = _signal(company=monitoring, title="hot", confidence=0.9, hours_ago=1)
    cold = _signal(company=candidate, title="cold", confidence=0.9, hours_ago=48)
    assert score_signal(hot) > score_signal(cold)


def test_build_pulse_feed_pins_must_see_and_paginates(tmp_path, monkeypatch):
    from database import Database
    from models import utc_now

    db = Database(f"sqlite:///{tmp_path / 'pulse.db'}")
    db.create_all()
    with db.session_factory() as session:
        company = Company(
            name="Acme",
            official_domain="acme.test",
            tier="target",
            priority="high",
            aliases=[],
        )
        session.add(company)
        session.commit()
        session.refresh(company)

        now = datetime.now(timezone.utc)
        rows = []
        for i in range(20):
            conf = 0.9 if i < 4 else 0.7
            rows.append(
                CompanySignal(
                    company_id=company.id,
                    url=f"https://news.test/{i}",
                    canonical_url=f"https://news.test/{i}",
                    domain="news.test",
                    source_type="news_media",
                    confidence=conf,
                    title=f"Signal {i}",
                    collector="test",
                    first_seen_at=now - timedelta(minutes=i * 20),
                    last_seen_at=now - timedelta(minutes=i * 20),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
            )
        session.add_all(rows)
        session.commit()

        page1 = build_pulse_feed(session, limit=5, offset=0, pin_limit=3, min_fill=5)
        assert page1["window"] in {"today", "24h", "7d"}
        assert len(page1["must_see"]) == 3
        assert all(item["priority"] == "High" for item in page1["must_see"])
        assert page1["feed_total"] >= 5
        assert len(page1["feed"]) == min(5, page1["feed_total"])
        assert page1["has_more"] is True

        page2 = build_pulse_feed(
            session, limit=5, offset=page1["next_offset"], pin_limit=3, min_fill=5
        )
        ids1 = {item["row"].id for item in page1["feed"]}
        ids2 = {item["row"].id for item in page2["feed"]}
        assert ids1.isdisjoint(ids2)
        assert page2["feed"]