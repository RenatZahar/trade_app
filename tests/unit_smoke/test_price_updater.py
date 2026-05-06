from modules.bts_price_updater import price_updater


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return []


def test_get_price_data_uses_single_binance_klines_endpoint(monkeypatch):
    requested_urls = []

    def fake_get(url, params):
        requested_urls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(price_updater.requests, "get", fake_get)

    price_updater.get_price_data(1_000, 2_000)

    assert requested_urls == ["https://api.binance.com/api/v3/klines"]
