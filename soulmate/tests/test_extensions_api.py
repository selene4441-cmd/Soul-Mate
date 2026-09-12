from __future__ import annotations

from fastapi.testclient import TestClient


def test_extensions_list_and_call_example_plugin(client: TestClient) -> None:
    skills = client.get("/extensions/skills")
    assert skills.status_code == 200
    assert any(s["skill_id"] == "example" for s in skills.json())

    resp = client.get("/extensions/plugins")
    assert resp.status_code == 200
    plugins = resp.json()
    assert any(p["plugin_id"] == "example_echo" for p in plugins)

    resp2 = client.post(
        "/extensions/plugins/example_echo/tools/add",
        json={"args": {"a": 2, "b": 3}},
    )
    assert resp2.status_code == 200
    assert resp2.json()["result"] == {"sum": 5.0}

    snippet = client.get("/extensions/skills/example/content?offset=0&limit=200")
    assert snippet.status_code == 200
    assert "content" in snippet.json()
