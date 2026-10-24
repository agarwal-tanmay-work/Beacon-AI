"""Small conveniences shared by the API tests."""

from dataclasses import dataclass
from typing import Any

import httpx

from tests.fake_ai import FakeAI, turn

API = "/api/v1"


def same_pixels(a: bytes, b: bytes) -> bool:
    """Uploaded images are re-encoded to strip metadata: compare what they *show*, not their bytes."""
    import io

    from PIL import Image

    with Image.open(io.BytesIO(a)) as first, Image.open(io.BytesIO(b)) as second:
        return first.size == second.size and first.convert("RGB").tobytes() == second.convert("RGB").tobytes()


ADMIN_PASSWORD = "correct horse battery staple"


async def admin_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(f"{API}/admin/auth/login", json={"username": "beaconai", "password": ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@dataclass
class Session:
    report_id: str
    token: str

    def body(self, **extra: Any) -> dict[str, Any]:
        return {"report_id": self.report_id, "access_token": self.token, **extra}


async def new_session(client: httpx.AsyncClient) -> Session:
    response = await client.post(f"{API}/public/reports/create", json={})
    assert response.status_code == 200, response.text
    data = response.json()
    return Session(data["report_id"], data["access_token"])


async def say(client: httpx.AsyncClient, session: Session, text: str) -> httpx.Response:
    return await client.post(f"{API}/public/reports/message", json=session.body(content=text))


async def upload(client: httpx.AsyncClient, session: Session, data: bytes, name: str = "photo.png") -> httpx.Response:
    return await client.post(
        f"{API}/public/evidence/upload",
        data={"report_id": session.report_id, "access_token": session.token},
        files={"file": (name, data, "application/octet-stream")},
    )


def script_full_intake(fake: FakeAI) -> list[str]:
    """Queue the model's side of a complete, successful intake and return the user's messages to send."""
    what, where, when, who = "Officer demanded 500 rupees bribe", "Border checkpost, Amritsar", "Yesterday at 3 PM", "Officer Raj"
    fake.chat_script[:] = [
        turn("I'm so sorry that happened. Where did this take place?", asked="where", what=what),
        turn("Thank you. When did it happen?", asked="when", what=what, where=where),
        turn("Understood. Who was involved?", asked="who", what=what, where=where, when=when),
        turn("Thank you. Do you have any evidence?", asked="evidence", what=what, where=where, when=when, who=who),
        turn(
            "Would you like to provide contact details? This is completely optional.",
            asked="contact_info",
            what=what,
            where=where,
            when=when,
            who=who,
            evidence="SKIPPED",
        ),
        turn(
            "Would you like to add any more details?",
            asked="other_details",
            what=what,
            where=where,
            when=when,
            who=who,
            evidence="SKIPPED",
            contact_info="SKIPPED",
        ),
        turn(
            "Thank you for speaking up.",
            ready=True,
            what=what,
            where=where,
            when=when,
            who=who,
            evidence="SKIPPED",
            contact_info="SKIPPED",
            other_details="SKIPPED",
        ),
    ]
    return [
        "An officer demanded 500 rupees",
        "At the border checkpost in Amritsar",
        "Yesterday at 3 PM",
        "Officer Raj",
        "no",
        "no",
        "no, that's all",
    ]


async def run_full_intake(client: httpx.AsyncClient, fake: FakeAI, session: Session) -> dict[str, Any]:
    """Drive the whole conversation; returns the final (submission) response."""
    last: dict[str, Any] = {}
    for message in script_full_intake(fake):
        response = await say(client, session, message)
        assert response.status_code == 200, response.text
        last = response.json()
    return last
