"""Unit tests for the HTMX response helpers in accounts/htmx.py."""

import json

from django.http import HttpResponse
from django.test import RequestFactory

from accounts.htmx import htmx_or_redirect, hx_response, set_hx_headers


def test_hx_response_defaults_204_no_headers():
    response = hx_response()
    assert response.status_code == 204
    assert "HX-Trigger" not in response.headers
    assert "HX-Redirect" not in response.headers
    assert "HX-Refresh" not in response.headers


def test_hx_response_string_trigger_kept_verbatim():
    response = hx_response(trigger="junkChanged")
    assert response.status_code == 204
    assert response["HX-Trigger"] == "junkChanged"


def test_hx_response_dict_trigger_equals_json_dumps():
    trigger = {"appModalClose": True, "agendaChanged": True}
    response = hx_response(trigger=trigger)
    assert response["HX-Trigger"] == json.dumps(trigger)


def test_hx_response_redirect_and_refresh_and_status():
    response = hx_response(redirect="/shops/1/", refresh=True, status=200)
    assert response.status_code == 200
    assert response["HX-Redirect"] == "/shops/1/"
    assert response["HX-Refresh"] == "true"


def test_hx_response_all_together():
    trigger = {"toast": {"message": "Sold junk.", "type": "success"}}
    response = hx_response(trigger=trigger, redirect="/shops/detail/1/", refresh=True, status=204)
    assert response.status_code == 204
    assert response["HX-Trigger"] == json.dumps(trigger)
    assert response["HX-Redirect"] == "/shops/detail/1/"
    assert response["HX-Refresh"] == "true"


def test_htmx_or_redirect_htmx_request():
    factory = RequestFactory()
    request = factory.get("/", HTTP_HX_REQUEST="true")
    response = htmx_or_redirect(request, "/shops/1/", trigger="junkChanged")
    assert response.status_code == 204
    assert response["HX-Redirect"] == "/shops/1/"
    assert response["HX-Trigger"] == "junkChanged"


def test_htmx_or_redirect_non_htmx_request():
    factory = RequestFactory()
    request = factory.get("/")
    response = htmx_or_redirect(request, "/shops/1/")
    assert response.status_code == 302
    assert response["Location"] == "/shops/1/"


def test_set_hx_headers_keeps_body_and_status():
    response = HttpResponse("partial body", status=200)
    out = set_hx_headers(response, trigger={"toast": {"message": "m", "type": "success"}})
    assert out is response
    assert response.status_code == 200
    assert response.content == b"partial body"
    assert response["HX-Trigger"] == json.dumps({"toast": {"message": "m", "type": "success"}})
