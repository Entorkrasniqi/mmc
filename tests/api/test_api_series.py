"""Time series (ontology.md: telemetry samples are a time series, not objects). Samples are written straight into the table, with
values chosen so that every bucket can be worked out on paper."""
import math
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("psycopg")

BASE = 1_800_000_000_000                       # 2027-01-15T08:00:00Z in spacecraft time (ms since 1970)
START = datetime(2027, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
PATH = "/api/spacecraft/MINISAT-1/series/battery_soc_pct"


def put(world, rows, parameter="battery_soc_pct", spacecraft="MINISAT-1"):
    """rows = [(seconds after BASE, value)]"""
    import psycopg
    with psycopg.connect(world.db.conninfo("admin")) as conn:
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO ops.telemetry_samples (spacecraft_id, parameter_name, sc_time_ms, value) "
                            "VALUES (%s, %s, %s, %s)", [(spacecraft, parameter, BASE + int(s * 1000), v) for s, v in rows])


def at(seconds):
    return (START + timedelta(seconds=seconds)).isoformat()


def get(api, **params):
    return api.ok(api.get("vera", PATH, **params))


def test_the_time_in_the_test_is_what_it_says():
    assert BASE == int(START.timestamp() * 1000)


# ------------------------------------------------------------------------------------------------ raw samples

def test_a_few_samples_come_back_as_they_are_with_the_definition_for_the_chart(api):
    put(api.world, [(1, 50.0), (2, 49.0), (3, 48.5), (4, 47.0), (5, 46.0)])
    series = get(api, **{"from": at(0), "to": at(10)})
    assert series["resolution"] == "raw" and series["bucket_ms"] is None and series["samples"] == 5
    assert [(p["t_ms"] - BASE, p["v"]) for p in series["points"]] == [(1000, 50.0), (2000, 49.0), (3000, 48.5), (4000, 47.0), (5000, 46.0)]
    assert series["points"][0]["t"] == "2027-01-15T08:00:01.000+00:00"
    assert series["parameter"]["name"] == "battery_soc_pct" and series["parameter"]["warning"] == [35, None]
    assert series["parameter"]["critical"] == [20, None] and series["parameter"]["unit"] == "%"
    assert (series["from"], series["to"]) == (at(0).replace("+00:00", ".000+00:00"), at(10).replace("+00:00", ".000+00:00"))


def test_the_bounds_are_inclusive_at_the_millisecond(api):
    put(api.world, [(1, 1.0), (2, 2.0), (3, 3.0)])
    assert [p["v"] for p in get(api, **{"from": at(1), "to": at(3)})["points"]] == [1.0, 2.0, 3.0]
    assert [p["v"] for p in get(api, **{"from": at(1.001), "to": at(2.999)})["points"]] == [2.0]
    assert [p["v"] for p in get(api, **{"from": at(2), "to": at(2)})["points"]] == [2.0]
    assert get(api, **{"from": at(3.001), "to": at(9)})["points"] == []


def test_a_bound_between_two_milliseconds_is_rounded_inwards(api):
    """Samples sit on whole milliseconds. A window that starts at 1.0005 s starts at 1.001 s, one that ends at 2.9995 s ends at
    2.999 s: the samples at exactly 1.000 s and 3.000 s lie outside. (A float timestamp times 1000 can land a millisecond off.)"""
    put(api.world, [(1, 1.0), (2, 2.0), (3, 3.0)])
    assert [p["v"] for p in get(api, **{"from": at(1.0005), "to": at(2.9995)})["points"]] == [2.0]
    assert [p["v"] for p in get(api, **{"from": at(0.9995), "to": at(3.0005)})["points"]] == [1.0, 2.0, 3.0]


