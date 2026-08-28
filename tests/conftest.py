import socket
import pytest

@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    def blocked(*args,**kwargs): raise AssertionError("external network is disabled in tests")
    monkeypatch.setattr(socket,"create_connection",blocked)
