#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


KITCHEN_ID = "11111111-1111-1111-1111-111111111001"
GRILL_STATION_ID = "11111111-1111-1111-1111-111111111101"
PACKAGING_STATION_ID = "11111111-1111-1111-1111-111111111103"


def request_json(method: str, base_url: str, path: str, payload: dict | None = None) -> tuple[int, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed


def ensure_success(status: int, body: object, action: str, allowed: set[int] | None = None) -> object:
    allowed = allowed or {200, 201}
    if status not in allowed:
        raise RuntimeError(f"{action} failed with HTTP {status}: {body}")
    return body


def find_by_name(items: list[dict], name: str) -> dict | None:
    return next((item for item in items if item.get("name") == name), None)


def ensure_kitchen(kitchen_url: str) -> dict:
    status, body = request_json("POST", kitchen_url, "/kitchens", {"id": KITCHEN_ID, "name": "Demo Kitchen"})
    if status in {200, 201}:
        return body
    status, kitchens = request_json("GET", kitchen_url, "/kitchens")
    ensure_success(status, kitchens, "list kitchens")
    existing = find_by_name(kitchens, "Demo Kitchen")
    if existing:
        return existing
    raise RuntimeError(f"create kitchen failed with HTTP {status}: {body}")


def ensure_station(kitchen_url: str, kitchen_id: str, station_id: str, name: str, station_type: str) -> dict:
    payload = {
        "id": station_id,
        "name": name,
        "station_type": station_type,
        "capacity": 1,
        "visible_backlog_limit": 4,
    }
    status, body = request_json("POST", kitchen_url, f"/kitchens/{kitchen_id}/stations", payload)
    if status in {200, 201}:
        return body
    status, stations = request_json("GET", kitchen_url, f"/kitchens/{kitchen_id}/stations")
    ensure_success(status, stations, "list stations")
    existing = find_by_name(stations, name)
    if existing:
        return existing
    raise RuntimeError(f"create station {name} failed with HTTP {status}: {body}")


def ensure_menu_item(menu_url: str) -> dict:
    status, items = request_json("GET", menu_url, "/menu-items?limit=500")
    ensure_success(status, items, "list menu items")
    existing = find_by_name(items, "Burger")
    if existing:
        return existing
    status, body = request_json(
        "POST",
        menu_url,
        "/menu-items",
        {"name": "Burger", "description": "Demo burger", "status": "active"},
    )
    return ensure_success(status, body, "create Burger")


def ensure_recipe_step(menu_url: str, menu_item_id: str, station_type: str, operation: str, duration: int, order: int) -> None:
    status, recipe = request_json("GET", menu_url, f"/menu-items/{menu_item_id}/recipe")
    if status == 200 and any(step.get("step_order") == order for step in recipe.get("steps", [])):
        return
    payload = {
        "station_type": station_type,
        "operation": operation,
        "duration_seconds": duration,
        "step_order": order,
    }
    status, body = request_json("POST", menu_url, f"/menu-items/{menu_item_id}/recipe-steps", payload)
    ensure_success(status, body, f"create recipe step {order}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic demo data through public APIs.")
    parser.add_argument("--kitchen-url", default=os.environ.get("KITCHEN_SERVICE_URL", "http://localhost:8001"))
    parser.add_argument("--menu-url", default=os.environ.get("MENU_SERVICE_URL", "http://localhost:8002"))
    parser.add_argument("--fulfillment-url", default=os.environ.get("FULFILLMENT_SERVICE_URL", "http://localhost:8003"))
    parser.add_argument("--state-file", default="scripts/demo/.demo_state.json")
    args = parser.parse_args()

    kitchen = ensure_kitchen(args.kitchen_url)
    kitchen_id = kitchen["id"]
    grill = ensure_station(args.kitchen_url, kitchen_id, GRILL_STATION_ID, "Demo Grill", "grill")
    packaging = ensure_station(args.kitchen_url, kitchen_id, PACKAGING_STATION_ID, "Demo Packaging", "packaging")

    burger = ensure_menu_item(args.menu_url)
    burger_id = burger["id"]
    ensure_recipe_step(args.menu_url, burger_id, "grill", "cook_patty", 480, 1)
    ensure_recipe_step(args.menu_url, burger_id, "packaging", "pack_burger", 60, 2)

    status, availability = request_json(
        "POST",
        args.menu_url,
        f"/kitchens/{kitchen_id}/menu-items/{burger_id}/availability",
        {"is_available": True},
    )
    ensure_success(status, availability, "upsert Burger availability")

    state = {
        "kitchen_id": kitchen_id,
        "stations": {"grill": grill["id"], "packaging": packaging["id"]},
        "menu_items": {"burger": burger_id},
        "simulator_workers_config": f"{grill['id']}:1,{packaging['id']}:1",
    }
    state_path = Path(args.state_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    state_path.with_suffix(".env").write_text(
        f"SIMULATOR_WORKERS_CONFIG={state['simulator_workers_config']}\n",
        encoding="utf-8",
    )

    print(f"kitchen_id={state['kitchen_id']}")
    print(f"grill_station_id={state['stations']['grill']}")
    print(f"packaging_station_id={state['stations']['packaging']}")
    print(f"burger_menu_item_id={state['menu_items']['burger']}")
    print(f"SIMULATOR_WORKERS_CONFIG={state['simulator_workers_config']}")


if __name__ == "__main__":
    main()
