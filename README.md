---
title: Gestor Bibliografico
emoji: 📚
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Gestor Bibliográfico

Aplicación web tipo Mendeley: cada usuario importa documentos (DOI, enlace o PDF),
la app extrae los metadatos y genera citas en APA 7, IEEE y BibTeX.

🔗 **App en vivo:** https://MariaSalazar-gestor-bibliografico.hf.space

## Tecnologías
- **Backend:** FastAPI (Python) + SQLAlchemy — SQLite en local, PostgreSQL (Neon) en producción.
- **Extracción:** httpx (DOI/Crossref, Unpaywall) + pypdf.
- **Citas:** formateador propio APA 7 (es-ES) · citeproc-py (IEEE) · BibTeX propio.
- **Login:** propio (contraseña con bcrypt, sesión con JWT).
- **Frontend:** Vue 3 + PrimeVue 4 + PDF.js, vendorizados (sin Node ni build); los sirve el backend.

## Arquitectura (DDD por capas)
```
backend/app/
  domain/          Entidades, value objects, puertos (interfaces) y excepciones. Sin dependencias externas.
  application/     Casos de uso (servicios) que dependen de los PUERTOS, no de implementaciones.
  infrastructure/  Implementaciones: repos SQLAlchemy, httpx/Crossref, pypdf, formateador de citas, seguridad.
  interfaces/      FastAPI: routers, schemas, inyección de dependencias.
  bootstrap.py     Composition root: arma la infraestructura y la inyecta en la aplicación.
  main.py          App FastAPI: mapea excepciones de dominio a HTTP y sirve el frontend.
```
Regla de dependencias: **todo apunta hacia `domain`**; la inversión se resuelve con puertos
abstractos y el composition root.

```
frontend/   index.html, app.js, app.css y vendor/ (Vue, PrimeVue, PDF.js)
resources/  ieee.csl (estilo CSL de IEEE)
```

## Cómo funciona
1. **Inicias sesión** (o te registras): cada usuario tiene su propia biblioteca en la base de datos.
2. **Importas** un documento por DOI, enlace o PDF → se extraen los metadatos a CSL-JSON;
   si el documento es de acceso abierto, también se descarga su PDF.
3. **Revisas y guardas**: el formulario muestra los campos según el tipo (libro, artículo,
   tesis, capítulo, web, ponencia, informe). El PDF queda guardado en la base de datos.
4. **Organizas** en carpetas y **editas** cuando quieras (con el PDF a la vista).
5. **Citas**: genera la referencia y la cita en el texto en APA 7 / IEEE / BibTeX, o
   **descarga** la lista de referencias ordenada A–Z.

### Ejecutar en local
```powershell
cd backend
python -m venv .venv                                    # solo la primera vez
.venv\Scripts\python -m pip install -r requirements.txt # solo la primera vez
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
Abre **http://127.0.0.1:8000**. Pruebas: `python -m tests.smoke` desde `backend/`.
