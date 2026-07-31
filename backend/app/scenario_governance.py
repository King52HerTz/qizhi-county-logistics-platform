from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ScenarioTransitionRecord, ScenarioVersionRecord


class ScenarioGovernanceError(ValueError):
    pass


def scenario_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_transition(
    session: Session,
    record: ScenarioVersionRecord,
    *,
    from_status: str | None,
    to_status: str,
    note: str | None,
    actor_id: int | None,
) -> None:
    session.add(
        ScenarioTransitionRecord(
            scenario_version_id=record.id,
            from_status=from_status,
            to_status=to_status,
            note=note,
            actor_id=actor_id,
        )
    )


def _locked_versions(session: Session, ids: list[int]) -> list[ScenarioVersionRecord]:
    return list(
        session.scalars(
            select(ScenarioVersionRecord)
            .where(ScenarioVersionRecord.id.in_(sorted(set(ids))))
            .order_by(ScenarioVersionRecord.id)
            .with_for_update()
        )
    )


def submit_scenario(
    session: Session,
    record: ScenarioVersionRecord,
    *,
    actor_id: int,
    note: str,
) -> ScenarioVersionRecord:
    locked = session.scalar(
        select(ScenarioVersionRecord)
        .where(ScenarioVersionRecord.id == record.id)
        .with_for_update()
    )
    if locked is None:
        raise ScenarioGovernanceError("场景版本不存在")
    if locked.status not in {"draft", "rejected"}:
        raise ScenarioGovernanceError("只有草稿或已驳回版本可以提交审核")
    previous = locked.status
    locked.status = "pending_review"
    locked.release_note = note.strip()
    locked.submitted_by = actor_id
    locked.submitted_at = datetime.now(timezone.utc)
    locked.reviewed_by = None
    locked.reviewed_at = None
    locked.review_note = None
    record_transition(
        session,
        locked,
        from_status=previous,
        to_status="pending_review",
        note=note.strip(),
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(locked)
    return locked


def approve_scenario(
    session: Session,
    record: ScenarioVersionRecord,
    *,
    actor_id: int,
    note: str,
) -> ScenarioVersionRecord:
    active_ids = list(
        session.scalars(
            select(ScenarioVersionRecord.id).where(ScenarioVersionRecord.status == "active")
        )
    )
    locked = {item.id: item for item in _locked_versions(session, [record.id, *active_ids])}
    target = locked.get(record.id)
    if target is None:
        raise ScenarioGovernanceError("场景版本不存在")
    if target.status != "pending_review":
        raise ScenarioGovernanceError("只有待审核版本可以审核通过")

    for current in locked.values():
        if current.id != target.id and current.status == "active":
            current.status = "archived"
            record_transition(
                session,
                current,
                from_status="active",
                to_status="archived",
                note=f"由 {target.version_key} 发布替换",
                actor_id=actor_id,
            )
    session.flush()
    target.status = "active"
    target.reviewed_by = actor_id
    target.reviewed_at = datetime.now(timezone.utc)
    target.review_note = note.strip()
    target.activated_at = datetime.now(timezone.utc)
    record_transition(
        session,
        target,
        from_status="pending_review",
        to_status="active",
        note=note.strip(),
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(target)
    return target


def reject_scenario(
    session: Session,
    record: ScenarioVersionRecord,
    *,
    actor_id: int,
    note: str,
) -> ScenarioVersionRecord:
    locked = session.scalar(
        select(ScenarioVersionRecord)
        .where(ScenarioVersionRecord.id == record.id)
        .with_for_update()
    )
    if locked is None:
        raise ScenarioGovernanceError("场景版本不存在")
    if locked.status != "pending_review":
        raise ScenarioGovernanceError("只有待审核版本可以驳回")
    locked.status = "rejected"
    locked.reviewed_by = actor_id
    locked.reviewed_at = datetime.now(timezone.utc)
    locked.review_note = note.strip()
    record_transition(
        session,
        locked,
        from_status="pending_review",
        to_status="rejected",
        note=note.strip(),
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(locked)
    return locked


def rollback_scenario(
    session: Session,
    record: ScenarioVersionRecord,
    *,
    actor_id: int,
    note: str,
) -> ScenarioVersionRecord:
    active_ids = list(
        session.scalars(
            select(ScenarioVersionRecord.id).where(ScenarioVersionRecord.status == "active")
        )
    )
    locked = {item.id: item for item in _locked_versions(session, [record.id, *active_ids])}
    target = locked.get(record.id)
    if target is None:
        raise ScenarioGovernanceError("场景版本不存在")
    if target.status != "archived":
        raise ScenarioGovernanceError("只有已归档版本可以回滚")

    for current in locked.values():
        if current.id != target.id and current.status == "active":
            current.status = "archived"
            record_transition(
                session,
                current,
                from_status="active",
                to_status="archived",
                note=f"回滚至 {target.version_key}",
                actor_id=actor_id,
            )
    session.flush()
    target.status = "active"
    target.reviewed_by = actor_id
    target.reviewed_at = datetime.now(timezone.utc)
    target.review_note = f"回滚发布：{note.strip()}"
    target.activated_at = datetime.now(timezone.utc)
    record_transition(
        session,
        target,
        from_status="archived",
        to_status="active",
        note=f"回滚发布：{note.strip()}",
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(target)
    return target


def _items(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in payload.get(key, []) if item.get("id")}


def _describe_change(before: dict[str, Any], after: dict[str, Any]) -> str:
    ignored = {"id"}
    changes = []
    for key in sorted((set(before) | set(after)) - ignored):
        if before.get(key) != after.get(key):
            changes.append(f"{key}: {before.get(key)} → {after.get(key)}")
    return "；".join(changes[:6]) or "内容已更新"


def _diff_group(base: dict[str, Any], target: dict[str, Any], key: str) -> dict[str, Any]:
    before = _items(base, key)
    after = _items(target, key)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(item_id for item_id in set(before) & set(after) if before[item_id] != after[item_id])
    details = [
        {"object_id": item_id, "change_type": "added", "description": "新增记录"}
        for item_id in added
    ]
    details += [
        {"object_id": item_id, "change_type": "removed", "description": "删除记录"}
        for item_id in removed
    ]
    details += [
        {
            "object_id": item_id,
            "change_type": "changed",
            "description": _describe_change(before[item_id], after[item_id]),
        }
        for item_id in changed
    ]
    return {
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "details": details[:100],
    }


def _metrics(payload: dict[str, Any]) -> dict[str, Any]:
    orders = payload.get("orders", [])
    vehicles = payload.get("vehicles", [])
    return {
        "node_count": len(payload.get("nodes", [])),
        "order_count": len(orders),
        "vehicle_count": len(vehicles),
        "total_weight_kg": sum(int(item.get("weight_kg", 0)) for item in orders),
        "cold_chain_capacity_kg": sum(
            int(item.get("capacity_kg", 0))
            for item in vehicles
            if item.get("cold_chain") and item.get("available", True)
        ),
    }


def compare_scenarios(
    base: ScenarioVersionRecord,
    target: ScenarioVersionRecord,
) -> dict[str, Any]:
    base_metrics = _metrics(base.payload)
    target_metrics = _metrics(target.payload)
    deltas = {key: target_metrics[key] - base_metrics[key] for key in base_metrics}
    return {
        "base": base,
        "target": target,
        "base_metrics": base_metrics,
        "target_metrics": target_metrics,
        "deltas": deltas,
        "nodes": _diff_group(base.payload, target.payload, "nodes"),
        "orders": _diff_group(base.payload, target.payload, "orders"),
        "vehicles": _diff_group(base.payload, target.payload, "vehicles"),
    }
