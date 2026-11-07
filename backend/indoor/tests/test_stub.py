import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from indoor import api
from indoor.router import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_route_shape():
    r = client.post("/api/indoor/route",
                    json={"start": "entrance_east", "destination": "THEATRE_A", "accessible": True})
    assert r.status_code == 200
    body = r.json()
    assert body["steps"][-1]["turn"] == "arrive"
    assert all(s["via"] != "stairs" for s in body["steps"])
    assert {s["floor"] for s in body["segments"]} == {0, 1}


def test_unknown_node_404():
    r = client.post("/api/indoor/route",
                    json={"start": "nope", "destination": "THEATRE_A", "accessible": True})
    assert r.status_code == 404


def test_building_and_locate():
    assert client.get("/api/indoor/building").json()["building_id"] == "nancy_rothwell"
    r = client.post("/api/indoor/locate", json={"text": "I'm at the east entrance"})
    assert r.json()["node_id"] == "entrance_east"


def test_python_api():
    assert api.room_exists("THEATRE_A") and not api.room_exists("X")
    with pytest.raises(api.UnknownNodeError):
        api.get_indoor_route("nope", "THEATRE_A", True)
