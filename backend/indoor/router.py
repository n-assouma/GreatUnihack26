"""FastAPI router for indoor endpoints (CONTRACTS section 3)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import api

router = APIRouter(prefix="/api/indoor")


class RouteRequest(BaseModel):
    start: str
    destination: str
    accessible: bool = False
    heading: float | None = None


class LocateRequest(BaseModel):
    text: str


@router.get("/building")
def building() -> dict:
    return api.get_building_summary()


@router.post("/route")
def route(req: RouteRequest) -> dict:
    try:
        return api.get_indoor_route(req.start, req.destination, req.accessible, req.heading)
    except api.UnknownNodeError as e:
        raise HTTPException(status_code=404, detail=f"unknown node: {e}")
    except api.NoRouteError as e:
        raise HTTPException(status_code=404, detail=f"no route: {e}")


@router.post("/locate")
def locate(req: LocateRequest) -> dict:
    return api.locate(req.text)
