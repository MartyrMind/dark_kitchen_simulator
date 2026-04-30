from uuid import uuid4


async def test_create_and_get_menu_item(client):
    create_response = await client.post(
        "/menu-items",
        json={"name": "Burger", "description": "Classic beef burger", "status": "active"},
    )

    assert create_response.status_code == 201
    item = create_response.json()
    assert item["name"] == "Burger"

    list_response = await client.get("/menu-items")
    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()] == [item["id"]]

    get_response = await client.get(f"/menu-items/{item['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == item["id"]


async def test_duplicate_menu_item_name_returns_409(client):
    payload = {"name": "Burger", "status": "active"}
    first_response = await client.post("/menu-items", json=payload)
    second_response = await client.post("/menu-items", json={**payload, "name": "burger"})

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["error"] == "menu_item_already_exists"


async def test_unknown_menu_item_returns_404(client):
    response = await client.get(f"/menu-items/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"] == "menu_item_not_found"
