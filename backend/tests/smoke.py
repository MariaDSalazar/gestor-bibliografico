"""Smoke test del backend FastAPI: ejerce la API de extremo a extremo, con login.

Uso (desde backend/, con el venv activo):  python -m tests.smoke
"""

from __future__ import annotations

import os
import tempfile
import uuid

# BD temporal (SQLite) ANTES de importar la app.
os.environ["BIBLIO_DATA"] = os.path.join(tempfile.gettempdir(), f"biblio-py-{uuid.uuid4().hex}")
os.environ.pop("DATABASE_URL", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
fails = 0


def check(cond, msg):
    global fails
    print(("  OK " if cond else "  XX FALLO: ") + msg)
    if not cond:
        fails += 1


def main():
    r = client.get("/api/health")
    check(r.status_code == 200 and r.json()["ok"], "health responde ok")

    # Sin token, la API protegida responde 401
    r = client.get("/api/documents")
    check(r.status_code == 401, "sin token -> 401")

    # Registro + token
    r = client.post("/api/auth/register", json={"username": "tester", "password": "secreto123"})
    check(r.status_code == 200 and r.json().get("token"), "registro -> token")
    H = {"Authorization": f"Bearer {r.json()['token']}"}

    r = client.get("/api/auth/me", headers=H)
    check(r.status_code == 200 and r.json()["username"] == "tester", "auth/me devuelve el usuario")

    r = client.post("/api/auth/register", json={"username": "tester", "password": "x"})
    check(r.status_code == 400, "usuario duplicado -> 400")
    r = client.post("/api/auth/login", json={"username": "tester", "password": "malo"})
    check(r.status_code == 400, "login con clave incorrecta -> 400")

    r = client.get("/api/documents", headers=H)
    check(r.status_code == 200 and r.json() == [], "biblioteca arranca vacia")

    csl = {
        "type": "article-journal",
        "title": "Un estudio de ejemplo",
        "author": [{"family": "García", "given": "Ana"}],
        "issued": {"date-parts": [[2020]]},
        "container-title": "Revista de Pruebas",
        "DOI": "10.1000/ejemplo",
    }
    r = client.post("/api/documents", headers=H, json={"csl": csl})
    check(r.status_code == 201 and r.json()["id"] > 0, "crea documento (201)")
    doc = r.json()
    check(doc["title"] == "Un estudio de ejemplo" and doc["year"] == 2020, "desnormaliza title/year")
    check(doc["has_pdf"] is False, "documento nuevo no tiene PDF")
    did = doc["id"]

    r = client.get(f"/api/documents/{did}", headers=H)
    check(r.json()["csl"]["author"][0]["family"] == "García", "recupera CSL-JSON integro (UTF-8)")

    # Edición
    r = client.put(f"/api/documents/{did}", headers=H, json={"csl": {**csl, "title": "Corregido"}})
    check(r.status_code == 200 and r.json()["title"] == "Corregido", "edita documento (PUT)")

    # PDF en la BD
    r = client.post(f"/api/documents/{did}/pdf", headers={**H, "Content-Type": "application/pdf"}, content=b"%PDF-1.4 fake")
    check(r.status_code == 204, "guarda PDF en la BD (204)")
    r = client.get(f"/api/documents/{did}", headers=H)
    check(r.json()["has_pdf"] is True, "has_pdf=True tras guardar")
    r = client.get(f"/api/documents/{did}/pdf", headers=H)
    check(r.status_code == 200 and r.content.startswith(b"%PDF"), "sirve el PDF (200)")

    # Carpetas
    r = client.post("/api/collections", headers=H, json={"name": "Tesis"})
    check(r.status_code == 201, "crea carpeta")
    cid = r.json()["id"]
    r = client.post(f"/api/collections/{cid}/documents", headers=H, json={"documentId": did})
    check(r.status_code == 204, "asigna documento a carpeta")
    r = client.get(f"/api/documents?collection={cid}", headers=H)
    check(len(r.json()) == 1, "filtra por carpeta")
    r = client.get("/api/collections", headers=H)
    check(r.json()[0]["doc_count"] == 1, "carpeta refleja 1 doc")
    r = client.delete(f"/api/collections/{cid}", headers=H)
    check(r.status_code == 204, "borra carpeta")
    r = client.get("/api/documents", headers=H)
    check(len(r.json()) == 1, "borrar carpeta NO borra documentos")

    # Citas
    r = client.post("/api/citations/reference", headers=H, json={"csl": csl, "style": "apa"})
    check(r.status_code == 200 and "(" in r.json()["result"], "citations APA -> 200")
    r = client.post("/api/citations/reference", headers=H, json={"csl": csl, "style": "bibtex"})
    check(r.status_code == 200 and r.json()["result"].startswith("@"), "citations BibTeX -> 200")
    r = client.post("/api/citations/in-text", headers=H, json={"csl": csl, "variante": "narrative"})
    check(r.status_code == 200 and r.json()["result"], "citations in-text -> 200")

    # Exportación
    r = client.post("/api/export", headers=H, json={"style": "apa"})
    check(r.status_code == 200 and "attachment" in r.headers.get("content-disposition", ""), "export APA (descarga)")

    # Aislamiento entre usuarios
    r = client.post("/api/auth/register", json={"username": "otro", "password": "secreto123"})
    H2 = {"Authorization": f"Bearer {r.json()['token']}"}
    r = client.get("/api/documents", headers=H2)
    check(r.json() == [], "otro usuario NO ve documentos ajenos")
    r = client.get(f"/api/documents/{did}", headers=H2)
    check(r.status_code == 404, "otro usuario NO accede a doc ajeno (404)")

    r = client.delete(f"/api/documents/{did}", headers=H)
    check(r.status_code == 204, "elimina documento (204)")

    print("\n" + ("OK  Smoke FastAPI: TODO OK" if fails == 0 else f"XX  {fails} fallos"))
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
