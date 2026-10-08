# Kitchen Smart Display

Dashboard de cocina en formato *Bento Grid* (diseñado a 1920×1080 y escalado a cualquier resolución, p. ej. 1440×900; legible a 2–3 m) que sustituye a MagicMirror. Diseño original en [SPECIFICATION.md](SPECIFICATION.md); este README describe lo que está implementado.

| Tarjeta | Fuente | Actualización |
|---|---|---|
| Reloj y fecha | Navegador del dispositivo cliente | cada segundo |
| Agenda (hoy + 3 semanas) | Google Calendar (iCal) | 10 min |
| Energía solar | Inversor GoodWe (UDP local) + SEMS+ (nube GoodWe) | 10 s / ~2 min |
| La compra | Google Keep | 5 min |
| El tiempo (una o varias ciudades) | Open-Meteo | 15 min |
| Spotify (solo si suena algo) | Spotify Web API, varias cuentas | 5 s |
| Píldoras NAS / AdGuard | OpenMediaVault, AdGuard Home | 1 min / 5 min |
| Noticias | Feeds RSS/Atom | 30 min |

## Arquitectura

```
Dispositivo cliente (Chromium en modo kiosko)
        │  HTTP + WebSocket  :3080
        ▼
NAS ── contenedor "kitchen-dashboard" (network_mode: host)
        ├── FastAPI: API REST, WebSocket /ws/solar y la web compilada
        └── un poller asíncrono por módulo ──► inversor (UDP 8899), OMV, AdGuard,
                                               Google, Spotify, SEMS+, Open-Meteo, RSS
```

- **Un único contenedor** sirve la web, la API y el WebSocket. El frontend (React + Vite + Tailwind) se compila en una etapa intermedia de la build; la imagen final no lleva Node.
- `network_mode: host` es necesario para el UDP con el inversor y para llegar a OMV/AdGuard por `localhost`.
- **Tolerancia a fallos:** si un servicio no responde, su módulo sigue sirviendo la última lectura válida con `"status": "stale"` y la tarjeta muestra "Sin actualizar". Ningún módulo afecta a los demás.
- El dispositivo cliente no ejecuta lógica: solo abre la web. La página se recarga sola cada día a las 04:00 para recoger nuevas versiones y evitar fugas de memoria del navegador.

## Despliegue en el NAS

La configuración real vive en `config.yaml`, que **no está en el repositorio** (contiene credenciales). Se parte de la plantilla [config.example.yaml](config.example.yaml).

### Con Portainer (stack desde git)

1. **Crea la configuración en el NAS**, en una ruta fija fuera de Portainer, por ejemplo:
   ```bash
   mkdir -p /srv/smartdisplay
   curl -fsSL https://raw.githubusercontent.com/largoguns/smartdisplay/main/config.example.yaml -o /srv/smartdisplay/config.yaml
   chmod 600 /srv/smartdisplay/config.yaml
   nano /srv/smartdisplay/config.yaml        # rellenar (ver "Configuración")
   ```
   El contenedor corre con el usuario UID 1000: si el fichero es de otro usuario, dale lectura (`chown 1000 /srv/smartdisplay/config.yaml`).
