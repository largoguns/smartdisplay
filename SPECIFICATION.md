# Especificación Técnica: Kitchen Smart Display Dashboard

## 1. Resumen del Proyecto y Objetivos

El proyecto consiste en una aplicación web tipo *smart display* diseñada para reemplazar una instalación existente de **MagicMirror** en un monitor de cocina convencional.

A diferencia del concepto tradicional de espejo (fondo negro absoluto `#000000` y tipografía blanca de alto contraste), el diseño adopta una estética moderna basada en un **Bento Grid** responsivo con paleta de tonos oscuros suaves (*Slate/Zinc* `#020617` / `#0f172a`), desenfoques translúcidos (*glassmorphism* tenue), acentos de color dinámicos según el estado de cada servicio y una tipografía optimizada para lectura a media distancia (2 a 3 metros).

### Topología de Despliegue

* **Servidor de Aplicación (NAS Local con OpenMediaVault):** Orquestación vía `docker-compose`. Aloja:
  * El **backend** (FastAPI + Python 3.11 en bucles asíncronos), configurado con `network_mode: host` para interactuar sin impedimentos con servicios LAN (UDP GoodWe, RPC OMV, API AdGuard).
  * El **frontend** (SPA React servido mediante Nginx, exponiendo el puerto `3000` y actuando como reverse proxy hacia el backend).
* **Cliente Pantalla (Raspberry Pi existente):** Actúa exclusivamente como cliente ligero en modo kiosko. Inicia Chromium en pantalla completa apuntando a `http://<IP_NAS>:3000` sin ejecutar lógica de backend ni requerir almacenamiento persistente.
* **Hardware y Servicios Locales:**
  * Inversor solar fotovoltaico **GoodWe** accesible por UDP directo en LAN.
  * Servidor **OpenMediaVault (OMV)** para monitorización de hardware/almacenamiento.
  * Instancia local de **AdGuard Home** para métricas de red y filtrado DNS.
  * 3 altavoces **Google Home** que reproducen Spotify desde múltiples cuentas.

---

## 2. Diagrama de Arquitectura de Red

```
                                      RED LOCAL (LAN)
 ┌───────────────────────────────────────────────────────────────────────────────────┐
 │                                                                                   │
 │  ┌───────────────────────────── NAS Local (OMV) ───────────────────────────────┐  │
 │  │                                                                             │  │
 │  │   ┌───────────────────────────┐          ┌──────────────────────────────┐   │  │
 │  │   │  frontend (Docker)        │          │  backend (Docker)            │   │  │
 │  │   │  Nginx + React Vite SPA   │          │  FastAPI + Asyncio           │   │  │
 │  │   │  Puerto: 3000             │          │  network_mode: host          │   │  │
 │  │   │                           │          │  Puerto: 8000                │   │  │
 │  │   │  - /     -> SPA Build     │          │  - REST API Hub              │   │  │
 │  │   │  - /api/ -> Proxy Backend │─────────>│  - WebSockets (/ws/solar)    │   │  │
 │  │   │  - /ws/  -> Proxy WS      │          └──────┬───────────┬──────────┘   │  │
 │  │   └─────────────▲─────────────┘                 │           │              │  │
 │  │                 │                               │           │              │  │
 │  │                 │                               │ JSON-RPC  │ REST         │  │
 │  │                 │                               ▼           ▼              │  │
 │  │                 │                        ┌────────────┐ ┌───────────────┐  │  │
 │  │                 │                        │ OMV Core   │ │ AdGuard Home  │  │  │
 │  │                 │                        │ :80 /rpc   │ │ :3000 /control│  │  │
 │  │                 │                        └────────────┘ └───────────────┘  │  │
 │  └─────────────────┼───────────────────────────────────────────────────────────┘  │
 │                    │ HTTP (:3000)                                                 │
 │                    │                                                              │
 │  ┌─────────────────┴─────────────┐         ┌───────────────────────────────┐      │
 │  │ Raspberry Pi (Pantalla)       │         │ Inversor GoodWe (LAN)         │      │
 │  │ Chromium Kiosk Mode           │         │ Puerto UDP :8899              │      │
 │  └───────────────────────────────┘         └───────────────────────────────┘      │
 │                                                                                   │
 └───────────────────────────────────────┬───────────────────────────────────────────┘
                                         │ HTTPS (Internet)
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │ Servicios Externos / Cloud:                    │
                 │ - Open-Meteo API (Meteorología sin API key)    │
                 │ - Google Calendar (.ics públicos/privados)     │
                 │ - Google Keep API (Lista "La Compra")          │
                 │ - Spotify Web API (Polling dual-account)       │
                 │ - Feeds RSS/Atom de noticias                   │
                 └────────────────────────────────────────────────┘
```

