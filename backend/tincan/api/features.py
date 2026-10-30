from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sqlalchemy import select

from tincan.api.deps import ApiError, runtime
from tincan.models import Contact, Feature
from tincan.schemas import FeatureIn, FeatureOut, PreviewOut

router = APIRouter(prefix="/api/features", tags=["features"])


def all_features(rt) -> list[FeatureOut]:
    with rt.db.session() as s:
        by_digit = {c.speed_dial: c for c in s.scalars(select(Contact)) if c.speed_dial is not None}
        rows = {f.digit: f for f in s.scalars(select(Feature))}
    out = []
    for d in range(10):
        if d in by_digit:
            c = by_digit[d]
            out.append(
                FeatureOut(
                    digit=d,
                    kind="speed_dial",
                    config={"contact_id": c.id, "name": c.name},
                    enabled=bool(c.enabled),
                )
            )
        elif d in rows:
            out.append(FeatureOut.from_row(rows[d]))
        else:
            out.append(FeatureOut(digit=d, kind="none", config={}, enabled=True))
    return out


@router.get("")
async def list_features(request: Request) -> list[FeatureOut]:
    return all_features(runtime(request))


@router.put("/{digit}")
async def put_feature(digit: int, body: FeatureIn, request: Request) -> FeatureOut:
    rt = runtime(request)
    if not 0 <= digit <= 9:
        raise ApiError(404, "not_found", "Digits are 0-9")
    with rt.db.session() as s:
        taken = s.scalar(select(Contact).where(Contact.speed_dial == digit))
        if taken is not None:
            raise ApiError(
                409, "speed_dial_taken", f"Digit {digit} is the speed dial for {taken.name}"
            )
        f = s.get(Feature, digit)
        if f is None:
            f = Feature(digit=digit)
            s.add(f)
        f.kind = body.kind
        f.config = json.dumps(body.config)
        f.enabled = body.enabled
        s.flush()
        return FeatureOut.from_row(f)


@router.post("/{digit}/preview")
async def preview(digit: int, request: Request) -> PreviewOut:
    rt = runtime(request)
    feature_out = next((f for f in all_features(rt) if f.digit == digit), None)
    if feature_out is None:
        raise ApiError(404, "not_found", "Digits are 0-9")
    if feature_out.kind == "speed_dial":
        from tincan.tts import prompts

        text = prompts.CALLING.format(name=feature_out.config.get("name", ""))
    else:
        feature = rt.features.get(feature_out.kind)
        if feature is None:
            raise ApiError(400, "unknown_feature", f"No feature of kind {feature_out.kind}")
        text = await feature.text(rt, feature_out.config)
    path = await rt.tts.render(text)
    return PreviewOut(text=text, audio_url=f"/api/audio/prompts/{path.name}")
