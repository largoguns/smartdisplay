# Cómo contribuir

## Mensajes de commit: Conventional Commits

Todos los commits siguen [Conventional Commits 1.0](https://www.conventionalcommits.org/es/v1.0.0/):

```
<tipo>(<ámbito opcional>): <descripción en imperativo y minúsculas>

<cuerpo opcional: qué y por qué>

<pie opcional: BREAKING CHANGE: ..., referencias>
```

| Tipo | Para |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de un error |
| `docs` | Solo documentación |
| `refactor` | Cambio de código sin cambiar comportamiento |
| `test` | Tests |
| `build` | Docker, dependencias, compose |
| `chore` | Mantenimiento que no encaja en los anteriores |

- **Ámbitos habituales:** el módulo afectado (`solar`, `sems`, `nas`, `adguard`, `keep`, `calendar`, `weather`, `spotify`, `news`), `frontend`, `config`, `kiosk`.
- Un cambio incompatible (p. ej. renombrar una clave de `config.yaml`) lleva `!` tras el tipo (`feat(config)!: ...`) y un pie `BREAKING CHANGE:` explicando cómo migrar.
- Un commit por cambio lógico: no mezclar una funcionalidad con correcciones no relacionadas.

Ejemplos:

```
feat(weather): permite varias ubicaciones con tarjetas compactas
fix(nas): lee cpuUtilization en OMV 8
docs: documenta el despliegue con Portainer
```

## Antes de hacer commit

- Tests del backend: `cd backend && .venv/bin/pytest`
- Tipos del frontend: `cd frontend && npx tsc --noEmit`
- **Nunca** subas `config.yaml` ni `.env` (están en `.gitignore`): contienen credenciales. El repositorio es público; revisa que no se cuelen IPs, coordenadas, tokens ni correos personales en ejemplos o tests.
