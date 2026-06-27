/* Gestor Bibliográfico — frontend estático en Vue 3 + PrimeVue 4 (sin build, sin Node).
 * Vue global build + PrimeVue UMD, ambos vendorizados local. El backend FastAPI sirve
 * estos archivos, así que la API va al mismo origen.
 * IMPORTANTE: con compilación de plantillas en el DOM, los componentes se registran y
 * usan en kebab-case con guion (p-*) para evitar colisión con tags HTML nativos. */
const { createApp, reactive, ref, computed, onMounted, watch } = Vue

const API_BASE = '' // mismo origen que el backend

function getToken() {
  return localStorage.getItem('biblio_token') || ''
}

async function api(path, opts = {}) {
  const o = { method: opts.method || 'GET', headers: {} }
  const tk = getToken()
  if (tk) o.headers['Authorization'] = 'Bearer ' + tk
  if (opts.body !== undefined) {
    if (opts.raw) {
      o.body = opts.body
      o.headers['Content-Type'] = opts.contentType || 'application/octet-stream'
    } else {
      o.body = JSON.stringify(opts.body)
      o.headers['Content-Type'] = 'application/json'
    }
  }
  const res = await fetch(API_BASE + path, o)
  if (res.status === 401) {
    localStorage.removeItem('biblio_token')
    window.dispatchEvent(new Event('biblio-unauth'))
  }
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const err = new Error((data && data.detail) || res.statusText)
    err.detail = data && data.detail
    throw err
  }
  return data
}

