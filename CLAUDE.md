# Notas para agentes

- Commits: **Conventional Commits** (ver [CONTRIBUTING.md](CONTRIBUTING.md)). Un commit por cambio lógico.
- Repositorio público: nada de datos personales ni secretos en código, ejemplos o tests. `config.yaml` y `.env` están en `.gitignore`.
- Antes de commit: `pytest` en `backend/` y `npx tsc --noEmit` en `frontend/`.
