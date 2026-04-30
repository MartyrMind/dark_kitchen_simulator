from app.events import MongoKdsEventWriter


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


async def test_station_event_includes_standard_fields(monkeypatch):
    writer = MongoKdsEventWriter()
    writer._client = FakeMongo()

    await writer.write_station_event(
        "StationCreated",
        kitchen_id=1,
        station_id=2,
        station_type="grill",
        correlation_id="corr-1",
        payload={"capacity": 2},
    )

    event = writer._client["dark_kitchen_events"]["station_events"].documents[0]
    assert event["event_type"] == "StationCreated"
    assert event["service"] == "kitchen-service"
    assert event["correlation_id"] == "corr-1"
    assert event["station_type"] == "grill"
    assert "created_at" in event
    assert event["payload"] == {"capacity": 2}