def test_without_bounds_the_series_ends_at_its_newest_sample_and_looks_back_an_hour(api):
    put(api.world, [(0, 1.0), (3000, 2.0), (3599, 3.0), (3600, 4.0), (7200, 5.0)])
    series = get(api)
    assert series["to"].startswith("2027-01-15T10:00:00") and series["from"].startswith("2027-01-15T09:00:00")
    assert [p["v"] for p in series["points"]] == [4.0, 5.0]               # 7200 s back to 3600 s, both ends included
    assert [p["v"] for p in get(api, window_s=3601)["points"]] == [3.0, 4.0, 5.0]
    assert [p["v"] for p in get(api, window_s=7200)["points"]] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [p["v"] for p in get(api, **{"to": at(3000)})["points"]] == [1.0, 2.0]          # 'to' given, 'from' = to - 1 h


def test_a_parameter_with_no_samples_is_an_empty_series_not_an_error(api):
    series = api.ok(api.get("vera", "/api/spacecraft/MINISAT-1/series/battery_voltage"))
    assert series["points"] == [] and series["samples"] == 0 and series["from"] is None and series["to"] is None
    assert series["parameter"]["name"] == "battery_voltage"


def test_samples_of_other_parameters_and_spacecraft_do_not_leak_in(api):
    api.world.db.commit("migrator", "INSERT INTO ops.spacecraft (spacecraft_id, name) VALUES ('MINISAT-2', 'Second')")
    put(api.world, [(1, 11.0)], spacecraft="MINISAT-1")
    put(api.world, [(1, 22.0), (2, 23.0)], spacecraft="MINISAT-2")
    put(api.world, [(1, 33.0)], parameter="battery_voltage")
    assert [p["v"] for p in get(api, **{"from": at(0), "to": at(9)})["points"]] == [11.0]
    other = api.ok(api.get("vera", "/api/spacecraft/MINISAT-2/series/battery_soc_pct", **{"from": at(0), "to": at(9)}))
    assert [p["v"] for p in other["points"]] == [22.0, 23.0]


# ------------------------------------------------------------------------------------------------ thinning

def test_many_samples_are_grouped_into_buckets_with_mean_min_max_and_count(api):
    """100 samples 1 s apart with value = index, asked for 10 points over [0 s, 99 s]: the bucket width is
    ceil(99001 / 10) = 9901 ms, and sample i falls in bucket floor(1000 i / 9901) = floor(i / 9.901): ten samples each."""
    put(api.world, [(i, float(i)) for i in range(100)])
    series = get(api, **{"from": at(0), "to": at(99), "max_points": 10})
    assert series["resolution"] == "bucketed" and series["bucket_ms"] == 9901 and series["samples"] == 100
    assert len(series["points"]) == 10
    for b, point in enumerate(series["points"]):
        low, high = 10 * b, 10 * b + 9
        assert (point["t_ms"] - BASE, point["min"], point["max"], point["n"]) == (low * 1000, float(low), float(high), 10)
        assert point["v"] == pytest.approx((low + high) / 2.0)


@pytest.mark.parametrize("max_points", [2, 3, 7, 10, 33, 99])
def test_a_thinned_series_never_has_more_points_than_asked_and_loses_no_sample(api, max_points):
    put(api.world, [(i * 0.7, float((i * 37) % 101)) for i in range(150)])
    series = get(api, **{"from": at(0), "to": at(110), "max_points": max_points})
    assert series["resolution"] == "bucketed" and len(series["points"]) <= max_points
    assert sum(p["n"] for p in series["points"]) == 150
    assert min(p["min"] for p in series["points"]) == 0.0 and max(p["max"] for p in series["points"]) == 100.0
    times = [p["t_ms"] for p in series["points"]]
    assert times == sorted(times) and len(set(times)) == len(times)


def test_exactly_max_points_samples_are_not_thinned(api):
    put(api.world, [(i, float(i)) for i in range(10)])
    assert get(api, **{"from": at(0), "to": at(9), "max_points": 10})["resolution"] == "raw"
    assert get(api, **{"from": at(0), "to": at(9), "max_points": 9})["resolution"] == "bucketed"


