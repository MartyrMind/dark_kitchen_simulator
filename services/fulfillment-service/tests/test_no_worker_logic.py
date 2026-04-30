from pathlib import Path


def test_no_worker_consumer_or_kds_logic():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    text = "\n".join(path.read_text(encoding="utf-8") for path in app_dir.rglob("*.py"))

    forbidden = ["xreadgroup", "xack", "xgroup_create", "/kds/", "dispatch_candidates", "select_station"]
    lowered = text.lower()
    for marker in forbidden:
        assert marker not in lowered
