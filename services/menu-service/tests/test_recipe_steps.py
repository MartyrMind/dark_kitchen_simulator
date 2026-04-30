async def _create_menu_item(client) -> str:
    response = await client.post("/menu-items", json={"name": "Burger", "status": "active"})
    assert response.status_code == 201
    return response.json()["id"]


async def test_recipe_steps_are_returned_ordered(client):
    menu_item_id = await _create_menu_item(client)

    second = await client.post(
        f"/menu-items/{menu_item_id}/recipe-steps",
        json={
            "station_type": "packaging",
            "operation": "pack_burger",
            "duration_seconds": 60,
            "step_order": 2,
        },
    )
    first = await client.post(
        f"/menu-items/{menu_item_id}/recipe-steps",
        json={
            "station_type": "grill",
            "operation": "cook_patty",
            "duration_seconds": 480,
            "step_order": 1,
        },
    )
    recipe = await client.get(f"/menu-items/{menu_item_id}/recipe")

    assert second.status_code == 201
    assert first.status_code == 201
    assert recipe.status_code == 200
    assert [step["step_order"] for step in recipe.json()["steps"]] == [1, 2]


async def test_duplicate_recipe_step_order_returns_409(client):
    menu_item_id = await _create_menu_item(client)
    payload = {
        "station_type": "grill",
        "operation": "cook_patty",
        "duration_seconds": 480,
        "step_order": 1,
    }

    first = await client.post(f"/menu-items/{menu_item_id}/recipe-steps", json=payload)
    second = await client.post(f"/menu-items/{menu_item_id}/recipe-steps", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"] == "recipe_step_order_already_exists"


async def test_recipe_step_validation(client):
    menu_item_id = await _create_menu_item(client)
    base_payload = {
        "station_type": "grill",
        "operation": "cook_patty",
        "duration_seconds": 480,
        "step_order": 1,
    }

    invalid_duration = await client.post(
        f"/menu-items/{menu_item_id}/recipe-steps",
        json={**base_payload, "duration_seconds": 0},
    )
    invalid_order = await client.post(
        f"/menu-items/{menu_item_id}/recipe-steps",
        json={**base_payload, "step_order": 0},
    )
    invalid_station = await client.post(
        f"/menu-items/{menu_item_id}/recipe-steps",
        json={**base_payload, "station_type": "cold"},
    )

    assert invalid_duration.status_code == 422
    assert invalid_order.status_code == 422
    assert invalid_station.status_code == 422
