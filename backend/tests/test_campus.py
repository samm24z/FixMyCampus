"""The campus layout: matching free text to places and the places endpoint."""

import pytest

from app.core import campus


@pytest.mark.parametrize("text, key", [
    ("Where is the Exam Branch?", "as2"),
    ("exam in AS-2 hall", "as2"),
    ("the fan in the admin block", "civil-block"),
    ("meet at the Principal’s office", "civil-block"),
    ("first year block, AS&H", "as-block"),
    ("water cooler in CSE Block, room 204", "cse-block"),
    ("tap near the indoor sports room above the canteen", "indoor-sports-room"),
    ("lights off in the Boys' Hostel", "boys-hostel"),
    ("the playground", "ground"),
])
def test_places_are_found_by_name_or_alias(text, key):
    assert campus.match_place(text).key == key


@pytest.mark.parametrize("text", ["Room 204 of B Block", "ground floor corridor", "mass of waste", "hotels", ""])
def test_unknown_places_and_partial_words_do_not_match(text):
    assert campus.match_place(text) is None


def test_keys_names_and_aliases_are_unique():
    keys = [p.key for p in campus.PLACES]
    terms = [t for p in campus.PLACES for t in {campus._normal(x) for x in (p.name, *p.aliases)}]
    assert len(set(keys)) == len(keys) and len(set(terms)) == len(terms)
    assert {p.kind for p in campus.PLACES} == {"block", "facility"}


def test_location_is_composed_from_place_and_detail():
    assert campus.compose_location("CSE Block", "Room 204") == "CSE Block, Room 204"
    assert campus.compose_location("CSE Block", "  ") == "CSE Block"
    assert campus.compose_location("", "Room 204") == "Room 204"


async def test_places_need_sign_in_and_list_every_place(async_client, login):
    assert (await async_client.get("/api/v1/campus/places")).status_code in (401, 403)
    response = await async_client.get("/api/v1/campus/places", headers=await login("student"))
    assert response.status_code == 200
    places = response.json()
    assert [p["key"] for p in places] == [p.key for p in campus.PLACES]
    assert set(places[0]) == {"key", "name", "kind", "description"}


def test_same_place_compares_campus_places_and_falls_back_to_exact_text():
    from app.core.campus import same_place
    assert same_place("CSE Block, Room 204", "cse block 2nd floor")
    assert not same_place("CSE Block, Room 204", "ECE Block, Room 204")
    assert not same_place("CSE Block", "Room 204")
    assert same_place("Room 204", "room 204") and not same_place("Room 204", "Room 205")
