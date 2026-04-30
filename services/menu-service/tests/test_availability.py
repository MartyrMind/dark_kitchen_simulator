from uuid import uuid4


async def _create_menu_item(client, name: str = "Burger", status: str = "active") -> str:
    response = await client.post("/menu-items", json={"name": name, "status": status})
    assert response.status_code == 201
    return response.json()["id"]


async def test_availability_upsert_and_kitchen_menu(client):
    kitchen_id = str(uuid4())
    menu_item_id = await _create_menu_item(client)

    created = await client.post(
        f"/kitchens/{kitchen_id}/menu-items/{menu_item_id}/availability",
        json={"is_available": True},
    )
    updated = await client.post(
        f"/kitchens/{kitchen_id}/menu-items/{menu_item_id}/availability",
        json={"is_available": False},
    )
    unavailable_menu = await client.get(f"/kitchens/{kitchen_id}/menu")
    diagnostic_menu = await client.get(f"/kitchens/{kitchen_id}/menu?include_unavailable=true")

    assert created.status_code == 200
    assert created.json()["is_available"] is True
    assert updated.status_code == 200
    assert updated.json()["is_available"] is False
    assert unavailable_menu.status_code == 200
    assert unavailable_menu.json() == []
    assert diagnostic_menu.status_code == 200
    assert len(diagnostic_menu.json()) == 1
    assert diagnostic_menu.json()[0]["is_available"] is False


async def test_kitchen_menu_returns_only_available_active_items(client):
    kitchen_id = str(uuid4())
    available_item_id = await _create_menu_item(client, "Burger")
    unavailable_item_id = await _create_menu_item(client, "Fries")
    disabled_item_id = await _create_menu_item(client, "Old shake", "disabled")

    await client.post(
        f"/kitchens/{kitchen_id}/menu-items/{available_item_id}/availability",
        json={"is_available": True},
    )
    await client.post(
        f"/kitchens/{kitchen_id}/menu-items/{unavailable_item_id}/availability",
        json={"is_available": False},
    )
    await client.post(
        f"/kitchens/{kitchen_id}/menu-items/{disabled_item_id}/availability",
        json={"is_available": True},
    )

    response = await client.get(f"/kitchens/{kitchen_id}/menu")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [available_item_id]


async def test_availability_for_unknown_menu_item_returns_404(client):
    response = await client.post(
        f"/kitchens/{uuid4()}/menu-items/{uuid4()}/availability",
        json={"is_available": True},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "menu_item_not_found"
