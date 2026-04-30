#!/usr/bin/env python3
import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(method: str, base_url: str, path: str, payload: dict | None = None, timeout: int = 10) -> tuple[int, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed


def wait_url(url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def print_json(label: str, value: object) -> None:
    print(label)
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a demo order and wait for ready_for_pickup.")
    parser.add_argument("--fulfillment-url", default="http://localhost:8003")
    parser.add_argument("--kitchen-url", default="http://localhost:8001")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--grafana-url", default="http://localhost:3000")
    parser.add_argument("--state-file", default="scripts/demo/.demo_state.json")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    state = json.loads(Path(args.state_file).read_text(encoding="utf-8"))
    deadline = (datetime.now(UTC) + timedelta(hours=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "kitchen_id": state["kitchen_id"],
        "pickup_deadline": deadline,
        "items": [{"menu_item_id": state["menu_items"]["burger"], "quantity": 1}],
    }
    status, order = request_json("POST", args.fulfillment_url, "/orders", payload)
    if status != 201:
        raise RuntimeError(f"order creation failed with HTTP {status}: {order}")
    order_id = order["id"]
    print(f"order_id={order_id}")

    deadline_at = time.monotonic() + args.timeout
    last_order: object = order
    last_tasks: object = []
    observed_displayed = False
    observed_progress_or_done = False

    while time.monotonic() < deadline_at:
        _, last_order = request_json("GET", args.fulfillment_url, f"/orders/{order_id}")
        _, last_tasks = request_json("GET", args.fulfillment_url, f"/orders/{order_id}/tasks")
        if isinstance(last_tasks, list):
            statuses = {task.get("status") for task in last_tasks}
            observed_displayed = observed_displayed or "displayed" in statuses or "in_progress" in statuses or "done" in statuses
            observed_progress_or_done = observed_progress_or_done or "in_progress" in statuses or "done" in statuses
        if isinstance(last_order, dict) and last_order.get("status") == "ready_for_pickup":
            wait_url(args.prometheus_url.rstrip("/") + "/-/ready", 10)
            wait_url(args.grafana_url.rstrip("/") + "/api/health", 10)
            if not observed_displayed or not observed_progress_or_done:
                raise RuntimeError("order completed, but smoke checks did not observe displayed/in_progress states")
            print("Demo succeeded.")
            print(f"order_status={last_order['status']}")
            print(f"grill_station_id={state['stations']['grill']}")
            print(f"packaging_station_id={state['stations']['packaging']}")
            return
        time.sleep(args.poll_interval)

    print_json("last_order", last_order)
    print_json("last_tasks", last_tasks)
    for station_type, station_id in state["stations"].items():
        _, tasks = request_json("GET", args.kitchen_url, f"/kds/stations/{station_id}/tasks?status=displayed")
        print_json(f"kds_{station_type}_displayed_tasks", tasks)
    raise RuntimeError(f"order {order_id} did not reach ready_for_pickup within {args.timeout}s")


if __name__ == "__main__":
    main()
