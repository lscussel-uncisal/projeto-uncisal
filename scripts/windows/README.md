# Scripts do Windows

Atalhos pra rodar o projeto localmente no Windows sem precisar decorar comandos.

## `dev-up.bat` — sobe o servidor de desenvolvimento

- Aplica migrações pendentes do banco (SQLite local).
- Abre o servidor Django numa **janela de terminal separada**, em `http://localhost:8000`.
- Pode fechar essa janela normalmente pra parar, ou usar o `dev-down.bat`.

Pré-requisito (só na primeira vez): criar a virtualenv e instalar as dependências.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
```

## `dev-down.bat` — derruba o servidor de desenvolvimento

Encontra o processo escutando na porta 8000 e encerra ele. Seguro rodar mesmo se não
houver nada rodando (só avisa e não faz nada).

## Observações

- Esses scripts usam `config.settings.dev` (padrão do `manage.py`) — banco SQLite local,
  Turnstile desligado automaticamente se `TURNSTILE_SITE_KEY`/`SECRET_KEY` não estiverem no
  `.env`. **Nunca** apontam pra produção.
- Se mudar alguma classe Tailwind nos templates, o CSS **não** recompila sozinho — rodar
  manualmente (ver `README.md` da raiz do repositório, seção sobre Tailwind) antes de testar
  visualmente, senão o navegador carrega o CSS antigo em cache.
- Não têm relação com o deploy de produção — isso continua automático via GitHub Actions a
  cada `git push` (ver `.github/workflows/deploy.yml`).