---

## 3. Estructura de Directorios del Proyecto

```
kitchen-dashboard/
├── docker-compose.yml
├── config.yaml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── modules/
│       │   ├── __init__.py
│       │   ├── solar.py        # Conexión UDP local con inversor GoodWe
│       │   ├── calendar.py     # Parser iCalendar con eventos recurrentes
│       │   ├── weather.py      # Cliente Open-Meteo
│       │   ├── news.py         # Parser RSS/Atom
│       │   ├── keep.py         # Sincronización Google Keep ("La Compra")
│       │   ├── nas.py          # Cliente JSON-RPC OpenMediaVault
│       │   ├── adguard.py      # Cliente API AdGuard Home
│       │   └── spotify.py      # Gestor dual-account Spotify
│       └── schemas/
│           ├── __init__.py
│           └── models.py       # Modelos Pydantic v2
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── ClockWidget.tsx
│       │   ├── SolarFlowWidget.tsx
│       │   ├── WeatherWidget.tsx
│       │   ├── CalendarWidget.tsx
│       │   ├── KeepShoppingWidget.tsx
│       │   ├── SpotifyNowPlaying.tsx
│       │   ├── SystemPills.tsx       # Mini badges de OMV y AdGuard
│       │   └── NewsTicker.tsx
│       ├── hooks/
│       │   └── useSolarSocket.ts
│       └── types/
│           └── dashboard.ts
└── scripts/
    └── rpi-kiosk.sh            # Script de arranque Chromium para la Raspberry Pi
```

---

## 4. Configuración Centralizada (`config.yaml`)

El backend lee toda la configuración de un archivo unificado:

```yaml
server:
  host: "0.0.0.0"
  port: 8000

# 1. Inversor Fotovoltaico GoodWe
inverter:
  enabled: true
  ip_address: "192.168.1.150"     # IP LAN del GoodWe
  poll_interval_seconds: 10       # Sondeo UDP

# 2. Información Meteorológica (Open-Meteo)
weather:
  enabled: true
  latitude: 40.4168               # Coordenadas locales
  longitude: -3.7038
  update_interval_minutes: 15

# 3. Calendarios de Google (iCal URLs)
calendars:
  enabled: true
  update_interval_minutes: 10
  sources:
    - name: "Personal"
      color: "#38bdf8"
      ics_url: "https://calendar.google.com/calendar/ical/.../basic.ics"
    - name: "Familia"
      color: "#34d399"
      ics_url: "https://calendar.google.com/calendar/ical/.../basic.ics"

# 4. Lista de la Compra (Google Keep)
keep:
  enabled: true
  username: "usuario@gmail.com"
  password: "app_specific_password_o_master_token"
  target_list_title: "La Compra"
  poll_interval_seconds: 300

# 5. Monitorización del NAS (OpenMediaVault)
omv:
  enabled: true
  url: "http://127.0.0.1:80"       # Si corre en host mode, o IP del NAS
  username: "admin"
  password: "omv_admin_password"
  poll_interval_seconds: 60

# 6. Seguridad y DNS (AdGuard Home)
adguard:
  enabled: true
  url: "http://127.0.0.1:3000"     # URL y puerto web de AdGuard
  username: "admin"
  password: "adguard_password"
  poll_interval_seconds: 300

# 7. Spotify Doméstico (Soporte Multi-Cuenta)
spotify:
  enabled: true
  client_id: "TU_SPOTIFY_CLIENT_ID"
  client_secret: "TU_SPOTIFY_CLIENT_SECRET"
  poll_interval_seconds: 5
  accounts:
    - name: "Cuenta 1"
      refresh_token: "REFRESH_TOKEN_CUENTA_1"
    - name: "Cuenta 2"
      refresh_token: "REFRESH_TOKEN_CUENTA_2"
  preferred_devices:
    - "Google Home Cocina"
    - "Google Home Salon"
    - "Google Home Pasillo"

# 8. Noticias RSS/Atom
news:
  enabled: true
  update_interval_minutes: 30
  ticker_speed_seconds: 15
  feeds:
    - name: "El País"
      url: "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"
    - name: "Xataka"
      url: "https://feeds.weblogssl.com/xataka2"
```

