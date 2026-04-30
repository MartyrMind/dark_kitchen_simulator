async def test_station_capacity_must_be_positive(client):
    kitchen = await client.post("/kitchens", json={"name": "Main kitchen"})

    response = await client.post(
        f"/kitchens/{kitchen.json()['id']}/stations",
        json={
            "name": "Bad station",
            "station_type": "grill",
            "capacity": 0,
            "visible_backlog_limit": 2,
        },
    )

    assert response.status_code == 422


async def test_visible_backlog_limit_must_be_positive(client):
    kitchen = await client.post("/kitchens", json={"name": "Main kitchen"})

    response = await client.post(
        f"/kitchens/{kitchen.json()['id']}/stations",
        json={
            "name": "Bad station",
            "station_type": "grill",
            "capacity": 1,
            "visible_backlog_limit": 0,
        },
    )

    assert response.status_code == 422


async def test_unknown_station_type_is_rejected(client):
    kitchen = await client.post("/kitchens", json={"name": "Main kitchen"})

    response = await client.post(
        f"/kitchens/{kitchen.json()['id']}/stations",
        json={
            "name": "Unknown station",
            "station_type": "oven",
            "capacity": 1,
            "visible_backlog_limit": 2,
        },
    )

    assert response.status_code == 422


async def test_unknown_station_status_is_rejected(client):
    kitchen = await client.post("/kitchens", json={"name": "Main kitchen"})
    station = await client.post(
        f"/kitchens/{kitchen.json()['id']}/stations",
        json={
            "name": "Grill",
            "station_type": "grill",
            "capacity": 1,
            "visible_backlog_limit": 2,
        },
    )

    response = await client.patch(f"/stations/{station.json()['id']}/status", json={"status": "busy"})

    assert response.status_code == 422


async def test_cannot_create_station_for_unknown_kitchen(client):
    response = await client.post(
        "/kitchens/404/stations",
        json={
            "name": "Ghost station",
            "station_type": "grill",
            "capacity": 1,
            "visible_backlog_limit": 2,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "kitchen_not_found"
