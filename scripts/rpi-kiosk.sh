#!/bin/bash
# Arranque del dispositivo cliente: abre el dashboard en Chromium en modo kiosko.
# Instalación y arranque automático (labwc, wayfire o X11): ver README,
# sección "Dispositivo cliente".
#
# Uso: start-kiosk.sh [URL]   (por defecto DASHBOARD_URL o la de abajo)

DASHBOARD_URL="${1:-${DASHBOARD_URL:-http://<IP_DEL_NAS>:3000}}"
PREFS="$HOME/.config/chromium/Default/Preferences"

# Deshabilitar gestión de energía y salvapantallas del monitor (solo X11).
if command -v xset >/dev/null 2>&1 && [ -n "$DISPLAY" ]; then
  xset s noblank
  xset s off
  xset -dpms
fi

# Ocultar cursor de ratón tras medio segundo.
if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0.5 -root &
fi

# Limpiar posibles cierres erróneos de Chromium (evita la barra "Restaurar páginas").
if [ -f "$PREFS" ]; then
  sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PREFS"
  sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"
fi

# Raspberry Pi OS Bookworm instala el binario como "chromium".
CHROMIUM="$(command -v chromium-browser || command -v chromium)"
if [ -z "$CHROMIUM" ]; then
  echo "Chromium no está instalado" >&2
  exit 1
fi

# Esperar a que el NAS responda antes de abrir el navegador (arranque en frío).
for _ in $(seq 1 60); do
  curl -fsS -o /dev/null --max-time 2 "$DASHBOARD_URL" && break
  sleep 2
done

exec "$CHROMIUM" \
  --noerrdialogs \
  --disable-infobars \
  --kiosk \
  --check-for-update-interval=31536000 \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --disable-features=Translate \
  --autoplay-policy=no-user-gesture-required \
  "$DASHBOARD_URL"
