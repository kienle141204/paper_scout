from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from agent.tools.notion_client import NotionConfigError, NotionPaperClient
from agent.tools import notion_oauth


def _install_fake_notion_sdk(monkeypatch, *, query_results=None, properties=None):
    query_results = list(query_results or [])
    properties = properties or {
        "Title": {"type": "title"},
        "PaperScout Key": {"type": "rich_text"},
    }

    class FakeDatabases:
        def __init__(self, root):
            self.root = root
            self.retrieves = []
            self.queries = []

        def retrieve(self, **kwargs):
            self.retrieves.append(kwargs)
            return {"properties": properties}

        def query(self, **kwargs):
            self.queries.append(kwargs)
            return {"results": query_results}

    class FakePages:
        def __init__(self):
            self.created = []

        def create(self, **kwargs):
            self.created.append(kwargs)
            return {"id": "created-page"}

    class FakeChildren:
        def __init__(self):
            self.appended = []

        def append(self, **kwargs):
            self.appended.append(kwargs)
            return {"results": []}

    class FakeBlocks:
        def __init__(self):
            self.children = FakeChildren()

    class FakeClient:
        instances = []

        def __init__(self, auth):
            self.auth = auth
            self.databases = FakeDatabases(self)
            self.pages = FakePages()
            self.blocks = FakeBlocks()
            self.instances.append(self)

    monkeypatch.setitem(sys.modules, "notion_client", SimpleNamespace(Client=FakeClient))
    return FakeClient


def test_notion_client_creates_database_page_with_schema_mapped_properties(monkeypatch):
    fake_client = _install_fake_notion_sdk(monkeypatch)

    client = NotionPaperClient(token="secret", database_id="db-1")
    result = client.upsert_paper_page(
        notion_key="doi:10.123/demo",
        title="Demo Paper",
        preview="# Demo Paper\n\n## Metadata\n- Authors: Ada\nPlain paragraph",
    )

    sdk = fake_client.instances[0]
    assert sdk.auth == "secret"
    assert result.notion_page_id == "created-page"
    assert result.created is True
    assert result.updated is False
    assert sdk.databases.retrieves == [{"database_id": "db-1"}]
    assert sdk.databases.queries[0]["filter"] == {
        "property": "PaperScout Key",
        "rich_text": {"equals": "doi:10.123/demo"},
    }

    created = sdk.pages.created[0]
    assert created["parent"] == {"database_id": "db-1"}
    assert set(created["properties"]) == {"Title", "PaperScout Key"}
    assert created["properties"]["Title"]["title"][0]["text"]["content"] == "Demo Paper"
    assert created["properties"]["PaperScout Key"]["rich_text"][0]["text"]["content"] == "doi:10.123/demo"
    assert [block["type"] for block in created["children"]] == [
        "heading_1",
        "heading_2",
        "bulleted_list_item",
        "paragraph",
    ]


def test_notion_client_appends_blocks_when_database_page_exists(monkeypatch):
    fake_client = _install_fake_notion_sdk(monkeypatch, query_results=[{"id": "existing-page"}])

    client = NotionPaperClient(token="secret", database_id="db-1")
    result = client.upsert_paper_page(
        notion_key="paper_id:P1",
        title="Existing Paper",
        preview="# Existing Paper\n\n## Summary\nUpdated summary",
    )

    sdk = fake_client.instances[0]
    assert result.notion_page_id == "existing-page"
    assert result.created is False
    assert result.updated is True
    assert sdk.pages.created == []
    assert sdk.blocks.children.appended[0]["block_id"] == "existing-page"
    assert [block["type"] for block in sdk.blocks.children.appended[0]["children"]] == [
        "heading_1",
        "heading_2",
        "paragraph",
    ]


def test_notion_client_rejects_database_without_idempotency_property(monkeypatch):
    _install_fake_notion_sdk(monkeypatch, properties={"Name": {"type": "title"}})

    with pytest.raises(NotionConfigError, match="PaperScout Key"):
        NotionPaperClient(token="secret", database_id="db-1")


def test_notion_client_can_create_child_page_under_parent_page(monkeypatch):
    fake_client = _install_fake_notion_sdk(monkeypatch)

    client = NotionPaperClient(token="secret", parent_page_id="parent-1")
    result = client.upsert_paper_page(
        notion_key="paper_id:P2",
        title="Parent Page Paper",
        preview="# Parent Page Paper",
    )

    sdk = fake_client.instances[0]
    assert result.notion_page_id == "created-page"
    assert sdk.databases.retrieves == []
    assert sdk.databases.queries == []
    assert sdk.pages.created[0]["parent"] == {"page_id": "parent-1"}
    assert sdk.pages.created[0]["properties"] == {
        "title": {"title": [{"type": "text", "text": {"content": "Parent Page Paper"}}]}
    }


def test_notion_client_can_create_private_workspace_page(monkeypatch):
    fake_client = _install_fake_notion_sdk(monkeypatch)
    calls = []

    class FakeResponse:
        status_code = 200
        content = b'{"id":"workspace-page"}'

        def json(self):
            return {"id": "workspace-page"}

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("agent.tools.notion_client.requests.request", fake_request)

    client = NotionPaperClient(token="oauth-token", workspace_parent=True)
    result = client.upsert_paper_page(
        notion_key="paper_id:P3",
        title="Workspace Paper",
        preview="# Workspace Paper",
    )

    assert result.notion_page_id == "workspace-page"
    assert fake_client.instances[0].pages.created == []
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://api.notion.com/v1/pages"
    assert calls[0]["headers"]["Authorization"] == "Bearer oauth-token"
    assert calls[0]["json"]["parent"] == {"workspace": True}
    assert calls[0]["json"]["properties"]["title"]["title"][0]["text"]["content"] == "Workspace Paper"


def test_notion_oauth_store_roundtrip_and_export_mapping(tmp_path):
    db_path = tmp_path / "library.sqlite3"
    notion_oauth.save_connection(
        {
            "access_token": "token",
            "refresh_token": "refresh",
            "workspace_id": "workspace-1",
            "workspace_name": "Research",
            "bot_id": "bot-1",
            "owner": {"type": "user"},
        },
        db_path=db_path,
    )

    conn = notion_oauth.get_connection(db_path=db_path)
    assert conn is not None
    assert conn["access_token"] == "token"
    assert conn["workspace_name"] == "Research"

    notion_oauth.save_export_page(
        notion_key="doi:10/demo",
        notion_page_id="page-1",
        paper_id="P1",
        db_path=db_path,
    )
    assert notion_oauth.get_export_page("doi:10/demo", db_path=db_path) == "page-1"

    notion_oauth.delete_connection(db_path=db_path)
    assert notion_oauth.get_connection(db_path=db_path) is None
