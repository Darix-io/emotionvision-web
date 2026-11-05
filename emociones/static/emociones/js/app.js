(function () {
    'use strict';

    const app = document.getElementById('app');
    const urls = {
        iniciar: app.dataset.urlIniciar,
        video: app.dataset.urlVideo,
        estado: app.dataset.urlEstado,
        detener: app.dataset.urlDetener,
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
