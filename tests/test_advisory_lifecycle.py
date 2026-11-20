import json
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.app import app
from config import settings
from execution.engine import engine
from execution.logger import (
    record_advisory_log,
    get_advisories,
    get_active_advisory,
    update_advisory_status,
    get_advisory_performance_summary
)

client = TestClient(app)

def test_advisory_lifecycle_and_state_latch():
    # 1. Record an active advisory with strict 1:3 RRR
    adv = record_advisory_log(
        candle_timestamp=datetime.now().isoformat(),
        data_source="YAHOO",
        symbol="ETERNAL.NS",
        side="BUY",
        entry_price=100.0,
        stop_loss=98.0,
        target=106.0,
        quantity=100,
        directive="ACTION: BUY 100 SHARES of ETERNAL around ₹100.00 | TARGET: ₹106.00 | STOP LOSS: ₹98.00 | STRICT 1:3 RISK-TO-REWARD",
        reason="AI High-conviction trend setup",
        status="ACTIVE",
        risk_reward="1:3.00",
        brackets={
            "entry_price": 100.0,
            "stop_loss": 98.0,
            "target": 106.0,
            "risk_reward_ratio": "1:3.00",
            "suggested_quantity": 100,
            "estimated_max_risk_rupees": 200.0,
            "estimated_target_profit_rupees": 600.0
        }
    )
    assert adv is not None
    adv_id = adv["id"]

    # 2. Check get_active_advisory
    active = get_active_advisory()
    assert active is not None
    assert active["id"] == adv_id
    assert active["status"] == "ACTIVE"

    # 3. Test API endpoint /api/advisories/active
    res_active = client.get("/api/advisories/active")
    assert res_active.status_code == 200
    data_active = res_active.json()
    assert data_active["has_active_advisory"] is True
    assert data_active["advisory"]["id"] == adv_id

    # 4. Test Target Hit resolution (+3R)
    updated = update_advisory_status(
        advisory_id=adv_id,
        new_status="TARGET_HIT",
        exit_price=106.0,
        exit_time=datetime.now().isoformat(),
        realized_pnl=600.0,
        realized_points=6.0
    )
    assert updated is True

    # 5. Verify performance summary reflects the win
    summary = get_advisory_performance_summary()
    assert summary["target_hits"] >= 1
    assert summary["total_profit"] >= 600.0

    # 6. Test /api/advisories/history endpoint
    res_hist = client.get("/api/advisories/history")
    assert res_hist.status_code == 200
    data_hist = res_hist.json()
    assert data_hist["count"] >= 1
    assert "summary" in data_hist
    assert data_hist["summary"]["target_hits"] >= 1
