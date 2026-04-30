async def test_create_and_get_kitchen(client):
    create_response = await client.post("/kitchens", json={"name": "Main kitchen"})

    assert create_response.status_code == 201
    kitchen = create_response.json()
    assert kitchen["name"] == "Main kitchen"
    assert kitchen["status"] == "active"

    list_response = await client.get("/kitchens")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == kitchen["id"]

    get_response = await client.get(f"/kitchens/{kitchen['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Main kitchen"


async def test_unknown_kitchen_returns_404(client):
    response = await client.get("/kitchens/404")

    assert response.status_code == 404
    assert response.json()["detail"] == "kitchen_not_found"
