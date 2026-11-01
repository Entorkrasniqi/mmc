"""Fixtures of the API tests in tests/api (imported by tests/conftest.py, like dbfixtures.py: a second conftest.py in a
subfolder would shadow the first one for every test that does ``from conftest import ...``).

They need FastAPI, httpx and a PostgreSQL server (see dbfixtures.py); otherwise the tests skip.
"""
import pytest


@pytest.fixture()
def api(world):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from apihelpers import Api
    return Api(world)


@pytest.fixture()
def ground(world):
    pytest.importorskip("fastapi")
    from apihelpers import Ground
    made = []

    def make(**kw):
        made.append(Ground(world, **kw))
        return made[-1]
    yield make
    for g in made:
        g.close()
