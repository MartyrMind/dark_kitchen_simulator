from app.events.task_events import TaskQueuedEventWriter
from conftest import KITCHEN_ID


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(document)


class FakeDatabase(dict):
    def __getitem__(self, name):
        if name not in self:
            self[name] = FakeCollection()
        return dict.__getitem__(self, name)


class FakeMongo(dict):
    def __getitem__(self, name):
        if name not in self:
            self[name] = FakeDatabase()
        return dict.__getitem__(self, name)


async def test_order_events_include_standard_fields(session):
    from app.schemas import OrderCreate
    from app.services import OrderCreationService
    from conftest import BURGER_ID, FakeKitchenClient, FakeMenuClient, FakeTaskPublisher

    mongo = FakeMongo()
    writer = TaskQueuedEventWriter(mongo, enabled=True)
    service = OrderCreationService(session, FakeKitchenClient(), FakeMenuClient(), FakeTaskPublisher(), writer)

    created = await service.create_order(OrderCreate(kitchen_id=KITCHEN_ID, items=[{"menu_item_id": BURGER_ID, "quantity": 1}]))
    events = mongo["dark_kitchen_events"]["order_events"].documents

    assert created.id
    assert {event["event_type"] for event in events} == {"OrderCreated", "KitchenTasksCreated"}
    assert all(event["service"] == "fulfillment-service" for event in events)
    assert all("created_at" in event for event in events)
    assert all("correlation_id" in event for event in events)
    assert all("payload" in event for event in events)
