"""WSGI entry for PythonAnywhere free hosting (no credit card).

PythonAnywhere free web apps speak WSGI; FastAPI is ASGI, so we wrap it.
"""

from a2wsgi import ASGIMiddleware

from app.main import app as asgi_app

application = ASGIMiddleware(asgi_app)