2. En Portainer: **Stacks → Add stack → Repository**:
   - Repository URL: `https://github.com/largoguns/smartdisplay`
   - Reference: `refs/heads/main`
   - Compose path: `docker-compose.yml`
   - **Environment variables:** `CONFIG_FILE` = `/srv/smartdisplay/config.yaml`, más los secretos de [Secretos fuera de config.yaml](#secretos-fuera-de-configyaml) (`OMV_PASSWORD`, `ADGUARD_PASSWORD`)
3. **Deploy the stack.** La primera vez construye la imagen (unos minutos).

| Acción | Cómo |
|---|---|
| Aplicar cambios de `config.yaml` | Reiniciar el contenedor `kitchen-dashboard` |
| Cambiar secretos (`OMV_PASSWORD`...) | Editar las variables del stack → **Update the stack** |
| Actualizar a la última versión | En el stack: **Pull and redeploy** (con *Re-pull image and redeploy* activado) |
| Ver logs | Contenedor `kitchen-dashboard` → Logs |

Si `CONFIG_FILE` apunta a un fichero que no existe, Docker crea un **directorio** con ese nombre y el contenedor falla al arrancar: crea el fichero antes del primer despliegue.

### Con docker compose

```bash
git clone https://github.com/largoguns/smartdisplay.git && cd smartdisplay
cp config.example.yaml config.yaml && chmod 600 config.yaml   # y rellenarlo
cp .env.example .env && chmod 600 .env                         # contraseñas de OMV y AdGuard
docker compose up -d --build
```

| Acción | Comando |
|---|---|
| Aplicar cambios de `config.yaml` | `docker compose restart` |
| Aplicar cambios de `.env` | `docker compose up -d` (**no** `restart`: reutiliza las variables antiguas) |
| Actualizar el código | `git pull && docker compose up -d --build` |
| Ver logs | `docker compose logs -f` |

### En ambos casos

El dashboard queda en `http://<IP_NAS>:3080` (`server.port`). No se usa el 3000 porque AdGuard Home lo publica por defecto para su asistente de instalación. Si `server.port` está ocupado, el contenedor lo indica en el log y no arranca: elige otro y actualiza la URL del dispositivo cliente. Estado de cada módulo: `http://<IP_NAS>:3080/api/health`.

## Configuración

Todo está en `config.yaml` (plantilla: [config.example.yaml](config.example.yaml)). Una sección ausente o con `enabled: false` desactiva el módulo y su tarjeta.

### Secretos fuera de config.yaml

Cualquier valor de `config.yaml` puede escribirse como `${VARIABLE}` y se sustituye al arrancar por esa variable de entorno. La plantilla lo usa para las contraseñas de OMV y AdGuard, que sus APIs exigen en claro:

```yaml
omv:
  password: "${OMV_PASSWORD}"
adguard:
  password: "${ADGUARD_PASSWORD}"
```

- **En local:** fichero `.env` junto a `docker-compose.yml` (plantilla en [.env.example](.env.example); está en `.gitignore`).
- **En Portainer:** como *Environment variables* del stack.
- Si una variable no está definida, el arranque lo avisa en el log y solo falla el módulo que la usa.
- Para añadir otra, referénciala en `config.yaml` y añádela a `environment:` en [docker-compose.yml](docker-compose.yml).

### Servidor

```yaml
server:
  port: 3080                  # web + API
  timezone: "Europe/Madrid"   # para calendario y "hoy"
  log_level: "INFO"
```

### Inversor GoodWe (`inverter`)

```yaml
inverter:
  ip_address: "192.168.1.150"
  family: "DT"                # opcional: ET, ES, DT... (sin él, autodetección)
  poll_interval_seconds: 10
```

- Para localizar el inversor en la red: `python3 scripts/goodwe_probe.py` (busca por broadcast y dice qué IP es el inversor y qué datos da). Ver [Scripts](#scripts).
- **Reserva su IP en el DHCP del router**: si cambia, el módulo deja de leerlo.
- Los inversores **DT sin medidor** (como el GW3000D-NS) solo saben la producción: el consumo del hogar y la red se obtienen de SEMS+ (siguiente sección). Sin SEMS la tarjeta muestra "—" y "Sin medidor".

### SEMS+ (`sems`): consumo del hogar y red

Si la instalación tiene un **HomeKit** (medidor de GoodWe), sus mediciones solo se publican en la nube de GoodWe. El módulo `sems` las lee con la misma API que usa la web [semsplus.goodwe.com](https://semsplus.goodwe.com) (**no oficial**: puede romperse si GoodWe la cambia; en ese caso Hogar y Red vuelven a "—" sin afectar al resto).

```yaml
sems:
  enabled: true
  username: "tu_email@ejemplo.com"
  password_hash: "..."        # python3 scripts/sems_hash.py
  station_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # en la URL de tu planta en semsplus.goodwe.com
  poll_interval_seconds: 60
  max_age_minutes: 15         # lecturas más antiguas no se muestran
```

- **No guardes la contraseña:** `scripts/sems_hash.py` genera el hash que envía la web (`base64(md5(contraseña))`). Sigue permitiendo entrar en SEMS, así que protégelo igual (fuera de git, `chmod 600`). También se acepta `password:` en claro, desaconsejado.
- SEMS solo tiene **una lectura nueva cada ~2 minutos**; consultar más a menudo de 30–60 s no da datos más frescos y aumenta el riesgo de que GoodWe limite la cuenta.
- Para comprobar acceso y datos antes de activarlo: `python3 scripts/sems_probe.py <email> <station_id>`.

**Cómo se combinan inversor y SEMS** (la tarjeta indica el origen en su cabecera):

| Situación | Paneles | Hogar | Red | Cabecera |
|---|---|---|---|---|
| Inversor con medidor propio | inversor | inversor | inversor | — |
| Inversor sin medidor + SEMS | inversor (en vivo) | SEMS | **paneles − hogar**, en vivo | "Red estimada · consumo vía SEMS 12:34" |
| Inversor apagado (noche) + SEMS | SEMS | SEMS | SEMS | "Hogar y red vía SEMS 12:34" |
| Inversor sin medidor, sin SEMS | inversor | — | — | — |

En el modo "red estimada" los tres valores siempre cuadran y la red sigue al instante a las nubes; el consumo del hogar se actualiza cuando SEMS publica (~2 min). De noche se conserva la energía generada en el día.

### El tiempo (`weather`)

```yaml
weather:
  update_interval_minutes: 15
  locations:                  # la primera es la principal
    - name: "Casa"
      latitude: 40.4168
      longitude: -3.7038
    - name: "Sevilla"         # las demás: tarjetas compactas debajo
      latitude: 37.3891
      longitude: -5.9845
```

- Coordenadas: clic derecho en Google Maps, o `curl "https://geocoding-api.open-meteo.com/v1/search?name=Sevilla&language=es"`. Basta con las del municipio.
- La tarjeta principal se adapta al alto disponible: si no cabe todo (p. ej. con Spotify sonando), oculta primero la previsión por horas.

### Calendarios (`calendars`)

```yaml
calendars:
  update_interval_minutes: 10
  days_ahead: 21              # hoy + 3 semanas
  sources:
    - name: "Personal"
      color: "#38bdf8"
      ics_url: "https://calendar.google.com/calendar/ical/.../basic.ics"
```

- URL: Google Calendar → Configuración del calendario → **"Dirección secreta en formato iCal"**. Da acceso de lectura a todo el calendario: no la compartas. Si se filtra, "Restablecer" la invalida.
- Se expanden los eventos recurrentes y se omiten los cancelados y los ya terminados.

### Lista de la compra (`keep`)

```yaml
keep:
  username: "tu_cuenta@gmail.com"
  master_token: "aas_et/..."
  target_list_title: "La Compra"   # sin distinguir mayúsculas
  completed_items_shown: 0         # elementos marcados a mostrar (0 = solo pendientes)
  poll_interval_seconds: 300
```

- **Master token:** abre <https://accounts.google.com/EmbeddedSetup>, inicia sesión y acepta; en DevTools → Application → Cookies copia `oauth_token` (caduca en minutos) y ejecuta:
  ```bash
  docker compose run --rm -it -v "$PWD/scripts:/scripts:ro" dashboard python /scripts/keep_token.py
  ```
  El token equivale a una contraseña de la cuenta de Google y no caduca solo; se revoca cambiando la contraseña o quitando el dispositivo en myaccount.google.com → Seguridad.
- Si hay varias listas con el mismo título, se usa la no archivada y más reciente.

### Spotify (`spotify`)

1. En <https://developer.spotify.com/dashboard> → **Create app**, API "Web API", Redirect URI `http://127.0.0.1:8888/callback` (Spotify no admite `localhost`).
2. En **User Management** añade el nombre y email de cada cuenta a mostrar (en *Development mode* las demás se rechazan con 403).
3. Por cada cuenta, abre la URL que imprime el script e inicia sesión (la segunda en una ventana de incógnito):
   ```bash
   python3 scripts/spotify_auth.py <client_id> <client_secret>
   # si el 8888 está ocupado: --port 8889 (y añade ese Redirect URI en Spotify)
   ```
4. Configura:
   ```yaml
   spotify:
     client_id: "..."
     client_secret: "..."
     accounts:
       - name: "Cuenta 1"         # nombre visible en la tarjeta
         refresh_token: "..."
     preferred_devices:            # desempate si suenan varias cuentas
       - "Google Home Cocina"
   ```

Si suena una sola cuenta se muestra esa; si suenan varias, la que use un dispositivo de `preferred_devices` (por orden). Sin reproducción la tarjeta se oculta y el espacio pasa a El tiempo.

### Anime (`anime`)

```yaml
anime:
  url: "http://<IP>:8888/anime"
  poll_interval_seconds: 1800
```

Llama a `POST <url>/api/tracking/refresh` de la app de seguimiento y muestra, en una franja sobre las noticias, cada serie con capítulos nuevos (`new_count > 0`) y cuántos tiene. Sin capítulos nuevos la franja se oculta. Las carátulas se cargan desde la web de origen.

### NAS y AdGuard (`omv`, `adguard`)

```yaml
omv:
  url: "http://<IP_NAS>:80"
  username: "admin"
  password: "${OMV_PASSWORD}"
  exclude_mount_points: ["/", "/boot", "/boot/efi"]
adguard:
  url: "http://<IP_NAS>:<puerto_web_adguard>"
  username: "dashboard"
  password: "${ADGUARD_PASSWORD}"
```

- Con la IP del NAS la misma configuración sirve en local y desplegada. Para encontrar el puerto web de AdGuard: su API responde `401` en `http://<host>:<puerto>/control/status`.
- La píldora del NAS se pone en ámbar con algún disco ≥ 90 % o la RAM ≥ 95 %.

**Usuario dedicado para AdGuard.** Así la contraseña que usa el dashboard no es la tuya. AdGuard no tiene usuarios de solo lectura (todos son administradores), pero si esta se filtra basta con borrar el usuario.

1. Genera una contraseña aleatoria y su hash bcrypt:
   ```bash
   PASS=$(openssl rand -base64 24); echo "$PASS"     # va a ADGUARD_PASSWORD
   docker run --rm httpd:alpine htpasswd -nbB dashboard "$PASS" | cut -d: -f2
   ```
2. Para AdGuard Home y edita su `AdGuardHome.yaml` (en Docker, en el volumen de `conf/`). Añade el usuario a la lista existente:
   ```yaml
   users:
     - name: admin            # el tuyo, sin tocar
       password: $2y$...
     - name: dashboard
       password: $2y$...      # el hash del paso 1
   ```
3. Arranca AdGuard y pon la contraseña del paso 1 en `ADGUARD_PASSWORD`.

### Noticias (`news`)

```yaml
news:
  update_interval_minutes: 30
  ticker_speed_seconds: 15        # tiempo por titular
  feeds:
    - name: "Xataka"
      url: "https://feeds.weblogssl.com/xataka2"
```

## Dispositivo cliente (pantalla de la cocina)

Cualquier equipo con Chromium y una pantalla sirve; lo habitual es una Raspberry Pi con Raspberry Pi OS **con escritorio**. El navegador se abre en **modo kiosko**: pantalla completa, sin barras ni diálogos. La página ya oculta el cursor y las barras de desplazamiento.

### 1. Preparar el sistema

```bash
sudo raspi-config
```

- **System Options → Boot / Auto Login → Desktop Autologin**: arranca directamente en el escritorio sin pedir usuario.
- **Display Options → Screen Blanking → No**: la pantalla no se apaga sola.
- Opcional: **Display Options → Resolution** si el monitor no se detecta a 1920×1080.

Paquetes (Chromium suele venir instalado; `unclutter` solo hace falta en X11):

```bash
sudo apt update && sudo apt install -y chromium-browser unclutter curl
```

En versiones recientes del sistema el paquete se llama `chromium`; el script detecta ambos.

### 2. Instalar el script de arranque

Desde el equipo con el repositorio:

```bash
scp scripts/rpi-kiosk.sh <usuario>@<IP_CLIENTE>:~/start-kiosk.sh
ssh <usuario>@<IP_CLIENTE> 'chmod +x ~/start-kiosk.sh'
```

El script desactiva el salvapantallas (X11), oculta el cursor, evita el aviso "Chromium no se cerró correctamente", **espera a que el NAS responda** (útil tras un corte de luz, si la pantalla arranca antes que el NAS) y abre Chromium en modo kiosko. Acepta la URL como argumento o en la variable `DASHBOARD_URL`.

Pruébalo a mano desde una terminal del escritorio del cliente:

```bash
~/start-kiosk.sh http://<IP_NAS>:3080
```

Para salir del modo kiosko: <kbd>Alt</kbd>+<kbd>F4</kbd>.

### 3. Arranque automático

Depende del entorno gráfico. Para saber cuál usas: `echo $XDG_SESSION_TYPE` (`wayland` o `x11`) y, en Wayland, `ps -e | grep -E "labwc|wayfire"`.

| Entorno | Fichero | Línea a añadir |
|---|---|---|
| Wayland con **labwc** (por defecto en las versiones actuales) | `~/.config/labwc/autostart` | `~/start-kiosk.sh http://<IP_NAS>:3080 &` |
| Wayland con **wayfire** | `~/.config/wayfire.ini`, sección `[autostart]` | `kiosk = ~/start-kiosk.sh http://<IP_NAS>:3080` |
| **X11** (LXDE) | `~/.config/lxsession/LXDE-pi/autostart` | `@/home/<usuario>/start-kiosk.sh http://<IP_NAS>:3080` |

Crea el fichero o la sección si no existe y reinicia (`sudo reboot`) para comprobarlo. Con labwc, un `~/.config/labwc/autostart` propio sustituye al del sistema, así que el escritorio arranca sin panel ni iconos: es lo deseable en un kiosko.

### 4. Opcional: apagar la pantalla por la noche

Con `crontab -e` en el cliente (ajusta las horas). Para el nombre de la salida en Wayland, ejecuta `wlr-randr` (suele ser `HDMI-A-1`):

```cron
# Wayland
0 0 * * *  WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 wlr-randr --output HDMI-A-1 --off
0 7 * * *  WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 wlr-randr --output HDMI-A-1 --on
# X11
0 0 * * *  DISPLAY=:0 xset dpms force off
0 7 * * *  DISPLAY=:0 xset dpms force on
```

### Requisitos de red del cliente

Solo necesita llegar a `http://<IP_NAS>:3080`. Las carátulas de Spotify se cargan desde internet (`i.scdn.co`); el resto de datos pasa por el NAS.

## API

| Endpoint | Contenido |
|---|---|
| `GET /api/health` | Estado, última lectura correcta y último error de cada módulo |
| `GET /api/solar/current` · `WS /ws/solar` | Energía (el WebSocket emite cada lectura) |
| `GET /api/calendar` | Eventos de hoy + `days_ahead` días |
| `GET /api/weather` · `/api/weather/{n}` · `/api/weather/locations` | Tiempo de la ubicación principal / de la n-ésima / lista de ubicaciones |
| `GET /api/keep/shopping-list` | Lista de la compra |
| `GET /api/media/now-playing` | Spotify |
| `GET /api/system/nas` · `GET /api/network/adguard` | NAS y AdGuard |
| `GET /api/news` | Titulares |
| `GET /api/anime` | Series de anime con capítulos nuevos |

Respuestas: `200` con `"status": "ok"` o `"stale"`; `503` si el módulo aún no tiene datos; `404` si está desactivado.

## Scripts

| Script | Para qué | Cómo se ejecuta |
|---|---|---|
| `.env.example` | Plantilla de los secretos por variable de entorno | `cp .env.example .env` |
| `scripts/rpi-kiosk.sh` | Arranque del dispositivo cliente en modo kiosko | en el cliente |
| `scripts/goodwe_probe.py` | Localizar el inversor y ver qué datos expone | `docker compose run --rm -v "$PWD/scripts:/scripts:ro" dashboard python /scripts/goodwe_probe.py [IP ...]` |
| `scripts/sems_hash.py` | Hash de la contraseña de SEMS para `password_hash` | `python3 scripts/sems_hash.py` |
| `scripts/sems_probe.py` | Probar login y flujo de energía de SEMS+ | `python3 scripts/sems_probe.py <email> <station_id>` |
| `scripts/keep_token.py` | Master token de Google Keep | `docker compose run --rm -it -v "$PWD/scripts:/scripts:ro" dashboard python /scripts/keep_token.py` |
| `scripts/spotify_auth.py` | Refresh token de cada cuenta de Spotify | `python3 scripts/spotify_auth.py <id> <secret> [--port N]` |

Los que se ejecutan con `python3` solo usan la librería estándar; los que van por `docker compose run` necesitan las librerías de la imagen. Los que piden contraseñas o cookies las leen ocultas y no las guardan.

## Seguridad

`config.yaml` contiene credenciales: URLs secretas de calendario, master token de Google, hash de SEMS y tokens de Spotify. Las contraseñas de OMV y AdGuard van aparte, en variables de entorno (`.env` o el stack de Portainer).

- Está en `.gitignore`: **nunca lo subas al repositorio** (es público). Déjalo con `chmod 600`.
- Está montado en el contenedor en solo lectura.
- El dashboard no tiene autenticación: cualquiera en la LAN puede verlo. No expongas el puerto a internet.

## Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| Módulo con `401`/"Incorrect username or password" tras editar `.env` | Se usó `docker compose restart`: las variables no se releen. Usa `docker compose up -d`. |
| `502`/página en blanco justo tras reiniciar | El backend tarda unos segundos en arrancar; las tarjetas reintentan cada 5 s. |
| El contenedor no arranca ("No se puede escuchar en …") | Otro servicio usa `server.port`. Para ver cuál: `ss -ltnp \| grep ':<puerto> '` (si es `docker-proxy`, `docker ps --format '{{.Names}} {{.Ports}}' \| grep ':<puerto>'`). |
| Energía solar "Sin actualizar" | Inversor apagado (de noche sin SEMS), IP cambiada, o el equipo que ejecuta el contenedor no llega a la LAN (p. ej. una VPN corporativa que enruta esa subred). |
| Hogar y Red con "—" | Inversor sin medidor y SEMS desactivado o con lecturas de más de `max_age_minutes`. |
| La compra muestra otra lista | Hay varias con el mismo título; se usa la no archivada y más reciente. Renombra o borra las antiguas. |
| Spotify `400`/`403` | Refresh token inválido (`400`) o la cuenta no está en *User Management* (`403`). |
| `spotify_auth.py`: puerto ocupado | Usa `--port` con otro libre y añade su Redirect URI en Spotify. |

## Desarrollo

Normas de contribución y formato de commits (Conventional Commits): [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
# Backend (escucha en server.port)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
CONFIG_PATH=../config.yaml STATIC_DIR=../frontend/dist .venv/bin/python -m app.main
.venv/bin/pytest

# Frontend con recarga en caliente en :5173 (proxy de /api y /ws hacia localhost:3080)
cd frontend && npm install && npm run dev
```

Estructura:

```
backend/app/
  main.py            API, WebSocket y servido de la web
  config.py          modelos de config.yaml
  modules/           un poller por servicio (base.py: reintentos y "stale")
  schemas/models.py  modelos Pydantic de las respuestas
frontend/src/
  App.tsx            layout del grid
  components/        una tarjeta por fichero
  hooks/             polling, WebSocket solar, medida de alto
scripts/             utilidades de configuración y el arranque del cliente
```
