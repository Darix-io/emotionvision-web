(function () {
    'use strict';

    const app = document.getElementById('app');
    const urls = {
        iniciar: app.dataset.urlIniciar,
        video: app.dataset.urlVideo,
        estado: app.dataset.urlEstado,
        detener: app.dataset.urlDetener,
        estadisticas: app.dataset.urlEstadisticas,
        borrar: app.dataset.urlBorrar,
    };
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;

    const $ = (id) => document.getElementById(id);
    const video = $('video');
    const espera = $('espera');
    const mensaje = $('mensaje');
    const btnIniciar = $('btn-iniciar');
    const btnDetener = $('btn-detener');
    const dialogo = $('dlg-privacidad');
    const insignia = $('estado-camara');

    // Emoji por emoción (solo presentación). Son emojis del sistema: no se carga nada de internet.
    const EMOJIS = {
        neutral: '😐', feliz: '😄', sorpresa: '😮', tristeza: '😢',
        enojo: '😠', asco: '🤢', miedo: '😨', desprecio: '😏',
    };
    const EMOJI_APAGADA = '😴';
    const EMOJI_SIN_ROSTRO = '🔎';
    const EMOJI_SIN_ESTIMACION = '🙂';

    let temporizador = null;
    let consultas = 0;
    let ultimoAnuncio = '';
    let ultimoEmoji = '';
    let firmaEstadisticas = '';

    function post(url) {
        return fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf } });
    }

    function capitalizar(texto) {
        return texto.charAt(0).toUpperCase() + texto.slice(1);
    }

    function emojiDe(emocion) {
        return EMOJIS[emocion] || EMOJI_SIN_ESTIMACION;
    }

    // Lectores de pantalla: solo se avisa cuando algo cambia (no cada 0,5 s).
    function anunciar(texto) {
        if (texto === ultimoAnuncio) return;
        ultimoAnuncio = texto;
        $('anuncio').textContent = texto;
    }

    function pintarEstadoCamara(encendida) {
        insignia.classList.toggle('estado-encendida', encendida);
        insignia.classList.toggle('estado-apagada', !encendida);
        $('estado-texto').textContent = encendida ? 'Cámara encendida' : 'Cámara apagada';
    }

    // ----- Panel de emoción actual -----
    function pintarPanel(datos) {
        const barra = $('barra');
        const relleno = $('barra-relleno');
        const confianza = $('panel-confianza');
        const rostros = datos ? datos.rostros : 0;
        let emoji, titulo, porcentaje = null, nota = '';

        if (!datos || !datos.activa) {
            emoji = EMOJI_APAGADA;
            titulo = '—';
        } else if (datos.rostros === 0) {
            emoji = EMOJI_SIN_ROSTRO;
            titulo = 'Sin rostro detectado';
        } else if (datos.emocion) {
            emoji = emojiDe(datos.emocion);
            titulo = capitalizar(datos.emocion);
            porcentaje = datos.confianza;
        } else {
            emoji = EMOJI_SIN_ESTIMACION;
            titulo = 'Rostro detectado';
            nota = ' · sin estimación disponible (¿falta el modelo?)';
        }

        const nodoEmoji = $('panel-emoji');
        if (emoji !== ultimoEmoji) {
            nodoEmoji.textContent = emoji;
            nodoEmoji.classList.remove('cambio');
            void nodoEmoji.offsetWidth;  // reinicia la animación
            nodoEmoji.classList.add('cambio');
            ultimoEmoji = emoji;
        }
        $('panel-emocion').textContent = titulo;
        $('panel-rostros').textContent = 'Rostros detectados: ' + rostros + nota;

        if (porcentaje === null) {
            confianza.textContent = '—';
            relleno.style.width = '0';
            barra.removeAttribute('aria-valuenow');
            barra.setAttribute('aria-valuetext', 'Sin dato');
        } else {
            confianza.textContent = porcentaje + '%';
            relleno.style.width = porcentaje + '%';
            barra.setAttribute('aria-valuenow', porcentaje);
            barra.setAttribute('aria-valuetext', porcentaje + '%');
        }

        anunciar(!datos || !datos.activa ? '' : titulo + (porcentaje === null ? '' : ', ' + porcentaje + '%'));
    }

    // ----- Estadísticas -----
    function celda(texto, columnas) {
        const td = document.createElement('td');
        td.textContent = texto;  // textContent: nunca se interpreta como HTML
        if (columnas) { td.colSpan = columnas; td.className = 'vacio'; }
        return td;
    }

    function celdaEmocion(emocion) {
        const td = document.createElement('td');
        const icono = document.createElement('span');
        icono.className = 'emoji';
        icono.setAttribute('aria-hidden', 'true');
        icono.textContent = emojiDe(emocion);
        td.append(icono, document.createTextNode(capitalizar(emocion)));
        return td;
    }

    function celdaConfianza(porcentaje) {
        const td = document.createElement('td');
        const pastilla = document.createElement('span');
        pastilla.className = 'pastilla';
        pastilla.textContent = porcentaje + '%';
        td.appendChild(pastilla);
        return td;
    }

    function filaBarra(e) {
        const li = document.createElement('li');
        li.className = 'barra-fila';
        li.dataset.emocion = e.emocion;

        const nombre = document.createElement('span');
        nombre.className = 'barra-nombre';
        const icono = document.createElement('span');
        icono.className = 'emoji';
        icono.setAttribute('aria-hidden', 'true');
        icono.textContent = emojiDe(e.emocion);
        nombre.append(icono, document.createTextNode(capitalizar(e.emocion)));

        const pista = document.createElement('span');
        pista.className = 'barra-pista';
        pista.setAttribute('aria-hidden', 'true');
        const valor = document.createElement('span');
        valor.className = 'barra-valor';
        valor.style.width = '0';
        pista.appendChild(valor);

        const cifra = document.createElement('span');
        cifra.className = 'barra-cifra';
        cifra.append(document.createElement('strong'), document.createElement('small'));

        li.append(nombre, pista, cifra);
        return li;
    }

    function actualizarFilaBarra(li, e, maximo, total) {
        li.querySelector('.barra-valor').style.width = Math.round((e.cantidad / maximo) * 100) + '%';
        li.querySelector('strong').textContent = e.cantidad;
        li.querySelector('small').textContent = Math.round((e.cantidad / total) * 100) + '%';
    }

    function pintarBarras(datos) {
        const lista = $('est-por-emocion');
        const claves = datos.por_emocion.map((e) => e.emocion).join();
        const actuales = Array.from(lista.querySelectorAll('.barra-fila')).map((li) => li.dataset.emocion).join();

        if (datos.por_emocion.length === 0) {
            const li = document.createElement('li');
            li.className = 'vacio';
            li.textContent = 'Sin registros.';
            lista.replaceChildren(li);
            return;
        }

        const maximo = Math.max(...datos.por_emocion.map((e) => e.cantidad));
        if (claves !== actuales) {
            // Cambió el orden o las emociones: se rehacen las filas (y las barras crecen con animación).
            const filas = datos.por_emocion.map(filaBarra);
            lista.replaceChildren(...filas);
            requestAnimationFrame(() => requestAnimationFrame(() => {
                filas.forEach((li, i) => actualizarFilaBarra(li, datos.por_emocion[i], maximo, datos.total));
            }));
        } else {
            // Mismo orden: se actualiza en el lugar para que las barras se muevan suavemente.
            lista.querySelectorAll('.barra-fila').forEach((li, i) => {
                actualizarFilaBarra(li, datos.por_emocion[i], maximo, datos.total);
            });
        }
    }

    function pintarEstadisticas(datos) {
        $('est-aviso').textContent = datos.disponible
            ? '' : 'No se pudo consultar la base de datos. El video sigue funcionando.';

        // Si nada cambió, no se toca la página (evita parpadeos y avisos repetidos).
        const firma = JSON.stringify(datos);
        if (firma === firmaEstadisticas) return;
        firmaEstadisticas = firma;

        $('est-total').textContent = datos.total;
        pintarBarras(datos);

        const cuerpo = $('est-ultimos');
        cuerpo.replaceChildren();
        if (datos.ultimos.length === 0) {
            const tr = document.createElement('tr');
            tr.appendChild(celda('Sin registros.', 4));
            cuerpo.appendChild(tr);
        }
        datos.ultimos.forEach((r) => {
            const tr = document.createElement('tr');
            tr.append(celda(r.fecha), celda(r.hora), celdaEmocion(r.emocion), celdaConfianza(r.confianza));
            cuerpo.appendChild(tr);
        });
    }

    async function cargarEstadisticas() {
        try {
            const resp = await fetch(urls.estadisticas, { cache: 'no-store' });
            pintarEstadisticas(await resp.json());
        } catch (e) {
            $('est-aviso').textContent = 'No se pudieron cargar las estadísticas.';
        }
    }

    $('btn-borrar').addEventListener('click', async () => {
        if (!window.confirm('¿Borrar todos los registros guardados? Esta acción no se puede deshacer.')) {
            return;
        }
        try {
            const resp = await post(urls.borrar);
            if (!resp.ok) {
                $('est-aviso').textContent = 'No se pudieron borrar los registros.';
                return;
            }
        } catch (e) {
            $('est-aviso').textContent = 'No se pudo comunicar con el servidor.';
            return;
        }
        cargarEstadisticas();
    });

    // ----- Cámara -----
    function mostrarApagada() {
        clearInterval(temporizador);
        temporizador = null;
        video.removeAttribute('src');
        video.style.display = 'none';
        espera.style.display = 'flex';
        btnIniciar.disabled = false;
        btnDetener.disabled = true;
        pintarEstadoCamara(false);
        pintarPanel(null);
        cargarEstadisticas();
    }

    function mostrarEncendida() {
        // El número evita que el navegador reutilice una conexión vieja.
        video.src = urls.video + '?t=' + Date.now();
        video.style.display = 'block';
        espera.style.display = 'none';
        btnIniciar.disabled = true;
        btnDetener.disabled = false;
        pintarEstadoCamara(true);
        temporizador = setInterval(consultarEstado, 500);
    }

    async function consultarEstado() {
        try {
            const resp = await fetch(urls.estado, { cache: 'no-store' });
            const datos = await resp.json();
            if (!datos.activa) {
                // El servidor cerró la cámara (por ejemplo, se perdió la conexión).
                mostrarApagada();
                return;
            }
            pintarPanel(datos);
            consultas += 1;
            if (consultas % 4 === 0) cargarEstadisticas();  // cada ~2 s
        } catch (e) {
            /* un fallo puntual no detiene el video */
        }
    }

    async function encenderCamara() {
        mensaje.textContent = '';
        btnIniciar.disabled = true;
        try {
            const resp = await post(urls.iniciar);
            const datos = await resp.json();
            if (!resp.ok || !datos.ok) {
                mensaje.textContent = datos.mensaje || 'No se pudo iniciar la cámara.';
                mostrarApagada();
                btnIniciar.focus();
                return;
            }
            mostrarEncendida();
            btnDetener.focus();  // el foco pasa al botón que ahora se puede usar
        } catch (e) {
            mensaje.textContent = 'No se pudo comunicar con el servidor.';
            mostrarApagada();
            btnIniciar.focus();
        }
    }

    // Primero se muestra el aviso de privacidad; la cámara se enciende solo al aceptar.
    btnIniciar.addEventListener('click', () => dialogo.showModal());
    $('dlg-cancelar').addEventListener('click', () => dialogo.close());
    $('dlg-aceptar').addEventListener('click', () => {
        dialogo.close();
        encenderCamara();
    });

    btnDetener.addEventListener('click', async () => {
        video.removeAttribute('src');
        try {
            await post(urls.detener);
        } finally {
            mostrarApagada();
            btnIniciar.focus();
        }
    });

    mostrarApagada();
})();
