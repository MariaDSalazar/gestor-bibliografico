"""Adaptador de citas (Fase 1).

- IEEE: citeproc-py + ieee.csl (estilo oficial CSL, locale es-ES).
- APA 7: formateador propio en español (referencia + variantes de cita en el texto).
  citeproc-py 0.6.0 no procesa el apa.csl moderno (CSL 1.0.2), y además las
  variantes APA in-text (narrativa, parentética, directa corta/larga) no las
  genera citeproc. Ver CONTEXTO.md §7-ofic.
- BibTeX: generación propia desde CSL-JSON.

Formato canónico de entrada: CSL-JSON. Todo en español (locale es-ES).
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

from ...domain.ports import CitationFormatter

warnings.filterwarnings("ignore")


class CiteprocCitationFormatter(CitationFormatter):
    def __init__(self, csl_dir: str | Path):
        self._dir = Path(csl_dir)

    # ───────────────────────── API del puerto ─────────────────────────
    def reference(self, csl, style: str = "apa") -> str:
        style = (style or "apa").strip().lower()
        items = [c for c in (csl if isinstance(csl, list) else [csl]) if c]
        if not items:
            return ""
        if style == "bibtex":
            return "\n\n".join(self._bibtex(c) for c in items)
        if style == "ieee":
            return self._ieee(items)
        return "\n\n".join(self._apa_reference(c) for c in items)  # apa por defecto

    def in_text(self, csl: dict, opts: dict) -> str:
        variante = (opts.get("variante") or "parenthetical").strip().lower()
        pagina = (opts.get("pagina") or "").strip()
        texto = (opts.get("textoCitado") or "").strip()
        autores_p = self._intext_authors(csl.get("author", []))
        anio = self._year_str(csl)
        pag = f", p. {pagina}" if pagina else ""

        if variante in ("narrative", "narrativa"):
            return f"{autores_p} ({anio})"
        if variante in ("direct_short", "directa_corta", "corta"):
            return f'"{texto}" ({autores_p}, {anio}{pag})'
        if variante in ("direct_long", "directa_larga", "larga"):
            return f"{texto}\n    ({autores_p}, {anio}{pag})"
        # Cita de fuente secundaria ("como se citó en"): el doc actual es la fuente
        # secundaria; la fuente original (la citada) la aporta el usuario.
        if variante in ("secundaria", "fuente_secundaria"):
            orig = (opts.get("autorOriginal") or "").strip() or "Autor original"
            orig_anio = (opts.get("anioOriginal") or "").strip() or "s. f."
            return f"({orig}, {orig_anio}, como se citó en {autores_p}, {anio})"
        if variante in ("secundaria_narrativa",):
            orig = (opts.get("autorOriginal") or "").strip() or "Autor original"
            orig_anio = (opts.get("anioOriginal") or "").strip() or "s. f."
            return f"{orig} ({orig_anio}, como se citó en {autores_p}, {anio})"
        # Varias fuentes originales citadas a través del MISMO documento secundario.
        # APA: ordenadas alfabéticamente, separadas por ";", con "como se citó en" al final.
        if variante in ("secundaria_multiple",):
            partes = []
            for f in opts.get("fuentes") or []:
                a = (f.get("autor") or "").strip()
                y = (f.get("anio") or "").strip() or "s. f."
                if a:
                    partes.append((a.lower(), f"{a}, {y}"))
            if not partes:
                return ""
            partes.sort(key=lambda p: p[0])
            cuerpo = "; ".join(p[1] for p in partes)
            return f"({cuerpo}, como se citó en {autores_p}, {anio})"
        # Varias obras combinadas en un mismo paréntesis (APA: orden alfabético, ";").
        if variante in ("multiple", "combinada"):
            partes = []
            for f in opts.get("fuentes") or []:
                a = (f.get("autor") or "").strip()
                y = (f.get("anio") or "").strip() or "s. f."
                if a:
                    partes.append((a.lower(), f"{a}, {y}"))
            if not partes:
                return ""
            partes.sort(key=lambda p: p[0])
            return "(" + "; ".join(p[1] for p in partes) + ")"
        return f"({autores_p}, {anio}{pag})"  # parentética (por defecto)

    # ───────────────────────── IEEE (citeproc) ─────────────────────────
    def _ieee(self, items: list[dict]) -> str:
        from citeproc import (
            Citation,
            CitationItem,
            CitationStylesBibliography,
            CitationStylesStyle,
            formatter,
        )
        from citeproc.source.json import CiteProcJSON

        src = []
        for i, c in enumerate(items):
            d = dict(c)
            d.setdefault("id", f"ref{i + 1}")
            src.append(d)
        source = CiteProcJSON(src)
        style = CitationStylesStyle(str(self._dir / "ieee.csl"), locale="es-ES", validate=False)
        bib = CitationStylesBibliography(style, source, formatter.plain)
        for d in src:
            bib.register(Citation([CitationItem(d["id"])]))
        salidas = []
        for entry in bib.bibliography():
            texto = "".join(str(x) for x in entry)
            salidas.append(re.sub(r"^\s*\[\d+\]\s*", "", texto))  # quita el "[1]" de lista
        return "\n".join(salidas)

    # ───────────────────────── APA 7 (es-ES) ─────────────────────────
    # Reglas por tipo según APA Style oficial (apastyle.apa.org), Purdue OWL y
    # normas-apa.org. Texto plano: el orden y la puntuación siguen APA 7;
    # la cursiva (revista/volumen, libro, tesis, web, ponencia) se aplica al pegar.
    _MESES = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]

    def _apa_reference(self, csl: dict) -> str:
        tipo = (csl.get("type") or "article-journal").strip()
        autores = self._apa_authors(csl.get("author", []))
        titulo = (csl.get("title") or "").strip().rstrip(".")
        cont = self._container(csl)
        doi = (csl.get("DOI") or "").strip()
        url = (csl.get("URL") or "").strip()
        enlace = f"https://doi.org/{doi}" if doi else url

        # Web y congreso llevan fecha con día/mes; el resto solo el año.
        con_dia = tipo in ("webpage", "paper-conference")
        fecha = self._apa_date(csl, con_dia)
        if autores:
            aut = autores if autores.endswith(".") else autores + "."  # punto tras el autor
            cab = f"{aut} ({fecha})."
        else:
            cab = f"({fecha})."

        if tipo == "article-journal":
            vol = (csl.get("volume") or "").strip()
            num = (csl.get("issue") or "").strip()
            volnum = vol + (f"({num})" if num else "")
            cola = ", ".join(p for p in (cont, volnum, self._pages(csl)) if p)
            cuerpo = f"{titulo}." + (f" {cola}." if cola else "")
        elif tipo == "book":
            editorial = (csl.get("publisher") or "").strip()
            cuerpo = f"{titulo}{self._edicion(csl)}." + (f" {editorial}." if editorial else "")
        elif tipo == "chapter":
            editorial = (csl.get("publisher") or "").strip()
            eds = self._editores(csl.get("editor", []))
            if eds and cont:
                en = f" En {eds}, {cont}{self._edicion(csl)}"
            elif cont:
                en = f" En {cont}{self._edicion(csl)}"
            else:
                en = ""
            pp = f" (pp. {self._pages(csl)})" if self._pages(csl) else ""
            cuerpo = f"{titulo}.{en}{pp}." + (f" {editorial}." if editorial else "")
        elif tipo == "thesis":
            genre = (csl.get("genre") or "Tesis doctoral").strip()
            univ = (csl.get("publisher") or csl.get("publisher-place") or "").strip()
            archivo = (csl.get("archive") or "").strip()
            no_pub = "no publicada" in genre.lower() or "unpublished" in genre.lower()
            if no_pub:  # universidad FUERA del corchete
                cuerpo = f"{titulo} [{genre}]." + (f" {univ}." if univ else "")
            else:  # publicada: universidad DENTRO + repositorio
                desc = f"[{genre}, {univ}]" if univ else f"[{genre}]"
                cuerpo = f"{titulo} {desc}." + (f" {archivo}." if archivo else "")
        elif tipo == "paper-conference":
            genre = (csl.get("genre") or "Ponencia").strip()
            evento = (csl.get("event-title") or csl.get("event") or cont or "").strip()
            lugar = (csl.get("event-place") or "").strip()
            partes = ", ".join(p for p in (evento, lugar) if p)
            cuerpo = f"{titulo} [{genre}]." + (f" {partes}." if partes else "")
        elif tipo == "report":
            num = (csl.get("number") or "").strip()
            editorial = (csl.get("publisher") or "").strip()
            numtxt = f" ({num})" if num else ""
            cuerpo = f"{titulo}{numtxt}." + (f" {editorial}." if editorial else "")
        elif tipo == "webpage":
            cuerpo = f"{titulo}." + (f" {cont}." if cont else "")
        else:
            cuerpo = f"{titulo}." + (f" {cont}." if cont else "")

        ref = f"{cab} {cuerpo}"
        if enlace:  # DOI/URL nunca llevan punto final
            ref = f"{ref} {enlace}"
        ref = " ".join(ref.split())
        return ref.replace(" .", ".").replace("..", ".")

    def _apa_date(self, csl: dict, con_dia: bool = False) -> str:
        parts = (csl.get("issued") or {}).get("date-parts") or []
        if not parts or not parts[0]:
            return "s. f."
        p = parts[0]
        try:
            anio = int(p[0])
        except (ValueError, TypeError, IndexError):
            return "s. f."
        if con_dia and len(p) >= 3:
            try:
                return f"{anio}, {int(p[2])} de {self._MESES[int(p[1]) - 1]}"
            except (ValueError, IndexError):
                pass
        if con_dia and len(p) >= 2:
            try:
                return f"{anio}, {self._MESES[int(p[1]) - 1]}"
            except (ValueError, IndexError):
                pass
        return str(anio)

    def _edicion(self, csl: dict) -> str:
        ed = str(csl.get("edition") or "").strip()
        if not ed:
            return ""
        m = re.search(r"\d+", ed)  # APA es-ES: "(2.ª ed.)"; la 1.ª no se indica
        if m:
            return "" if m.group(0) == "1" else f" ({m.group(0)}.ª ed.)"
        return f" ({ed})"

    def _editores(self, editors: list[dict]) -> str:
        names = []
        for e in editors:
            fam = (e.get("family") or "").strip()
            giv = (e.get("given") or "").strip()
            inits = " ".join(f"{x[0]}." for x in giv.split() if x)
            full = (inits + " " + fam).strip() if inits else fam  # inicial + apellido
            if full:
                names.append(full)
        if not names:
            return ""
        etiqueta = "Ed." if len(names) == 1 else "Eds."
        unidos = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]
        return f"{unidos} ({etiqueta})"

    def _apa_authors(self, authors: list[dict]) -> str:
        names = []
        for a in authors:
            literal = (a.get("literal") or "").strip()  # autor institucional
            if literal:
                names.append(literal)
                continue
            fam = (a.get("family") or "").strip()
            giv = (a.get("given") or "").strip()
            inits = " ".join(f"{p[0]}." for p in giv.replace(".", " ").split() if p)
            if fam and inits:
                names.append(f"{fam}, {inits}")
            elif fam:
                names.append(fam)
            elif giv:
                names.append(giv)
        if not names:
            return ""
        if len(names) == 1:
            return names[0]
        if len(names) <= 20:  # es-ES usa "y" (no "&") antes del último
            return ", ".join(names[:-1]) + ", y " + names[-1]
        return ", ".join(names[:19]) + ", . . . " + names[-1]  # 21+: elipsis sin "y"

    # ───────────────────────── BibTeX ─────────────────────────
    def _bibtex(self, csl: dict) -> str:
        tipos = {
            "article-journal": "article",
            "book": "book",
            "chapter": "incollection",
            "paper-conference": "inproceedings",
            "thesis": "phdthesis",
            "report": "techreport",
            "webpage": "misc",
        }
        bt = tipos.get(csl.get("type"), "misc")
        clave = self._bib_key(csl)

        campos: dict[str, str] = {}
        autores = " and ".join(
            f"{a.get('family', '')}, {a.get('given', '')}".strip().strip(",")
            for a in csl.get("author", [])
            if a.get("family") or a.get("given")
        )
        if autores:
            campos["author"] = autores
        if csl.get("title"):
            campos["title"] = csl["title"]
        cont = self._container(csl)
        if cont:
            campos["journal" if bt == "article" else "booktitle"] = cont
        anio = self._year_str(csl)
        if anio and anio != "s. f.":
            campos["year"] = anio
        for src, dst in (
            ("volume", "volume"), ("issue", "number"), ("edition", "edition"),
            ("publisher", "publisher"), ("DOI", "doi"), ("URL", "url"),
            ("ISBN", "isbn"), ("ISSN", "issn"),
        ):
            if csl.get(src):
                campos[dst] = str(csl[src])
        pags = self._pages(csl)
        if pags:
            campos["pages"] = pags.replace("–", "--")

        cuerpo = ",\n".join(f"  {k} = {{{v}}}" for k, v in campos.items())
        return f"@{bt}{{{clave},\n{cuerpo}\n}}"

    def _bib_key(self, csl: dict) -> str:
        autores = csl.get("author", [])
        fam = (autores[0].get("family") or autores[0].get("given") or "ref") if autores else "ref"
        anio = self._year_str(csl)
        anio = anio if anio != "s. f." else "sf"
        return "".join(ch for ch in f"{fam}{anio}" if ch.isalnum()) or "ref"

    # ───────────────────────── helpers comunes ─────────────────────────
    def _intext_authors(self, authors: list[dict]) -> str:
        fams = [(a.get("family") or a.get("given") or "").strip() for a in authors]
        fams = [f for f in fams if f]
        if not fams:
            return "Anónimo"
        if len(fams) == 1:
            return fams[0]
        if len(fams) == 2:
            return f"{fams[0]} y {fams[1]}"
        return f"{fams[0]} et al."

    def _year_str(self, csl: dict) -> str:
        parts = (csl.get("issued") or {}).get("date-parts") or []
        try:
            return str(int(parts[0][0]))
        except (IndexError, ValueError, TypeError):
            return "s. f."

    def _container(self, csl: dict) -> str:
        c = csl.get("container-title")
        if isinstance(c, list):
            c = c[0] if c else ""
        return (c or "").strip()

    def _pages(self, csl: dict) -> str:
        p = csl.get("page") or csl.get("pages") or ""
        return str(p).strip()
