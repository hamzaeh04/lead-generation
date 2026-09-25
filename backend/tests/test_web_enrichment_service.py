import httpx
import pytest

from app.services.web_enrichment_service import scrape_company_website

pytestmark = pytest.mark.asyncio

_RealAsyncClient = httpx.AsyncClient


def _mocked_async_client(handler):
    """monkeypatch.setattr(httpx, "AsyncClient", ...) replaces the name
    httpx.AsyncClient refers to for the rest of the test — referencing
    httpx.AsyncClient again inside the replacement would call the
    replacement itself (infinite self-reference), so this closes over the
    real class captured above instead."""

    def _factory(**kwargs):
        return _RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return _factory


async def test_scrape_returns_none_when_no_domain_or_website():
    assert await scrape_company_website(domain=None, website=None) is None


async def test_scrape_extracts_visible_text_and_strips_scripts(monkeypatch):
    html = (
        "<html><head><style>body{color:red}</style></head>"
        "<body><script>track()</script>"
        "<nav>Home About</nav>"
        "<main><h1>Acme Dental</h1><p>Same-day appointments for busy families.</p></main>"
        "<footer>Copyright 2026</footer>"
        "</body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=html)

    monkeypatch.setattr(httpx, "AsyncClient", _mocked_async_client(handler))

    excerpt = await scrape_company_website(domain="acme-dental.example", website=None)
    assert excerpt is not None
    assert "Acme Dental" in excerpt
    assert "Same-day appointments" in excerpt
    # script/style/nav/footer content must never leak into the excerpt
    assert "track()" not in excerpt
    assert "color:red" not in excerpt
    assert "Copyright 2026" not in excerpt


async def test_scrape_returns_none_on_non_2xx(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    monkeypatch.setattr(httpx, "AsyncClient", _mocked_async_client(handler))

    assert await scrape_company_website(domain="doesnotexist.example", website=None) is None


async def test_scrape_returns_none_on_network_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    monkeypatch.setattr(httpx, "AsyncClient", _mocked_async_client(handler))

    assert await scrape_company_website(domain="slow.example", website=None) is None


async def test_scrape_skips_non_html_responses(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")

    monkeypatch.setattr(httpx, "AsyncClient", _mocked_async_client(handler))

    assert await scrape_company_website(domain="acme.example", website=None) is None


async def test_scrape_prefers_website_over_domain_and_adds_scheme(monkeypatch):
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>hi</p>")

    monkeypatch.setattr(httpx, "AsyncClient", _mocked_async_client(handler))

    await scrape_company_website(domain="acme.example", website="acme.example/about")
    assert seen_urls == ["https://acme.example/about"]