const App = {
  setup() {
    const toast = PrimeVue.useToast()

    /* ---------- Autenticación ---------- */
    const currentUser = ref(null)
    const authMode = ref('login') // 'login' | 'register'
    const authForm = reactive({ username: '', password: '' })
    const authError = ref('')
    const authBusy = ref(false)

    async function cargarUsuario() {
      if (!getToken()) { currentUser.value = null; return }
      try {
        currentUser.value = await api('/api/auth/me')
      } catch (e) {
        currentUser.value = null
      }
    }

    async function entrar() {
      authError.value = ''
      if (!authForm.username.trim() || !authForm.password) {
        authError.value = 'Escribe usuario y contraseña.'
        return
      }
      authBusy.value = true
      try {
        const ruta = authMode.value === 'register' ? '/api/auth/register' : '/api/auth/login'
        const { token } = await api(ruta, { method: 'POST', body: { username: authForm.username.trim(), password: authForm.password } })
        localStorage.setItem('biblio_token', token)
        authForm.password = ''
        await cargarUsuario()
        await refresh()
      } catch (e) {
        authError.value = errText(e)
      } finally {
        authBusy.value = false
      }
    }

    function cerrarSesion() {
      localStorage.removeItem('biblio_token')
      currentUser.value = null
      documents.value = []
      folders.value = []
      selectedDoc.value = null
    }

    window.addEventListener('biblio-unauth', () => { currentUser.value = null })

    /* ---------- Estado ---------- */
    const documents = ref([])
    const folders = ref([])
    const activeFilter = reactive({ kind: 'all', id: undefined, name: undefined })
    const selectedDoc = ref(null)
    const docsSeleccionados = ref([]) // selección múltiple (checkboxes) para exportar

    const linkInput = ref('')
    const importMsg = ref(null) // { text, kind } — estado de importación inline
    const busy = ref(false)
    const pdfInput = ref(null)

    const showNewFolder = ref(false)
    const newFolderName = ref('')

    const showPreview = ref(false)
    const pendingCsl = ref(null)
    const editingId = ref(null) // id del doc en edición (null = creando uno nuevo)
    const pendingPdfFile = ref(null) // File del PDF a guardar en la BD al guardar
    const pdfUrl = ref(null) // visor: blob URL (import/adjuntar) o /api/documents/{id}/pdf (edición)
    const previewAviso = ref('') // aviso si la extracción automática falló
    const form = reactive({
      type: 'article-journal', title: '', authors: '', year: '', container: '', doi: '', folderId: '',
      // Campos específicos por tipo (APA):
      volume: '', issue: '', page: '',     // artículo
      publisher: '', edition: '',          // libro / capítulo / informe / tesis(universidad)
      editors: '',                         // capítulo (editores del libro)
      genre: '',                           // tesis (tipo) / conferencia (tipo de contribución)
      eventTitle: '', eventPlace: '',      // conferencia
      url: '', number: '',                 // URL (si no hay DOI) / informe (número)
      isbn: '', issn: '',                  // identificadores (no van en APA, sí en BibTeX)
    })

    // El campo "Publicación" cambia de significado según el tipo (revista / libro / sitio).
    const labelContainer = computed(() => {
      const t = form.type
      if (t === 'chapter') return 'Título del libro'
      if (t === 'webpage') return 'Nombre del sitio'
      return 'Revista / Publicación'
    })
    const mostrarContainer = computed(() => ['article-journal', 'chapter', 'webpage'].includes(form.type))
    // Si hay URL (y no PDF), se muestra la página web embebida en el diálogo.
    const webUrl = computed(() => {
      if (pdfUrl.value) return null
      const u = (form.url || '').trim()
      return /^https?:\/\//i.test(u) ? u : null
    })

    const typeOptions = [
      { label: 'Artículo de revista', value: 'article-journal' },
      { label: 'Libro', value: 'book' },
      { label: 'Capítulo de libro', value: 'chapter' },
      { label: 'Tesis / disertación', value: 'thesis' },
      { label: 'Ponencia / congreso', value: 'paper-conference' },
      { label: 'Página web', value: 'webpage' },
      { label: 'Informe', value: 'report' },
    ]
    const typeLabels = Object.fromEntries(typeOptions.map((t) => [t.value, t.label]))
    // Alias de tipos que devuelve Crossref (variantes/guiones distintos) → español.
    Object.assign(typeLabels, {
      'journal-article': 'Artículo de revista',
      'book-chapter': 'Capítulo',
      'proceedings-article': 'Ponencia',
      'posted-content': 'Preprint',
      report: 'Informe',
      thesis: 'Tesis',
      dataset: 'Conjunto de datos',
    })

    /* ---------- Derivados ---------- */
    const libraryTitle = computed(() => {
      if (activeFilter.kind === 'collection') return activeFilter.name
      if (activeFilter.kind === 'none') return 'Sin carpeta'
      return 'Todos los documentos'
    })
    const totalDocs = computed(() => folders.value.reduce((n) => n, documents.value.length))
    const folderSelectOptions = computed(() => [
      { label: '(Sin carpeta)', value: '' },
      ...folders.value.map((f) => ({ label: f.name, value: f.id })),
    ])
    const moveOptions = computed(() => folders.value.map((f) => ({ label: f.name, value: f.id })))

    /* ---------- Toast helpers ---------- */
    const ok = (detail, summary = 'Listo') => toast.add({ severity: 'success', summary, detail, life: 2500 })
    const info = (detail, summary = 'Info') => toast.add({ severity: 'info', summary, detail, life: 2500 })
    const fail = (detail, summary = 'Error') => toast.add({ severity: 'error', summary, detail, life: 4000 })
    const errText = (e) => (e && (e.detail || e.message)) || 'Error inesperado'

    /* ---------- Datos ---------- */
    async function loadFolders() {
      folders.value = await api('/api/collections')
    }
    async function loadLibrary() {
      let q = ''
      if (activeFilter.kind === 'none') q = '?collection=none'
      else if (activeFilter.kind === 'collection') q = '?collection=' + activeFilter.id
      documents.value = await api('/api/documents' + q)
      // Si el doc seleccionado ya no está en la vista, deselecciona.
      if (selectedDoc.value && !documents.value.some((d) => d.id === selectedDoc.value.id)) {
        selectedDoc.value = null
      }
    }
    async function refresh() {
      await Promise.all([loadFolders(), loadLibrary()])
    }
    function setFilter(f) {
      activeFilter.kind = f.kind
      activeFilter.id = f.id
      activeFilter.name = f.name
      return loadLibrary()
    }

    /* ---------- Importación ---------- */
    async function importLink() {
      if (!linkInput.value.trim()) return
      busy.value = true
      importMsg.value = { text: 'Buscando metadatos…', kind: 'info' }
      editingId.value = null
      pendingPdfFile.value = null
      if (pdfUrl.value && pdfUrl.value.startsWith('blob:')) URL.revokeObjectURL(pdfUrl.value)
      pdfUrl.value = null
      previewAviso.value = ''
      try {
        const { csl, pdf } = await api('/api/documents/import', { method: 'POST', body: { input: linkInput.value.trim() } })
        importMsg.value = null
        if (pdf) {
          // El enlace era un PDF: el backend lo descargó y lo devolvió en base64.
          const bytes = Uint8Array.from(atob(pdf), (c) => c.charCodeAt(0))
          const blob = new Blob([bytes], { type: 'application/pdf' })
          pendingPdfFile.value = new File([blob], 'documento.pdf', { type: 'application/pdf' })
          pdfUrl.value = URL.createObjectURL(blob)
        }
        openPreview(csl)
      } catch (e) {
        importMsg.value = { text: errText(e), kind: 'error' }
      } finally {
        busy.value = false
      }
    }
    async function onPdfPicked(ev) {
      const file = ev.target.files && ev.target.files[0]
      if (file) await importPdf(file)
      if (pdfInput.value) pdfInput.value.value = ''
    }
    async function importPdf(file) {
      editingId.value = null
      pendingPdfFile.value = file // se guardará en la BD al guardar el documento
      // Visor: blob URL del PDF para verlo mientras se importa.
      if (pdfUrl.value && pdfUrl.value.startsWith('blob:')) URL.revokeObjectURL(pdfUrl.value)
      pdfUrl.value = URL.createObjectURL(file)
      busy.value = true
      importMsg.value = { text: 'Leyendo "' + file.name + '" y buscando el DOI…', kind: 'info' }
      try {
        const buf = await file.arrayBuffer()
        const { csl } = await api('/api/documents/import-pdf', { method: 'POST', body: buf, raw: true, contentType: 'application/pdf' })
        importMsg.value = null
        previewAviso.value = ''
        openPreview(csl)
      } catch (e) {
        // La extracción automática falló (PDF sin DOI): abrir igual el formulario
        // para que el usuario lea el PDF (a la izquierda) y complete los datos a mano.
        importMsg.value = null
        previewAviso.value = 'No se pudieron extraer los datos automáticamente. Léelos del PDF y complétalos a mano.'
        openPreview({})
        form.doi = '10.' // deja la parte general del DOI; solo falta completar el resto
      } finally {
        busy.value = false
      }
    }
    function onDrop(ev) {
      const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0]
      if (file && file.type === 'application/pdf') importPdf(file)
      else importMsg.value = { text: 'Suelta un archivo PDF.', kind: 'error' }
    }

    /* ---------- Vista previa ---------- */
    function _cargarForm(csl) {
      const issued = csl.issued && csl.issued['date-parts'] && csl.issued['date-parts'][0]
      const cont = Array.isArray(csl['container-title']) ? csl['container-title'][0] : csl['container-title']
      form.type = csl.type || 'article-journal'
      form.title = csl.title || ''
      form.authors = (csl.author || []).map((a) => [a.family, a.given].filter(Boolean).join(', ')).join('; ')
      form.year = issued ? issued[0] : ''
      form.container = cont || ''
      form.doi = csl.DOI || ''
      form.volume = csl.volume || ''
      form.issue = csl.issue || ''
      form.page = csl.page || csl.pages || ''
      form.publisher = csl.publisher || ''
      form.edition = csl.edition || ''
      form.editors = (csl.editor || []).map((a) => [a.family, a.given].filter(Boolean).join(', ')).join('; ')
      form.genre = csl.genre || ''
      form.eventTitle = csl['event-title'] || csl.event || ''
      form.eventPlace = csl['event-place'] || ''
      form.url = csl.URL || ''
      form.number = csl.number || ''
      form.isbn = csl.ISBN || ''
      form.issn = csl.ISSN || ''
    }
    function openPreview(csl) {
      pendingCsl.value = csl
      _cargarForm(csl)
      form.folderId = activeFilter.kind === 'collection' ? activeFilter.id : ''
      showPreview.value = true
    }
    function cerrarPreview() {
      showPreview.value = false
      previewAviso.value = ''
      editingId.value = null
      pendingPdfFile.value = null
      if (pdfUrl.value && pdfUrl.value.startsWith('blob:')) URL.revokeObjectURL(pdfUrl.value)
      pdfUrl.value = null
    }
    function authorsToCsl(text) {
      return text.split(';').map((s) => s.trim()).filter(Boolean).map((part) => {
        const [family, given] = part.split(',').map((x) => (x || '').trim())
        return given ? { family, given } : { family }
      })
    }

    // Abre el formulario para EDITAR un documento ya guardado (muestra su PDF si lo tiene).
    function abrirEditar(doc) {
      if (!doc) return
      const csl = doc.csl || {}
      pendingCsl.value = csl
      editingId.value = doc.id
      pendingPdfFile.value = null
      _cargarForm(csl)
      form.folderId = ''
      previewAviso.value = ''
      if (pdfUrl.value && pdfUrl.value.startsWith('blob:')) URL.revokeObjectURL(pdfUrl.value)
      pdfUrl.value = doc.has_pdf ? '/api/documents/' + doc.id + '/pdf?t=' + Date.now() : null
      showPreview.value = true
    }

    async function subirPdf(docId, file) {
      const buf = await file.arrayBuffer()
      await api('/api/documents/' + docId + '/pdf', { method: 'POST', body: buf, raw: true, contentType: 'application/pdf' })
    }

    // Adjuntar/cambiar el PDF desde el diálogo (se guarda en la BD al guardar).
    function elegirPdfAdjunto(file) {
      if (!file || file.type !== 'application/pdf') return
      if (pdfUrl.value && pdfUrl.value.startsWith('blob:')) URL.revokeObjectURL(pdfUrl.value)
      pdfUrl.value = URL.createObjectURL(file)
      pendingPdfFile.value = file
    }
    function onAdjuntarPicked(ev) {
      elegirPdfAdjunto(ev.target.files && ev.target.files[0])
      ev.target.value = ''
    }
    function onAdjuntarDrop(ev) {
      elegirPdfAdjunto(ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0])
    }

    function formToCsl() {
      const csl = { ...(pendingCsl.value || {}) }
      csl.type = form.type
      csl.title = form.title.trim()
      csl.author = authorsToCsl(form.authors)
      csl.issued = form.year ? { 'date-parts': [[Number(form.year)]] } : undefined
      // helper: setea el campo si tiene valor, o lo borra
      const set = (campo, valor) => {
        if (valor && String(valor).trim()) csl[campo] = String(valor).trim()
        else delete csl[campo]
      }
      set('container-title', form.container)
      set('DOI', form.doi)
      set('volume', form.volume)
      set('issue', form.issue)
      set('page', form.page)
      set('publisher', form.publisher)
      set('edition', form.edition)
      set('genre', form.genre)
      set('event-title', form.eventTitle)
      set('event-place', form.eventPlace)
      set('URL', form.url)
      set('number', form.number)
      set('ISBN', form.isbn)
      set('ISSN', form.issn)
      if (form.editors.trim()) csl.editor = authorsToCsl(form.editors)
      else delete csl.editor
      return csl
    }

    async function savePreview() {
      const csl = formToCsl()
      try {
        if (editingId.value) {
          const id = editingId.value
          await api('/api/documents/' + id, { method: 'PUT', body: { csl } })
          if (pendingPdfFile.value) await subirPdf(id, pendingPdfFile.value)
          await refresh()
          const actualizado = documents.value.find((d) => d.id === id)
          cerrarPreview()
          if (actualizado) selectedDoc.value = actualizado
          ok('Cambios guardados', '✓ Documento')
        } else {
          const doc = await api('/api/documents', { method: 'POST', body: { csl } })
          if (form.folderId) {
            await api('/api/collections/' + form.folderId + '/documents', { method: 'POST', body: { documentId: doc.id } })
          }
          if (pendingPdfFile.value) await subirPdf(doc.id, pendingPdfFile.value)
          await refresh()
          cerrarPreview()
          linkInput.value = ''
          ok('Guardado en la biblioteca', '✓ Documento')
        }
      } catch (e) {
        fail(errText(e))
      }
    }

    /* ---------- Carpetas ---------- */
    async function createFolder() {
      const name = newFolderName.value.trim()
      if (!name) return
      try {
        const c = await api('/api/collections', { method: 'POST', body: { name } })
        newFolderName.value = ''
        showNewFolder.value = false
        await loadFolders()
        ok('Carpeta "' + c.name + '" creada', '📁 Carpeta')
        setFilter({ kind: 'collection', id: c.id, name: c.name }) // saltar a la nueva carpeta
      } catch (e) {
        fail(errText(e))
      }
    }
    async function deleteFolder(id, name) {
      try {
        await api('/api/collections/' + id, { method: 'DELETE' })
        if (activeFilter.kind === 'collection' && activeFilter.id === id) setFilter({ kind: 'all' })
        await refresh()
        info('Carpeta "' + name + '" eliminada (los documentos se conservan)')
      } catch (e) {
        fail(errText(e))
      }
    }
    async function assignDoc(collectionId, documentId) {
      if (!collectionId) return
      try {
        await api('/api/collections/' + collectionId + '/documents', { method: 'POST', body: { documentId } })
        await refresh()
        const c = folders.value.find((f) => f.id === collectionId)
        ok('Movido a "' + (c ? c.name : 'carpeta') + '"')
      } catch (e) {
        fail(errText(e))
      }
    }
    async function unfileDoc(collectionId, documentId) {
      try {
        await api('/api/collections/' + collectionId + '/documents/' + documentId, { method: 'DELETE' })
        await refresh()
        info('Quitado de la carpeta')
      } catch (e) {
        fail(errText(e))
      }
    }
    async function removeDoc(id) {
      try {
        await api('/api/documents/' + id, { method: 'DELETE' })
        if (selectedDoc.value && selectedDoc.value.id === id) selectedDoc.value = null
        await refresh()
        info('Documento eliminado')
      } catch (e) {
        fail(errText(e))
      }
    }

    /* ---------- Citas (Fase 1) ---------- */
    const citaActual = ref(null) // { etiqueta, texto }

    // Copiado robusto: intenta la Clipboard API y cae a execCommand (http sin TLS, sin foco).
    async function copiarTexto(texto) {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(texto)
          return true
        }
      } catch (e) {
        /* sigue al fallback */
      }
      try {
        const ta = document.createElement('textarea')
        ta.value = texto
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.focus()
        ta.select()
        const okc = document.execCommand('copy')
        document.body.removeChild(ta)
        return okc
      } catch (e) {
        return false
      }
    }

    async function copiar(texto) {
      if (await copiarTexto(texto)) ok('Copiado al portapapeles')
      else info('Selecciona el texto del recuadro y cópialo a mano')
    }

    async function citar(style, etiqueta) {
      if (!selectedDoc.value) return
      try {
        const { result } = await api('/api/citations/reference', {
          method: 'POST',
          body: { csl: selectedDoc.value.csl, style },
        })
        citaActual.value = { etiqueta, texto: result }
        if (await copiarTexto(result)) ok(etiqueta + ' copiada al portapapeles', '✓ Cita')
        else info('Cita generada (cópiala del recuadro)', etiqueta)
      } catch (e) {
        fail(errText(e))
      }
    }

    /* ---------- Cita en el texto (in-text APA) — guiada por menú ---------- */
    const showCitarTexto = ref(false)
    const tipoCita = ref('narrative')
    const tiposCita = [
      { label: 'Narrativa — el autor va en la frase', value: 'narrative' },
      { label: 'Parafraseo / parentética', value: 'parenthetical' },
      { label: 'Cita textual corta (menos de 40 palabras)', value: 'directa_corta' },
      { label: 'Cita textual larga (40 palabras o más)', value: 'directa_larga' },
      { label: 'Fuente secundaria («como se citó en»)', value: 'secundaria' },
      { label: 'Varias obras en un paréntesis', value: 'multiple' },
    ]
    const ayudasCita = {
      narrative: 'El autor forma parte de la frase. Ej.: Como señala García (2020), …',
      parenthetical: 'Idea con tus palabras; la referencia va entre paréntesis al final.',
      directa_corta: 'Cita literal entre comillas con la página, integrada en el párrafo.',
      directa_larga: 'Cita literal de 40+ palabras en bloque sangrado, sin comillas, con la página.',
      secundaria: 'Citas a un autor (fuente original) que leíste a través de ESTE documento.',
      multiple: 'Combina varias obras en un mismo paréntesis (orden alfabético).',
    }
    const citaForm = reactive({ pagina: '', textoCitado: '' })
    const secFuentes = ref([{ autor: '', anio: '' }]) // fuentes/obras (autor + año)
    const resultadoCita = ref('') // resultado principal
    const resultadoCita2 = ref('') // segundo resultado (p. ej. secundaria narrativa)

    const citaNecesitaTexto = computed(() => ['directa_corta', 'directa_larga'].includes(tipoCita.value))
    const citaNecesitaFuentes = computed(() => ['secundaria', 'multiple'].includes(tipoCita.value))
    const etiquetaResultado = computed(() =>
      (tiposCita.find((t) => t.value === tipoCita.value) || {}).label || 'Cita')

    function anadirFuente() {
      secFuentes.value.push({ autor: '', anio: '' })
    }
    function quitarFuente(i) {
      secFuentes.value.splice(i, 1)
      if (!secFuentes.value.length) secFuentes.value.push({ autor: '', anio: '' })
    }

    async function inTextApi(variante, extra) {
      const { result } = await api('/api/citations/in-text', {
        method: 'POST',
        body: { csl: selectedDoc.value.csl, variante, ...(extra || {}) },
      })
      return result
    }

    async function generarCita() {
      resultadoCita.value = ''
      resultadoCita2.value = ''
      const t = tipoCita.value
      try {
        if (t === 'narrative' || t === 'parenthetical') {
          resultadoCita.value = await inTextApi(t)
        } else if (t === 'directa_corta' || t === 'directa_larga') {
          if (!citaForm.textoCitado.trim()) return info('Escribe primero el fragmento citado')
          resultadoCita.value = await inTextApi(t, { pagina: citaForm.pagina, textoCitado: citaForm.textoCitado })
        } else if (t === 'secundaria') {
          const fuentes = secFuentes.value.filter((f) => (f.autor || '').trim())
          if (!fuentes.length) return info('Añade al menos una fuente original (autor)')
          resultadoCita.value = await inTextApi('secundaria_multiple', { fuentes })
          if (fuentes.length === 1) {
            resultadoCita2.value = await inTextApi('secundaria_narrativa', {
              autorOriginal: fuentes[0].autor, anioOriginal: fuentes[0].anio,
            })
          }
        } else if (t === 'multiple') {
          const fuentes = secFuentes.value.filter((f) => (f.autor || '').trim())
          if (!fuentes.length) return info('Añade al menos una obra (autor)')
          resultadoCita.value = await inTextApi('multiple', { fuentes })
        }
      } catch (e) {
        fail(errText(e))
      }
    }

    function abrirCitarTexto() {
      if (!selectedDoc.value) return
      tipoCita.value = 'narrative'
      citaForm.pagina = ''
      citaForm.textoCitado = ''
      secFuentes.value = [{ autor: '', anio: '' }]
      resultadoCita.value = ''
      resultadoCita2.value = ''
      showCitarTexto.value = true
      generarCita() // la narrativa no requiere entrada → se muestra de inmediato
    }

    // Al cambiar el tipo en el menú: limpiar y, si no requiere entrada, autogenerar.
    watch(tipoCita, () => {
      resultadoCita.value = ''
      resultadoCita2.value = ''
      if (tipoCita.value === 'narrative' || tipoCita.value === 'parenthetical') generarCita()
    })

    // Al cambiar de documento, ocultar citas y diálogo.
    watch(selectedDoc, () => {
      citaActual.value = null
      showCitarTexto.value = false
    })

    /* ---------- Exportar / descargar referencias ---------- */
    const showExport = ref(false)
    const exportStyle = ref('apa')
    const exportAlcance = ref('todos')
    const estilosExport = [
      { label: 'APA 7', value: 'apa' },
      { label: 'IEEE', value: 'ieee' },
      { label: 'BibTeX (.bib)', value: 'bibtex' },
    ]
    const alcanceOpciones = computed(() => [
      { label: 'Todos los documentos (' + documents.value.length + ')', value: 'todos' },
      { label: 'Solo los seleccionados (' + docsSeleccionados.value.length + ')', value: 'seleccionados' },
    ])

    function onRowClick(e) {
      selectedDoc.value = e.data // clic en la fila → ver detalle (el checkbox no dispara esto)
    }
    function abrirExport() {
      exportAlcance.value = docsSeleccionados.value.length ? 'seleccionados' : 'todos'
      showExport.value = true
    }
    async function descargarReferencias() {
      const ids = exportAlcance.value === 'seleccionados'
        ? docsSeleccionados.value.map((d) => d.id)
        : null
      try {
        const res = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + getToken() },
          body: JSON.stringify({ ids, style: exportStyle.value }),
        })
        if (!res.ok) {
          fail('No se pudo generar el archivo')
          return
        }
        const blob = await res.blob()
        const disp = res.headers.get('Content-Disposition') || ''
        const m = disp.match(/filename="?([^"]+)"?/)
        const nombre = m ? m[1] : 'referencias.txt'
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = nombre
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
        showExport.value = false
        ok('Descargado: ' + nombre, '✓ Referencias')
      } catch (e) {
        fail(errText(e))
      }
    }

    /* ---------- Presentación ---------- */
    function docAuthors(doc) {
      return (((doc.csl && doc.csl.author) || [])
        .map((a) => [a.given, a.family].filter(Boolean).join(' '))
        .join(', ')) || 'Autor desconocido'
    }
    function typeLabel(t) {
      return typeLabels[t] || t || '—'
    }

    onMounted(async () => {
      await cargarUsuario()
      if (currentUser.value) await refresh()
    })

    return {
      currentUser, authMode, authForm, authError, authBusy, entrar, cerrarSesion,
      documents, folders, activeFilter, selectedDoc,
      linkInput, importMsg, busy, pdfInput,
      showNewFolder, newFolderName,
      showPreview, form, typeOptions, pdfUrl, previewAviso, editingId,
      labelContainer, mostrarContainer, webUrl,
      libraryTitle, totalDocs, folderSelectOptions, moveOptions,
      importLink, onPdfPicked, onDrop, onAdjuntarPicked, onAdjuntarDrop,
      savePreview, cerrarPreview, abrirEditar, createFolder, deleteFolder,
      assignDoc, unfileDoc, removeDoc, citar, copiar, citaActual,
      docsSeleccionados, onRowClick, showExport, exportStyle, exportAlcance,
      estilosExport, alcanceOpciones, abrirExport, descargarReferencias,
      showCitarTexto, tipoCita, tiposCita, ayudasCita, citaForm, secFuentes,
      resultadoCita, resultadoCita2, citaNecesitaTexto, citaNecesitaFuentes, etiquetaResultado,
      abrirCitarTexto, generarCita, anadirFuente, quitarFuente,
      setFilter, docAuthors, typeLabel,
    }
  },
}

