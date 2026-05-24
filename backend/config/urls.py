import os
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render

def serve_react(request):
    """
    Serves the compiled React index.html from frontend/dist if it exists,
    otherwise displays a friendly developer helper message.
    """
    index_path = os.path.join(settings.BASE_DIR, '..', 'frontend', 'dist', 'index.html')
    if os.path.exists(index_path):
        return render(request, 'index.html')
    return HttpResponse(
        "<html><body style='font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: #0d1117; color: #c9d1d9;'>"
        "<div style='border: 1px solid #30363d; padding: 2.5rem; border-radius: 12px; background-color: #161b22; text-align: center; max-width: 500px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);'>"
        "<h2 style='color: #58a6ff; margin-bottom: 1rem;'>Breathe ESG Ingestion Engine</h2>"
        "<p style='margin-bottom: 1.5rem; line-height: 1.5;'>The Django REST API is running. The React frontend is not yet built.</p>"
        "<div style='background-color: #0d1117; padding: 1rem; border-radius: 8px; border: 1px solid #21262d; text-align: left; font-family: monospace; font-size: 0.9rem; color: #8b949e;'>"
        "# Run React Dev Server:<br/>"
        "cd frontend<br/>"
        "npm run dev<br/><br/>"
        "# Or Build static assets:<br/>"
        "cd frontend<br/>"
        "npm run build"
        "</div>"
        "</div>"
        "</body></html>",
        status=200
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('esg_ingest.urls')),
    re_path(r'^.*$', serve_react, name='react-spa'),
]
