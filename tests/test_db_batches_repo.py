from content_engine.db.connection import init_db
from content_engine.db import batches_repo


def _fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def test_insert_and_get_batch(tmp_path):
    db_path = _fresh_db(tmp_path)
    batches_repo.insert_batch(db_path, "batch1", "stoicism", ["youtube", "tiktok"], 2, 3, 180)

    batch = batches_repo.get_batch(db_path, "batch1")
    assert batch["topic"] == "stoicism"
    assert batch["target_platforms"] == "youtube,tiktok"
    assert batch["videos_count"] == 2
    assert batch["clips_per_video"] == 3
    assert batch["status"] == "running"


def test_mark_batch_finished(tmp_path):
    db_path = _fresh_db(tmp_path)
    batches_repo.insert_batch(db_path, "batch1", "stoicism", ["youtube"], 2, 2, 60)

    batches_repo.mark_batch_finished(db_path, "batch1", "succeeded")

    batch = batches_repo.get_batch(db_path, "batch1")
    assert batch["status"] == "succeeded"
    assert batch["finished_at"] is not None


def test_mark_batch_finished_with_error(tmp_path):
    db_path = _fresh_db(tmp_path)
    batches_repo.insert_batch(db_path, "batch1", "stoicism", ["youtube"], 2, 2, 60)

    batches_repo.mark_batch_finished(db_path, "batch1", "failed", error_message="search failed")

    batch = batches_repo.get_batch(db_path, "batch1")
    assert batch["status"] == "failed"
    assert batch["error_message"] == "search failed"


def test_list_recent_batches_orders_newest_first(tmp_path):
    db_path = _fresh_db(tmp_path)
    batches_repo.insert_batch(db_path, "batch1", "topic1", ["youtube"], 1, 1, 60)
    batches_repo.insert_batch(db_path, "batch2", "topic2", ["youtube"], 1, 1, 60)

    recent = batches_repo.list_recent_batches(db_path)
    assert [b["batch_id"] for b in recent] == ["batch2", "batch1"]
