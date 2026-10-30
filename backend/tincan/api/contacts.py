from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tincan import store
from tincan.api.deps import ApiError, runtime
from tincan.models import Contact, dt_to_str, utcnow
from tincan.schemas import ContactIn, ContactOut, ContactPatch, DndIn

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _get(rt, contact_id: int, s) -> Contact:
    c = s.get(Contact, contact_id)
    if c is None:
        raise ApiError(404, "not_found", f"No contact {contact_id}")
    return c


def _speed_dial_free(s, digit: int | None, exclude: int | None = None) -> None:
    if digit is None:
        return
    other = s.scalar(select(Contact).where(Contact.speed_dial == digit))
    if other is not None and other.id != exclude:
        raise ApiError(
            409, "speed_dial_taken", f"Speed dial {digit} is already used by {other.name}"
        )


@router.get("")
async def list_contacts(request: Request) -> list[ContactOut]:
    with runtime(request).db.session() as s:
        return [
            ContactOut.from_row(c)
            for c in s.scalars(select(Contact).order_by(Contact.speed_dial, Contact.id))
        ]


@router.post("", status_code=201)
async def create_contact(body: ContactIn, request: Request) -> ContactOut:
    rt = runtime(request)
    with rt.db.session() as s:
        _speed_dial_free(s, body.speed_dial)
        c = Contact(
            name=body.name,
            spoken_name=body.spoken_name or body.name,
            number=body.number,
            speed_dial=body.speed_dial,
            enabled=body.enabled,
            inbound_allowed=body.inbound_allowed,
            dnd_until=dt_to_str(body.dnd_until),
            max_call_minutes=body.max_call_minutes,
        )
        s.add(c)
        try:
            s.flush()
        except IntegrityError as exc:
            raise ApiError(409, "speed_dial_taken", "Speed dial already used") from exc
        return ContactOut.from_row(c)


@router.patch("/{contact_id}")
async def patch_contact(contact_id: int, body: ContactPatch, request: Request) -> ContactOut:
    rt = runtime(request)
    fields = body.model_dump(exclude_unset=True)
    with rt.db.session() as s:
        c = _get(rt, contact_id, s)
        if "speed_dial" in fields:
            _speed_dial_free(s, fields["speed_dial"], exclude=c.id)
        if "dnd_until" in fields:
            fields["dnd_until"] = dt_to_str(fields["dnd_until"])
        for k, v in fields.items():
            setattr(c, k, v)
        s.flush()
        return ContactOut.from_row(c)


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(contact_id: int, request: Request) -> Response:
    rt = runtime(request)
    with rt.db.session() as s:
        c = _get(rt, contact_id, s)
        s.delete(c)
    return Response(status_code=204)


@router.post("/{contact_id}/dnd")
async def set_dnd(contact_id: int, body: DndIn, request: Request) -> ContactOut:
    rt = runtime(request)
    with rt.db.session() as s:
        c = _get(rt, contact_id, s)
        if body.clear:
            c.dnd_until = None
        elif body.until is not None:
            c.dnd_until = dt_to_str(body.until)
        elif body.minutes is not None:
            c.dnd_until = store.dnd_for(body.minutes, utcnow())
        else:
            raise ApiError(400, "bad_request", "Pass minutes, until, or clear")
        s.flush()
        return ContactOut.from_row(c)
