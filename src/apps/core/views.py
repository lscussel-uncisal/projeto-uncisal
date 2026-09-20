from django.http import JsonResponse


def healthz(request):
    """Endpoint simples de health-check (usado pelo HEALTHCHECK do Docker)."""
    return JsonResponse({"status": "ok"})