---

## 5. Especificación de Módulos (Backend)

### 5.1. Módulo Solar: GoodWe Inverter
* **Dependencia:** `goodwe>=0.2.14`
* **Mecanismo:** Tarea asíncrona de fondo que conecta vía UDP al inversor.
* **Procesamiento de Métricas:**
  * `ppv`: Potencia fotovoltaica instantánea ($W$).
  * `house_consumption`: Potencia demandada por el hogar ($W$).
  * `active_power`: Flujo de red ($W$, positivo = inyección a red, negativo = consumo de red).
  * `battery_power` y `battery_soc`: Si el inversor cuenta con almacenamiento conectado.
  * `today_energy_kwh`: Producción acumulada en el día ($kWh$).
* **Entrega:** WebSockets en `/ws/solar` con cada actualización y fallback REST en `GET /api/solar/current`.

### 5.2. Módulo de Calendarios (Google Calendar)
* **Dependencias:** `httpx`, `icalendar`, `recurring-ical-events`
* **Mecanismo:** Descarga periódica de feeds `.ics` y cálculo de ocurrencias de eventos desde `hoy 00:00:00` hasta `hoy + 7 días 23:59:59`.
* **Endpoint:** `GET /api/calendar`
* **Formato:** Array ordenado cronológicamente con flags `is_ongoing` y `is_all_day`.

### 5.3. Módulo Meteorológico (Open-Meteo)
* **Dependencia:** `httpx`
* **Mecanismo:** Consulta REST a Open-Meteo (sin clave API).
* **Endpoint:** `GET /api/weather`
* **Contenido:**
  * Temperatura actual, sensación térmica, humedad relativa, velocidad de viento y código meteorológico WMO.
  * Pronóstico horario (próximas 12 horas).
  * Pronóstico diario (próximos 5 días: mín/máx y código WMO).

### 5.4. Módulo Lista de la Compra (Google Keep)
* **Dependencia:** `gkeepapi`
* **Mecanismo:** 
  * Se conecta usando credenciales con token específico.
  * Busca la lista cuyo título sea idéntico a `config.keep.target_list_title` ("La Compra").
  * Retorna los elementos pendientes (`completed = false`) y los últimos 3 completados.
* **Endpoint:** `GET /api/keep/shopping-list`
* **Salida JSON:**
  ```json
  {
    "title": "La Compra",
    "updated_at": "2026-10-06T08:30:00Z",
    "items": [
      { "id": "k1", "text": "Leche entera", "completed": false },
      { "id": "k2", "text": "Café en grano", "completed": false },
      { "id": "k3", "text": "Aceite de oliva", "completed": true }
    ]
  }
  ```

### 5.5. Módulo Estado del NAS (OpenMediaVault)
* **Dependencia:** `httpx`
* **Mecanismo:** Cliente JSON-RPC contra el endpoint `/rpc.php` de OMV.
  1. `Session::login` (almacena cookie de sesión `OpenMediaVault-SessionId`).
  2. `System::getInformation` para uso de CPU, RAM total/usada y uptime.
  3. `FileSystemMgmt::getList` para volúmenes montados (capacidad total, usada y porcentaje).
