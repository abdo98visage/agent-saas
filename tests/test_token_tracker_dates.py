from datetime import datetime, timezone

from app.services.token_tracker import current_quota_date


def test_quota_date_uses_riyadh_business_boundary():
    assert current_quota_date(datetime(2026, 7, 22, 20, 59, tzinfo=timezone.utc)) == "2026-07-22"
    assert current_quota_date(datetime(2026, 7, 22, 21, 0, tzinfo=timezone.utc)) == "2026-07-23"