const app = createApp(App)
app.use(PrimeVue.Config, { theme: { preset: PrimeVue.Themes.Aura, options: { darkModeSelector: '.app-dark' } } })
app.use(PrimeVue.ToastService)

// Registro manual de componentes (kebab p-* seguros para compilación en el DOM).
const componentes = {
  'p-button': PrimeVue.Button,
  'p-input-text': PrimeVue.InputText,
  'p-select': PrimeVue.Select,
  'p-dialog': PrimeVue.Dialog,
  'p-data-table': PrimeVue.DataTable,
  'p-column': PrimeVue.Column,
  'p-message': PrimeVue.Message,
  'p-card': PrimeVue.Card,
  'p-toast': PrimeVue.Toast,
}
for (const [nombre, comp] of Object.entries(componentes)) {
  if (comp) app.component(nombre, comp)
}

// Visor de PDF con PDF.js (renderiza cada página en un canvas; robusto y offline).
if (window.pdfjsLib) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.min.js'
}
app.component('pdf-visor', {
  props: { src: String },
  template: '<div class="pdfjs-cont"></div>',
  mounted() {
    this._tarea = 0
    this.render()
  },
  beforeUnmount() {
    this._tarea++ // cancela renders en curso
  },
  watch: {
    src() {
      this.render()
    },
  },
  methods: {
    async render() {
      const cont = this.$el
      const token = ++this._tarea
      if (!this.src) {
        cont.innerHTML = ''
        return
      }
      if (!window.pdfjsLib) {
        cont.innerHTML = '<div class="pdfjs-err">No se pudo iniciar el visor de PDF.</div>'
        return
      }
      cont.innerHTML = '<div class="pdfjs-cargando">Cargando PDF…</div>'
      try {
        // Los blob: (importación) cargan directo; las URLs del backend necesitan el token.
        const params = this.src.startsWith('blob:')
          ? this.src
          : { url: this.src, httpHeaders: { Authorization: 'Bearer ' + getToken() } }
        const pdf = await pdfjsLib.getDocument(params).promise
        if (token !== this._tarea) return
        cont.innerHTML = ''
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i)
          if (token !== this._tarea) return
          const vp = page.getViewport({ scale: 1.4 })
          const canvas = document.createElement('canvas')
          canvas.className = 'pdfjs-page'
          canvas.width = vp.width
          canvas.height = vp.height
          cont.appendChild(canvas)
          await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise
        }
      } catch (e) {
        if (token === this._tarea) {
          cont.innerHTML = '<div class="pdfjs-err">No se pudo cargar el PDF.</div>'
        }
      }
    },
  },
})

app.mount('#app')
