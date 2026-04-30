async def _create_kitchen(client) -> int:
    response = await client.post("/kitchens", json={"name": "Main kitchen"})
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_and_list_stations(client):
    kitchen_id = await _create_kitchen(client)

    create_response = await client.post(
        f"/kitchens/{kitchen_id}/stations",
        json={
            "name": "Grill 1",
            "station_type": "grill",
            "capacity": 3,
            "visible_backlog_limit": 8,
        },
    )

    assert create_response.status_code == 201
    station = create_response.json()
    assert station["busy_slots"] == 0
    assert station["capacity"] == 3
    assert station["visible_backlog_limit"] == 8

    list_response = await client.get(f"/kitchens/{kitchen_id}/stations")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    filtered_response = await client.get(f"/kitchens/{kitchen_id}/stations?station_type=grill")
    assert filtered_response.status_code == 200
    assert filtered_response.json()[0]["station_type"] == "grill"

    empty_response = await client.get(f"/kitchens/{kitchen_id}/stations?station_type=fryer")
    assert empty_response.status_code == 200
    assert empty_response.json() == []


async def test_update_station_capacity_and_status(client):
    kitchen_id = await _create_kitchen(client)
    station_response = await client.post(
        f"/kitchens/{kitchen_id}/stations",
        json={
            "name": "Assembly 1",
            "station_type": "assembly",
            "capacity": 2,
            "visible_backlog_limit": 6,
        },
    )
    station_id = station_response.json()["id"]

    capacity_response = await client.patch(f"/stations/{station_id}/capacity", json={"capacity": 5})
    assert capacity_response.status_code == 200
    assert capacity_response.json()["capacity"] == 5

    status_response = await client.patch(f"/stations/{station_id}/status", json={"status": "maintenance"})
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "maintenance"
