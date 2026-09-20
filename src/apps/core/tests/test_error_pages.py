import pytest
from django.template.loader import render_to_string
from django.test import Client


@pytest.mark.django_db
def test_404_renders_custom_page():
    client = Client()

    response = client.get("/rota-que-nao-existe/")

    assert response.status_code == 404
    assert "Página não encontrada" in response.content.decode()


def test_500_template_renders_without_leaking_internals():
    # Espelha como o Django realmente invoca o template de erro 500: sem request/contexto.
    html = render_to_string("500.html")

    assert "Algo deu errado" in html
    assert "Traceback" not in html
