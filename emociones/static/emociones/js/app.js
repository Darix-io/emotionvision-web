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

    let temporizador = null;
    let consultas = 0;

    function post(url) {
        return fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf } });
    }

    function capitalizar(texto) {
        return texto.charAt(0).toUpperCase() + texto.slice(1);
    }

    function pintarEstadoCamara(encendida) {
        insignia.classList.toggle('estado-encendida', encendida);
        insignia.classList.toggle('estado-apagada', !encendida);
        $('estado-texto').textContent = encendida ? 'Cámara encendida' : 'Cámara apagada';
    }

    function pintarPanel(datos) {
        const emocion = $('panel-emocion');
        const relleno = $('barra-relleno');
        const confianza = $('panel-confianza');
        $('panel-rostros').textContent = 'Rostros detectados: ' + (datos ? datos.rostros : 0);

        if (!datos || !datos.activa) {
            emocion.textContent = '—';
            confianza.textContent = 'Confianza: —';
            relleno.style.width = '0';
        } else if (datos.rostros === 0) {
            emocion.textContent = 'Sin rostro detectado';
            confianza.textContent = 'Confianza: —';
            relleno.style.width = '0';
        } else if (datos.emocion) {
            emocion.textContent = capitalizar(datos.emocion);
            confianza.textContent = 'Confianza: ' + datos.confianza + '%';
            relleno.style.width = datos.confianza + '%';
        } else {
            emocion.textContent = 'Rostro detectado';
            confianza.textContent = 'Sin estimación disponible (¿falta el modelo?)';
            relleno.style.width = '0';
        }
    }

    // ----- Estadísticas -----
    function celda(texto, columnas) {
        const td = document.createElement('td');
        td.textContent = texto;  // textContent: nunca se interpreta como HTML
        if (columnas) { td.colSpan = columnas; td.className = 'vacio'; }
        return td;
    }

    function pintarEstadisticas(datos) {
        $('est-aviso').textContent = datos.disponible
            ? '' : 'No se pudo consultar la base de datos. El video sigue funcionando.';
        $('est-total').textContent = datos.total;

        const lista = $('est-por-emocion');
        lista.replaceChildren();
        if (datos.por_emocion.length === 0) {
            const li = document.createElement('li');
            li.className = 'vacio';
            li.textContent = 'Sin registros.';
            lista.appendChild(li);
        }
        datos.por_emocion.forEach((e) => {
            const li = document.createElement('li');
            const nombre = document.createElement('span');
            nombre.textContent = capitalizar(e.emocion);
            const cantidad = document.createElement('strong');
            cantidad.textContent = e.cantidad;
            li.append(nombre, cantidad);
            lista.appendChild(li);
        });

        const cuerpo = $('est-ultimos');
        cuerpo.replaceChildren();
        if (datos.ultimos.length === 0) {
            const tr = document.createElement('tr');
            tr.appendChild(celda('Sin registros.', 4));
            cuerpo.appendChild(tr);
        }
        datos.ultimos.forEach((r) => {
            const tr = document.createElement('tr');
            tr.append(celda(r.fecha), celda(r.hora), celda(capitalizar(r.emocion)),
                      celda(r.confianza + '%'));
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

    function mostrarApagada() {
        clearInterval(temporizador);
        temporizador = null;
        video.removeAttribute('src');
        video.style.display = 'none';
        espera.style.display = 'block';
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
                return;
            }
            mostrarEncendida();
        } catch (e) {
            mensaje.textContent = 'No se pudo comunicar con el servidor.';
            mostrarApagada();
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
        }
    });

    mostrarApagada();
})();