def test_a_spike_inside_a_bucket_is_still_visible_in_its_maximum(api):
    put(api.world, [(i, 99.0 if i == 57 else 10.0) for i in range(100)])
    series = get(api, **{"from": at(0), "to": at(99), "max_points": 10})
    spiked = [p for p in series["points"] if p["max"] == 99.0]
    assert len(spiked) == 1 and spiked[0]["min"] == 10.0 and spiked[0]["v"] == pytest.approx((99.0 + 9 * 10.0) / 10.0)
    assert spiked[0]["t_ms"] - BASE == 50_000                        # the bucket that holds sample 57 starts at sample 50


# ------------------------------------------------------------------------------------------------ values JSON cannot carry

def test_nan_and_infinity_come_back_as_null_not_as_a_server_error(api):
    """float32 telemetry may legitimately be NaN or infinite; JSON has no way to write either."""
    put(api.world, [(1, 5.0), (2, math.nan), (3, math.inf), (4, -math.inf), (5, 7.0)])
    raw = get(api, **{"from": at(0), "to": at(9)})
    assert [p["v"] for p in raw["points"]] == [5.0, None, None, None, 7.0]


def test_the_store_itself_never_hands_out_a_non_finite_number(api):
    """Not left to the web framework: some versions refuse to encode NaN, others quietly write null. The query layer settles it."""
    from minisat.api import store
    put(api.world, [(1, 5.0), (2, math.nan), (3, math.inf), (4, -math.inf), (5, 7.0)])
    with api.app.state.ctx.store.session() as conn:
        raw = store.series(conn, "MINISAT-1", "battery_soc_pct", BASE, BASE + 10_000, 100)
        bucketed = store.series(conn, "MINISAT-1", "battery_soc_pct", BASE, BASE + 10_000, 2)
    assert [p["v"] for p in raw["points"]] == [5.0, None, None, None, 7.0]
    for point in bucketed["points"]:
        assert all(point[k] is None or math.isfinite(point[k]) for k in ("v", "min", "max"))


def test_a_bucket_ignores_non_finite_values_in_its_statistics_but_still_counts_them(api):
    put(api.world, [(0, 2.0), (1, math.nan), (2, 4.0), (3, math.inf), (4, math.nan), (5, math.nan)])
    series = get(api, **{"from": at(0), "to": at(5), "max_points": 2})
    # bucket width = ceil(5001 / 2) = 2501 ms: the samples at 0, 1, 2 s are the first bucket and 3, 4, 5 s the second
    assert series["bucket_ms"] == 2501 and [p["n"] for p in series["points"]] == [3, 3]
    first, second = series["points"]
    assert (first["v"], first["min"], first["max"]) == (3.0, 2.0, 4.0)          # the NaN at 1 s is not averaged in
    assert (second["v"], second["min"], second["max"]) == (None, None, None)    # infinity and NaN only


# ------------------------------------------------------------------------------------------------ bad requests

@pytest.mark.parametrize("params", [{"max_points": 1}, {"max_points": 5001}, {"window_s": 0}, {"window_s": -5},
                                    {"window_s": 31 * 86400}, {"from": "2027-01-15T08:00:00"}, {"to": "yesterday"}])
def test_nonsense_parameters_are_refused(api, params):
    put(api.world, [(1, 1.0)])
    assert api.get("vera", PATH, **params).status_code == 422


def test_a_window_that_ends_before_it_starts_is_refused(api):
    put(api.world, [(1, 1.0)])
    response = api.get("vera", PATH, **{"from": at(10), "to": at(5)})
    assert response.status_code == 422 and "before" in response.json()["detail"]


def test_an_unknown_parameter_is_404(api):
    assert api.get("vera", "/api/spacecraft/MINISAT-1/series/not_a_parameter").status_code == 404


def test_a_wide_window_over_few_samples_is_cheap_and_correct(api):
    put(api.world, [(1, 1.0), (30 * 86400 - 1, 2.0)])
    series = get(api, **{"from": at(0), "to": at(30 * 86400)})
    assert [p["v"] for p in series["points"]] == [1.0, 2.0]
