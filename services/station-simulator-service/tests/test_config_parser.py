import pytest

from app.simulator.config_parser import parse_workers_config


def test_parse_single_station_workers():
    workers = parse_workers_config("grill_1:2")

    assert [worker.worker_id for worker in workers] == ["grill_1-worker-1", "grill_1-worker-2"]
    assert [worker.station_id for worker in workers] == ["grill_1", "grill_1"]


def test_parse_multiple_stations():
    workers = parse_workers_config("grill_1:2,fryer_1:1,packaging_1:1")

    assert [worker.worker_id for worker in workers] == [
        "grill_1-worker-1",
        "grill_1-worker-2",
        "fryer_1-worker-1",
        "packaging_1-worker-1",
    ]


@pytest.mark.parametrize("config", ["", " ", "grill_1", ":1", "grill_1:0", "grill_1:-1", "grill_1:abc"])
def test_invalid_config_raises(config):
    with pytest.raises(ValueError):
        parse_workers_config(config)


def test_duplicate_station_id_raises():
    with pytest.raises(ValueError):
        parse_workers_config("grill_1:1,grill_1:2")
