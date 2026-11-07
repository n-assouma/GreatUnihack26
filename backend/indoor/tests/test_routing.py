import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from indoor import api, graph
from indoor.router import router

ENTRANCES = ["entrance_east", "entrance_south", "entrance_north"]
DEMO_ROOMS = ["THEATRE_A", "3A.041"]
TURNS = {"start", "straight", "slight_left", "slight_right", "left", "right", "turn_around",
         "lift", "stairs", "arrive"}

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_graph_edges_reference_existing_nodes():
    b = graph.building()  # raises BuildingDataError on bad references
    ids = {n["id"] for n in b["nodes"]}
    assert all(e["from"] in ids and e["to"] in ids for e in b["edges"])
    assert {"entrance_east", "entrance_south", "entrance_north", "THEATRE_A", "3A.041"} <= ids


@pytest.mark.parametrize("accessible", [True, False])
@pytest.mark.parametrize("room", DEMO_ROOMS)
@pytest.mark.parametrize("entrance", ENTRANCES)
def test_demo_rooms_reachable_from_every_entrance(entrance, room, accessible):
    r = api.get_indoor_route(entrance, room, accessible)
    assert r["steps"][-1]["turn"] == "arrive"
    assert r["steps"][-1]["to_node"] == room


def test_accessible_route_has_no_stairs_and_uses_lift():
    r = api.get_indoor_route("entrance_east", "THEATRE_A", accessible=True)
    assert all(s["via"] != "stairs" and s["turn"] != "stairs" for s in r["steps"])
    assert any(s["via"] == "lift" for s in r["steps"])
    assert {seg["floor"] for seg in r["segments"]} == {0, 1}


def test_route_matches_contract_shape():
    r = api.get_indoor_route("entrance_east", "THEATRE_A", accessible=True)
    assert set(r) == {"start_node", "destination_id", "accessible", "total_distance_m", "steps", "segments"}
    for i, s in enumerate(r["steps"]):
        assert s["index"] == i and s["turn"] in TURNS
        assert isinstance(s["instruction"], str) and s["instruction"]
        assert set(s) == {"index", "instruction", "floor", "from_node", "to_node", "distance_m",
                          "bearing_deg", "turn", "via", "target_floor"}
        if s["turn"] in ("lift", "stairs"):
            assert s["bearing_deg"] is None and s["target_floor"] is not None
    for seg in r["segments"]:
        assert seg["image_url"].startswith("/static/floorplans/floor_")
        assert all(len(p) == 2 for p in seg["points"]) and seg["step_indices"]
    assert sorted(i for seg in r["segments"] for i in seg["step_indices"]) == list(range(len(r["steps"])))


def test_first_turn_uses_entrance_facing_without_compass():
    r = api.get_indoor_route("entrance_east", "THEATRE_A", accessible=True)
    assert r["steps"][0]["turn"] != "start"  # facing_deg of the entrance gives a real turn
    r2 = api.get_indoor_route("f0_top_core1", "THEATRE_A", accessible=True)
    assert r2["steps"][0]["turn"] == "start"  # no facing known -> landmark-only wording


def test_heading_overrides_entrance_facing():
    a = api.get_indoor_route("entrance_east", "THEATRE_A", True)
    b = api.get_indoor_route("entrance_east", "THEATRE_A", True, heading=(a["steps"][0]["bearing_deg"] + 180) % 360)
    assert b["steps"][0]["turn"] == "turn_around"


def test_unknown_node_and_no_route():
    with pytest.raises(api.UnknownNodeError):
        api.get_indoor_route("nope", "THEATRE_A", True)
    with pytest.raises(api.UnknownNodeError):
        api.get_indoor_route("entrance_east", "nope", True)


@pytest.mark.parametrize("text,expected", [
    ("I'm at the east entrance", "entrance_east"),
    ("east entrance", "entrance_east"),
    ("at the main door", "entrance_east"),
    ("I'm at the north entrance", "entrance_north"),
    ("south entrance please", "entrance_south"),
    ("near the Core 3 lifts", "f0_core3_lift"),
    ("core 3 lifts on the first floor", "f1_core3_lift"),
])
def test_locate(text, expected):
    assert api.locate(text)["node_id"] == expected


def test_locate_unclear_gives_options():
    r = api.locate("by the lifts")
    assert r["node_id"] is None and 1 <= len(r["candidates"]) <= 3
    assert api.locate("")["node_id"] is None
    assert api.locate("banana submarine")["node_id"] is None


def test_heading_towards():
    h = api.heading_towards("entrance_east", "I'm facing the lifts")
    assert h is not None and 0 <= h < 360
    assert api.heading_towards("entrance_east", "I'm facing the moon") is None
    with pytest.raises(api.UnknownNodeError):
        api.heading_towards("nope", "lifts")


def test_rooms_and_nodes_exist():
    assert api.room_exists("THEATRE_A") and api.room_exists("3A.041") and not api.room_exists("9Z.999")
    assert api.node_exists("entrance_east") and not api.node_exists("zzz")


def test_http_endpoints():
    b = client.get("/api/indoor/building").json()
    assert b["building_id"] == "nancy_rothwell" and len(b["floors"]) == 4
    assert {e["id"] for e in b["entrances"]} == set(ENTRANCES)
    ok = client.post("/api/indoor/route", json={"start": "entrance_east", "destination": "THEATRE_A",
                                                "accessible": True})
    assert ok.status_code == 200
    assert client.post("/api/indoor/route", json={"start": "nope", "destination": "THEATRE_A",
                                                  "accessible": True}).status_code == 404
    assert client.post("/api/indoor/locate", json={"text": "east entrance"}).json()["node_id"] == "entrance_east"