* **Endpoint:** `GET /api/system/nas`
* **Salida JSON:**
  ```json
  {
    "status": "healthy",
    "cpu": { "usage_percent": 18.5 },
    "memory": { "total_gb": 16.0, "used_gb": 5.2, "percent": 32.5 },
    "storage": [
      {
        "mount_point": "/srv/dev-disk-by-uuid-data",
        "label": "Data Pool",
        "total_gb": 7800.0,
        "used_gb": 4100.0,
        "percent": 52.5
      }
    ]
  }
  ```

### 5.6. Módulo Seguridad y Red (AdGuard Home)
* **Dependencia:** `httpx`
* **Mecanismo:** Consulta REST a `http://<IP_ADGUARD>:<PORT>/control/stats` con Basic Auth.
* **Endpoint:** `GET /api/network/adguard`
* **Salida JSON:**
  ```json
  {
    "protection_enabled": true,
    "queries_24h": 54200,
    "blocked_24h": 8130,
    "block_ratio_percent": 15.0
  }
  ```

### 5.7. Módulo Spotify Multi-Cuenta (Google Home Integration)
* **Dependencia:** `spotipy` o `httpx` directo contra `https://api.spotify.com/v1/me/player/currently-playing`.
* **Lógica Dual-Account:**
  * En cada ciclo (cada 5 s), el poller consulta el estado de reproducción de cada cuenta registrada.
  * **Criterio de Selección:**
    1. Si una única cuenta está reproduciendo (`is_playing: true`), se publica su estado.
    2. Si ambas están activas, se prioriza la que tenga como dispositivo de reproducción uno de los listados en `preferred_devices` (los altavoces Google Home).
    3. Si ninguna está reproduciendo, se publica `is_active: false`.
* **Endpoint:** `GET /api/media/now-playing`
* **Salida JSON:**
  ```json
  {
    "is_active": true,
    "account": "Cuenta 1",
    "track": {
      "title": "Song Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "album_art_url": "https://i.scdn.co/image/...",
      "duration_ms": 210000,
      "progress_ms": 45000,
      "device_name": "Google Home Cocina"
    }
  }
  ```

### 5.8. Módulo de Noticias (RSS/Atom)
* **Dependencia:** `feedparser`
* **Mecanismo:** Agrega los feeds configurados y extrae los 25 titulares más recientes normalizados.
* **Endpoint:** `GET /api/news`

---

## 6. Diseño y Experiencia de Usuario (Frontend)

### 6.1. Principios de Pantalla Completa (Kiosk UX)
* `h-screen w-screen overflow-hidden select-none cursor-none`.
* No existen barras de desplazamiento (*scrollbars* ocultas).
* Toda información crítica utiliza tipografías de alto peso (`font-bold`, `tracking-tight`) legibles a 3 metros.

