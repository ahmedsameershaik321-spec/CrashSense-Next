import httpx

from app.services.nearby_resources import find_nearby_resources


class MockClient:
    def __init__(self, *, timeout, follow_redirects):
        self.timeout = timeout
        self.follow_redirects = follow_redirects

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, *, data, headers):
        self.url = url
        self.data = data
        self.headers = headers
        return httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "way",
                        "id": 2,
                        "center": {"lat": 51.501, "lon": -0.1},
                        "tags": {
                            "amenity": "hospital",
                            "name": "City Hospital",
                            "addr:street": "Road",
                            "addr:city": "London",
                        },
                    },
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 51.5005,
                        "lon": -0.1,
                        "tags": {
                            "emergency": "ambulance_station",
                            "name": "Ambulance Station",
                        },
                    },
                    {
                        "type": "node",
                        "id": 3,
                        "lat": 52.0,
                        "lon": -0.1,
                        "tags": {"amenity": "clinic", "name": "Outside radius"},
                    },
                    {
                        "type": "node",
                        "id": 4,
                        "lat": 51.5,
                        "lon": -0.1,
                        "tags": {"amenity": "restaurant", "name": "Not emergency"},
                    },
                ],
            },
            request=httpx.Request("POST", url),
        )


def test_osm_resources_are_filtered_to_radius_and_sorted_by_distance(monkeypatch):
    monkeypatch.setattr("app.services.nearby_resources.httpx.Client", MockClient)

    resources = find_nearby_resources(51.5, -0.1, 5000)

    assert [resource.name for resource in resources] == [
        "Ambulance Station",
        "City Hospital",
    ]
    assert resources[0].distance_meters < resources[1].distance_meters
    assert resources[1].address == "Road, London"

