from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backend_integration_guide_documents_gateway_contract():
    guide = (ROOT / "docs" / "backend-integration.md").read_text(encoding="utf-8")
    for required in (
        "反向代理或 API 网关",
        "X-CSRF-Token",
        "Set-Cookie",
        "Upgrade: websocket",
        "Idempotency-Key",
        "服务账号",
        "API Key",
        "Spring Cloud Gateway",
    ):
        assert required in guide


def test_nginx_example_preserves_auth_csrf_and_websocket_headers():
    nginx = (ROOT / "infra" / "nginx" / "tongpin.conf").read_text(encoding="utf-8")
    for required in (
        "proxy_pass http://tongpin_api/api/v1/",
        "proxy_set_header Cookie",
        "X-CSRF-Token",
        "Idempotency-Key",
        "Upgrade $http_upgrade",
        "Connection $connection_upgrade",
        "proxy_buffering off",
    ):
        assert required in nginx


def test_readme_links_backend_integration_guide():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/backend-integration.md" in readme
    assert "infra/nginx/tongpin.conf" in readme
    assert "服务账号/API Key" in readme