### 6.2. Distribución Bento Grid (Full HD 1920x1080)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [ 08:39 ] Martes, 6 de Octubre                                    [ 🛡️ AdGuard: 15% ] [ 🖥️ NAS: 18% ] │
├───────────────────────────────────┬───────────────────────────────────┬─────────────────────────────────┤
│                                   │                                   │                                 │
│  SOLAR POWER FLOW                 │  AGENDA DEL DÍA (Calendar)        │  EL TIEMPO (Weather)            │
│  - Paneles: 3.4 kW (Animado)      │  - 09:30 Reunión Equipo           │  - 19°C Sensación: 19°C        │
│  - Inversor: GoodWe (Activo)      │  - 13:00 Comida familiar          │  - Parcialmente nublado         │
│  - Consumo Hogar: 850 W           │  - 18:00 Taller de cerámica       │  - Previsión próximas 6h        │
│  - Red: Exportando 2.55 kW        │                                   │  - Próximos 5 días              │
│                                   ├───────────────────────────────────┼─────────────────────────────────┤
│                                   │                                   │                                 │
│                                   │  LA COMPRA (Google Keep)          │  SPOTIFY DOMÉSTICO (Condicional)│
│  TOTAL GENERADO HOY: 16.4 kWh     │  ☐ Leche entera                   │  [Carátula] Título Canción      │
│                                   │  ☐ Plátanos                       │  Artista - Google Home Cocina   │
│                                   │  ☑ Aceite de oliva                │  [=====>-------------] 01:23    │
│                                   │                                   │                                 │
├───────────────────────────────────┴───────────────────────────────────┴─────────────────────────────────┤
│  NOTICIAS (RSS Ticker):  [Xataka] Nuevo avance en semiconductores...                            15s ↻   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Tarjeta Dinámica de Spotify:** Si no hay reproducción activa, el componente colapsa suavemente (`opacity-0 max-h-0`) permitiendo que la tarjeta de "La Compra" o el "Tiempo" ocupen más espacio en la cuadrícula. Cuando alguien reproduce música en un Google Home, la tarjeta se expande automáticamente mostrando el arte del álbum y la barra de progreso.

---

## 7. Despliegue en NAS (`docker-compose.yml`)

El backend debe correr en `network_mode: host` para emitir y recibir paquetes UDP hacia el inversor GoodWe en la subred local, así como conectar por localhost con AdGuard y OMV.

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: kitchen-dashboard-backend
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    environment:
      - CONFIG_PATH=/app/config.yaml
      - PYTHONUNBUFFERED=1

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: kitchen-dashboard-frontend
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      - backend
```

### Configuración del Nginx del Frontend (`frontend/nginx.conf`)

```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 8. Configuración del Cliente Kiosko (Raspberry Pi)

En la Raspberry Pi, se crea el script de inicio en `/home/pi/start-kiosk.sh`:

```bash
#!/bin/bash
# Deshabilitar gestión de energía y salvapantallas del monitor
xset s noblank
xset s off
xset -dpms

# Ocultar cursor de ratón tras medio segundo
unclutter -idle 0.5 -root &

# Limpiar posibles cierres erróneos de Chromium
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' ~/.config/chromium/Default/Preferences
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' ~/.config/chromium/Default/Preferences

# Iniciar Chromium en modo Kiosko apuntando al NAS
chromium-browser \
  --noerrdialogs \
  --disable-infobars \
  --kiosk \
  --check-for-update-interval=31536000 \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  http://<IP_DEL_NAS>:3000
```

Para asegurar ejecución al iniciar sesión gráfica en Raspberry Pi OS, añadir en `~/.config/lxsession/LXDE-pi/autostart`:
```text
@/home/pi/start-kiosk.sh
```

---

## 9. Instrucciones Directas para el Agente de Desarrollo de IA

1. **Backend (FastAPI):**
   * Crear los modelos Pydantic en `schemas/models.py` asegurando tipos estrictos.
   * Implementar un `BackgroundScheduler` o tareas asíncronas independientes (`asyncio.create_task`) para cada módulo según sus intervalos en `config.yaml`.
   * En caso de fallo de red de un módulo (por ejemplo, si AdGuard o el inversor no responden temporalmente), atrapar la excepción, loguearla y servir la última lectura válida con un indicador `status: "stale"`, sin tirar la API ni interrumpir a los otros módulos.
2. **Frontend (React + Vite + Tailwind):**
   * Estructurar el grid con Tailwind CSS: `grid grid-cols-12 gap-4 h-screen p-4 bg-slate-950 text-slate-100`.
   * El `SolarFlowWidget` debe mostrar flechas con animación CSS sutil cuando hay flujo de potencia entre nodos.
   * Si `SpotifyNowPlaying` recibe `is_active: false`, el componente debe desmontarse o quedar con altura 0 para dar prioridad a la lista de la compra.