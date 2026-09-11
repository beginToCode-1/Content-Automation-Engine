from unittest.mock import MagicMock

from content_engine.search.youtube_search import search_videos


def _mock_client(search_items, video_items):
    client = MagicMock()
    client.search.return_value.list.return_value.execute.return_value = {"items": search_items}
    client.videos.return_value.list.return_value.execute.return_value = {"items": video_items}
    return client


def test_search_videos_skips_items_missing_video_id():
    search_items = [
        {"id": {"videoId": "abc123"}},
        {"id": {}},  # malformed - no videoId, must not crash
        {"id": {"videoId": "def456"}},
    ]
    video_items = [
        {
            "id": "abc123",
            "snippet": {"title": "A", "description": "", "channelTitle": "c", "publishedAt": ""},
            "contentDetails": {"duration": "PT2M"},
            "statistics": {},
        },
        {
            "id": "def456",
            "snippet": {"title": "B", "description": "", "channelTitle": "c", "publishedAt": ""},
            "contentDetails": {"duration": "PT3M"},
            "statistics": {},
        },
    ]
    client = _mock_client(search_items, video_items)

    candidates = search_videos("test topic", client=client)

    assert {c.video_id for c in candidates} == {"abc123", "def456"}

    videos_list_call = client.videos.return_value.list
    called_ids = videos_list_call.call_args.kwargs["id"]
    assert called_ids == "abc123,def456"
