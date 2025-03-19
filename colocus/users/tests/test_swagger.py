import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db(databases=["default", "core"])


def test_swagger_accessible_by_admin(admin_client):
    url = reverse("api-docs")
    response = admin_client.get(url)
    assert response.status_code == 200


def test_swagger_ui_accessible_without_auth(client):
    url = reverse("api-docs")
    response = client.get(url)
    assert response.status_code == 200


def test_api_schema_generated_successfully(admin_client):
    url = reverse("api-schema")
    response = admin_client.get(url)
    assert response.status_code == 200
