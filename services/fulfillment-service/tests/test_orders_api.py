from uuid import uuid4


async def test_post_order_and_get_order_and_tasks(client, order_payload):
    create_response = await client.post("/orders", json=order_payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "created"
    assert created["tasks_count"] == 4

    order_response = await client.get(f"/orders/{created['id']}")
    assert order_response.status_code == 200
    assert order_response.json()["id"] == created["id"]
    assert len(order_response.json()["items"]) == 1

    tasks_response = await client.get(f"/orders/{created['id']}/tasks")
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert len(tasks) == 4
    assert {task["status"] for task in tasks} == {"created"}
    assert "queued" not in {task["status"] for task in tasks}
    assert [task["recipe_step_order"] for task in tasks] == [1, 2, 1, 2]
    assert len([task for task in tasks if task["depends_on_task_ids"]]) == 2


async def test_unknown_order_returns_404(client):
    response = await client.get(f"/orders/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"] == "order_not_found"


async def test_post_order_does_not_require_redis(client, order_payload):
    response = await client.post("/orders", json=order_payload)

    assert response.status_code == 201
    assert response.json()["tasks_count"] == 4
