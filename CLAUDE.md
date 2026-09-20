# Instruções para o agente de IA neste repositório

Projeto acadêmico de segurança (pós-graduação UNCISAL). O código é público desde o início.
Estas regras existem para evitar erros caros de esquecimento — leia antes de editar.

## Nunca fazer

- **Nunca** escrever segredos, senhas, tokens ou chaves de API diretamente no código, mesmo
  "temporariamente para testar". Sempre via `django-environ` (`env(...)`) lendo do `.env`
  (que nunca é commitado). Lista completa do que não pode vazar: `docs/security/nao-commitar.md`.
- **Nunca** adicionar um valor default inseguro a uma variável sensível em `config/settings/prod.py`
  (ex.: `SECRET_KEY`, senha de e-mail). Se faltar no ambiente, a aplicação deve falhar alto
  (`ImproperlyConfigured`), nunca cair silenciosamente para um valor de desenvolvimento.
- **Nunca** desabilitar `CsrfViewMiddleware`, a verificação do Cloudflare Turnstile ou a parede de
  2FA "só para depurar" — isto é, nunca adicionar um bypass ad-hoc no código (`if DEBUG: skip...`,
  comentar a checagem, etc.). Se travar o desenvolvimento, avise e resolva a causa, não contorne.
  Isto é diferente do toggle **por ambiente já sancionado** — `settings.TURNSTILE_ENABLED` (ver
  duas regras abaixo) — que é a forma correta e única de o Turnstile ficar desligado em dev.
- **Nunca** logar senha, código 2FA, token de sessão ou o corpo de um header `Authorization` em
  texto puro — nem em `print`, nem em `logging`, nem em mensagens de erro devolvidas ao usuário.
- **Nunca** usar SQL cru com interpolação de string ou `{% autoescape off %}` / `|safe` em conteúdo
  vindo do usuário. Usar sempre o ORM do Django e o autoescape padrão dos templates.
  (Exceção aceitável: cursor bruto **read-only** em teste, para inspecionar o valor real gravado
  no banco — nunca em código de aplicação.)
- **Nunca** acessar `request.POST`/`request.GET`/JSON do body diretamente na lógica de negócio.
  Toda entrada externa passa primeiro por um `django.forms.Form`/`ModelForm` (ou, se um endpoint
  JSON for necessário, um serializer explícito) com `clean_<campo>`/`clean()` — só o dado validado
  chega em `services.py`.
- **Nunca** confiar no `Content-Type`/extensão enviados pelo cliente para decidir o que fazer com
  um arquivo. Se algum dia o projeto ganhar upload (ex.: anexo em chamado), o tipo real do arquivo
  precisa ser verificado no servidor (assinatura binária, não extensão) antes de aceitar ou servir
  o conteúdo, com uma lista branca explícita de mimetypes aceitos.
- **Nunca** adicionar um campo sensível novo ao modelo sem avaliar se ele precisa do
  `apps.core.fields.EncryptedCharField` (ver `TwoFactorDevice.totp_secret`).
- **Nunca** usar um caminho relativo em `DATABASE_PATH`/qualquer variável de caminho de volume
  Docker — dentro do container isso resolve para fora do volume montado e o dado some no próximo
  `docker compose up --build` (já aconteceu uma vez, ver ADR-008 em `docs/architecture/decisions.md`).
- **Nunca** habilitar Turnstile "manualmente" com um `if` espalhado pelo código. Checar sempre
  `settings.TURNSTILE_ENABLED` (ver ADR-009) — nasce `False` em dev/homologação por não ter chave
  configurada, é forçado `True` em produção via `require()`. Em homologação (`config/settings.staging`)
  não é obrigatório nem proibido ligar o Turnstile: se quiser testar o fluxo completo (não só o
  e-mail), defina `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` no `.env` de staging com as chaves
  **oficiais de teste da Cloudflare** (`1x00000000000000000000AA` / `1x0000000000000000000000000000000AA`
  — sempre validam, nunca são a chave real do domínio), nunca com a chave de produção.
- **Nunca** apontar `EMAIL_HOST`/`EMAIL_HOST_PASSWORD` de homologação para o Gmail de produção.
  Use `DJANGO_SETTINGS_MODULE=config.settings.staging` (Mailtrap/Mailpit — ver ADR-010).
- **Nunca** rodar `docker compose down -v`, `docker volume rm`, `docker system prune --volumes` ou
  qualquer comando que apague volumes (`db_data`, `media_data`) sem confirmação explícita do
  usuário nesta conversa — isso apaga o banco de dados de verdade. `docker compose down` (sem
  `-v`) é seguro, remove só o container; os volumes continuam intactos.
- **Nunca** commitar `db.sqlite3`, `.env`, chaves privadas (`*.pem`, `*.key`) ou capturas de tela
  sem antes conferir o checklist de `docs/security/nao-commitar.md`.
- **Nunca** rodar `git commit --no-verify` para pular os hooks de `pre-commit` (gitleaks,
  detect-private-key). Se um hook falhar, corrigir a causa.
- **Nunca** fazer `git push --force`, `git reset --hard` ou apagar branches sem confirmação
  explícita do usuário nesta conversa.

## Sempre fazer

- Seguir TDD: escrever/ajustar o teste em `apps/<app>/tests/` antes (ou junto) da implementação.
  Rodar `pytest` antes de considerar qualquer tarefa concluída.
- Manter views finas: regra de negócio vai em `services.py`, não em `views.py` (SRP).
- Checar RBAC em toda view nova de `apps/tickets` (usar `apps.accounts.permissions.role_required`
  ou `TicketService`), nunca confiar em dado vindo do cliente para decidir permissão.
- Ao adicionar uma dependência nova, registrar em `requirements.txt` ou `requirements-dev.txt`
  (nunca instalar "solto" só na venv local).
- Ao adicionar uma variável de ambiente sensível nova (chave, senha, segredo), usar o padrão já
  estabelecido: default só em `base.py` (obviamente inseguro, só para dev), e obrigatória via
  `require(env, "NOME")` em `config/settings/prod.py` (ver `config/settings/_require.py`).
- Ao tomar uma decisão de arquitetura não óbvia, registrar um ADR curto em
  `docs/architecture/decisions.md`.
- Rodar `ruff check src` e `black src` (ou deixar o pre-commit rodar) antes de finalizar uma
  alteração.
- Escrever toda mensagem de commit em **inglês**, seguindo Conventional Commits — ver
  `CONTRIBUTING.md`. O resto da documentação fica em português; o histórico de commits, não.

## Contexto do projeto

- Stack: Django 5 (monolito), SQLite, Docker, Nginx, Cloudflare (proxy + Turnstile), Oracle Cloud.
- Estrutura: ver `README.md` → "Estrutura do repositório".
- As 3+ mitigações OWASP Top 10:2025 escolhidas estão documentadas em
  `docs/security/owasp-mitigations.md` — qualquer código relacionado a auth, RBAC ou logging de
  segurança deve manter essa documentação atualizada.
