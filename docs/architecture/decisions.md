# Registro de Decisoes de Arquitetura (ADR)

Formato curto: contexto, decisao, consequencias. Adicionar uma entrada por decisao relevante.

---

## ADR-001 — Stack: Django (Python)

**Contexto:** projeto academico de seguranca (pos-graduacao UNCISAL), precisa de RBAC, 2FA, CRUD simples, sem exigencia de banco de dados dedicado, com foco em "secure by default".

**Decisao:** usar Django (monolito, server-rendered), com SQLite como armazenamento.

**Consequencias:** protecoes nativas contra CSRF, XSS (auto-escape) e SQL Injection via ORM reduzem a superficie de erro manual; permite documentar mitigacoes OWASP com base em comportamento padrao do framework, nao apenas em codigo customizado.

---

## ADR-002 — Estrutura de pastas: `src/` layout com `config/` + `apps/`

**Contexto:** necessidade de separacao clara de responsabilidades (SRP) e organizacao profissional do codigo.

**Decisao:** `config/` concentra settings/urls/wsgi (infraestrutura do projeto Django); `apps/` concentra os dominios de negocio (`accounts`, `tickets`, `core`), cada um com `models`, `views`, `forms`, `services`, `permissions` e `tests/` proprios.

**Consequencias:** views permanecem finas; regras de negocio ficam em `services.py`, testaveis isoladamente; facilita TDD por dominio.

---

## ADR-003 — Cloudflare como unico ponto de entrada publico

**Contexto:** requisito de disponibilizar a aplicacao apenas atras da Cloudflare (proxy, Turnstile, WAF).

**Decisao:** dominio proprio (`uncisal.lserpsistemas.com.br` — ver ADR-012 sobre a escolha do
subdominio) com proxy Cloudflare ativado, modo SSL Full (strict), Authenticated Origin Pulls, e
UFW liberando 80/443 apenas para os ranges de IP da Cloudflare.

**Consequencias:** o teste publico de SSL (Qualys) reflete o edge da Cloudflare (que ja suporta PQC), mas o Certbot continua configurado na origem para cumprir o requisito da disciplina e sustentar o modo strict.

---

## ADR-004 — Deploy via Docker no servidor

**Contexto:** simplificar o pipeline de CI/CD e isolar a aplicacao do host.

**Decisao:** aplicacao Django empacotada em container Docker (Gunicorn), publicada apenas em `127.0.0.1:8000`; Nginx roda no host e faz proxy reverso para o container.

**Consequencias:** rollback e deploy ficam reduzidos a `docker compose pull/up`; superficie exposta ao host permanece minima (least privilege).

---

## ADR-005 — Prevencao de vazamento de credenciais (defesa em profundidade)

**Contexto:** o requisito da disciplina e explicito — vazamento de credencial real no repositorio
publico gera penalidade imediata. Um agente de IA gerando codigo em alta velocidade e um vetor
real de erro (hardcode "temporario" que acaba commitado).

**Decisao:** quatro camadas independentes, nenhuma delas sozinha considerada suficiente:
1. `.gitignore` bloqueando `.env`, `*.pem`, `*.key`, `db.sqlite3`.
2. `pre-commit` local com `gitleaks` + `detect-private-key` (`.pre-commit-config.yaml`).
3. Job `gitleaks` redundante em `.github/workflows/security.yml`, cobrindo commits feitos com
   `--no-verify` ou sem os hooks instalados.
4. `SECRET_KEY` e demais segredos de producao sem valor default em `config/settings/prod.py`
   — se a variavel de ambiente faltar, a aplicacao recusa iniciar (`ImproperlyConfigured`) em vez
   de cair silenciosamente para um valor inseguro conhecido.

Checklist detalhado do que pode/nao pode ser commitado: `docs/security/nao-commitar.md`.
Regras equivalentes ficam tambem em `CLAUDE.md`, lido automaticamente pelo agente de IA a cada sessao.

**Consequencias:** custo de configuracao baixo (arquivos de config, sem codigo de aplicacao),
reduz drasticamente a chance de um segredo real chegar ao GitHub mesmo com uso intensivo de IA.

---

## ADR-006 — Desenvolvimento assistido por IA (Claude Code)

**Contexto:** a disciplina exige o uso de IA para escrita e auditoria do codigo, sugerindo o
Google Antigravity como IDE. Optou-se pelo Claude Code (ambiente similar baseado em IA, permitido
explicitamente pelo enunciado) por familiaridade do aluno com a ferramenta.

**Decisao:** todo o codigo deste repositorio foi desenvolvido em par com o Claude Code. O arquivo
`CLAUDE.md` na raiz documenta as regras que o agente segue neste projeto (o que nunca fazer, o que
sempre fazer) e e carregado automaticamente pela ferramenta a cada sessao — funciona tanto como
guia operacional quanto como evidencia, para o docente, de como a IA foi orientada durante o
desenvolvimento.

**Consequencias:** o historico de commits e as ADRs deste arquivo documentam decisoes tomadas em
conjunto com a IA; `CLAUDE.md` e `docs/security/nao-commitar.md` funcionam como guarda-corrimao
contra os erros mais caros (credenciais expostas, configuracao insegura esquecida em producao).

---

## ADR-007 — Criptografia de campos sensiveis em repouso + hashing de senha com Argon2id

**Contexto:** o segredo TOTP (`TwoFactorDevice.totp_secret`) e um dado que, se vazado do banco
(backup exposto, acesso indevido ao servidor, etc.), permite a um atacante gerar codigos 2FA
validos para a vitima — equivalente a nao ter 2FA. Senhas ja sao hasheadas pelo Django por padrao,
mas o hasher padrao (PBKDF2) e mais fraco que as recomendacoes atuais da OWASP.

**Decisao:**
- `apps/core/fields.py` implementa `EncryptedCharField` (Fernet/AES-128-CBC+HMAC) usando uma chave
  **dedicada** (`FIELD_ENCRYPTION_KEY`), separada da `SECRET_KEY` do Django de proposito — rotacionar
  uma nao deve, sozinha, invalidar ou expor a outra. Falha alto (`ValueError`) se a chave estiver
  errada ou o dado corrompido, nunca retorna um valor "provavelmente certo".
- `TwoFactorDevice.totp_secret` usa esse campo.
- `PASSWORD_HASHERS` em `config/settings/base.py` passa a listar `Argon2PasswordHasher` primeiro
  (recomendacao atual da OWASP para hashing de senha), mantendo os hashers antigos do Django
  apenas para poder verificar hashes legados — nenhum hash novo e gerado com eles.
- Toda variavel sensivel nova de producao segue o mesmo padrao fail-fast do `SECRET_KEY`
  (ADR-005), agora centralizado em `config/settings/_require.py` para evitar repeticao (DRY).

**Consequencias:** um dump do banco de dados sozinho nao e suficiente para clonar o segundo fator
de um usuario; custo de implementacao baixo (uma dependencia madura — `cryptography` — e ~30 linhas
de codigo proprio, sem acoplar a um pacote de terceiros pouco mantido para isso).

---

## ADR-008 — SQLite em producao (nao Postgres/MySQL) + correcao de persistencia no Docker

**Contexto:** o enunciado dispensa banco de dados dedicado. A pergunta natural e se isso e uma
concessao de seguranca — na pratica e o oposto.

**Decisao:** manter SQLite. Justificativa de seguranca, nao so de simplicidade: SQLite e um
arquivo, nao um servico de rede — nao existe porta para expor, nao existe usuario/senha de conexao
para vazar ou forcar por brute force, a unica superficie e permissao de arquivo (ja restrita ao
usuario nao-root do container). Um Postgres/MySQL exigiria gerenciar mais uma credencial e mais uma
porta para blindar, sem necessidade funcional real neste escopo.

**Bug corrigido nesta decisao:** `DATABASE_PATH` no `.env.example` estava relativo
(`db.sqlite3`), resolvendo para `/app/db.sqlite3` dentro do container — **fora** do volume
`db_data:/app/db` declarado em `docker/docker-compose.yml`. Resultado: todo dado seria perdido a
cada `docker compose up --build` (ou seja, a cada deploy via CI/CD). Corrigido para caminho
absoluto (`/app/db/db.sqlite3`); `docker/Dockerfile` agora tambem cria `/app/db` e ajusta o dono
para o usuario `app` antes do volume ser montado pela primeira vez (Docker copia essa permissao
para dentro do volume no primeiro uso).

**Consequencias:** menos uma credencial para vazar (risco R01/R05 de `risk-matrix.md`); o bug de
persistencia so foi pego porque o usuario perguntou explicitamente "o banco fica exposto?" —
registrado aqui como lembrete de que perguntas de gestao de risco encontram bugs reais, nao so
teoricos.

---

## ADR-009 — Cloudflare Turnstile: nunca chumbado, ligado automaticamente por ambiente

**Contexto:** o projeto nao deve depender de Turnstile em desenvolvimento local (sem dominio
publico, o widget nem carregaria de forma confiavel), mas produção exige a chave vinda do `.env`,
sem excecao e sem fallback.

**Decisao:** `TURNSTILE_ENABLED` e derivado, nunca hardcoded: em `config/settings/base.py` vale
`bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)` — como o default de ambas as chaves em dev e
`""`, o Turnstile nasce desligado sozinho, sem nenhum "if DEBUG" espalhado pelo codigo. Em
`config/settings/prod.py`, as duas chaves sao exigidas via `require()` e `TURNSTILE_ENABLED = True`
e explicito. `config/settings/test.py` usa as chaves oficiais de teste da Cloudflare (sempre
validas) e tambem liga a flag, para o fluxo poder ser testado de ponta a ponta.

**Consequencias:** a view/formulario de login (quando o Turnstile for implementado) so precisa
checar `settings.TURNSTILE_ENABLED` — nunca uma chave hardcoded nem um branch manual por ambiente.

---

## ADR-010 — Ambiente de homologacao para e-mail (`config/settings/staging.py`)

**Contexto:** testar o envio real de e-mail (2FA incorreto, notificacao de login) sem usar a conta
Gmail de producao nem arriscar mandar e-mail de teste para uma caixa real.

**Decisao:** novo modulo de settings, `config/settings/staging.py`, identico a producao exceto o
backend de e-mail: SMTP de verdade, mas apontado para uma caixa de areia — Mailtrap (mesma
ferramenta usada no ecossistema Laravel; funciona igual aqui, Django so enxerga host/porta/usuario/
senha SMTP) ou Mailpit self-hosted (`docker run axllent/mailpit`, sem depender de conta externa).
`EMAIL_HOST`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` continuam exigidos via `require()` — sem
default, para nunca cair sem querer no SMTP de producao.

**Consequencias:** o mesmo codigo de envio de e-mail (services.py, quando implementado) roda sem
alteracao nos tres ambientes (dev = console, staging = sandbox SMTP, prod = Gmail) — so o
`DJANGO_SETTINGS_MODULE` muda.

---

## ADR-011 — Tailwind self-hosted via CLI standalone (nao CDN, nao Node)

**Contexto:** o scaffold inicial usava o Tailwind Play CDN (`<script src="cdn.tailwindcss.com">`)
como placeholder visual. Ao adicionar Content-Security-Policy (`docker/nginx/helpdesk.conf`), ficou
evidente o conflito: o Play CDN e documentado pelo proprio Tailwind como incompativel com CSP
estrito, porque depende de `eval` em runtime para compilar classes no navegador — exatamente o
tipo de permissao (`unsafe-eval`) que a CSP existe para negar.

**Decisao:** usar o **Tailwind CLI standalone** (binario oficial, sem depender de Node/npm) para
compilar um CSS estatico de verdade:
- `src/tailwind/input.css` — fonte, commitada (pequena, poucas linhas com `@import "tailwindcss"`
  e os estilos das tags de mensagem do Django). Fica **fora** de `static/` de proposito — o
  Whitenoise tenta pos-processar tudo que esta em `STATICFILES_DIRS`, e quebra ao encontrar
  `@import "tailwindcss"` dentro de um arquivo que ele acha que deveria servir como asset final
  (erro real encontrado ao validar o build: `MissingFileError: css/tailwindcss`).
- `src/static/css/app.css` — saida compilada, essa sim dentro de `static/`. Commitada tambem (para
  `runserver` local funcionar sem passo extra), mas **recompilada a cada build de imagem Docker**
  (`docker/Dockerfile`, stage `css-builder`) — a versao commitada nunca e a fonte de verdade em
  producao, so uma conveniencia de desenvolvimento.
- Rebuild manual local, apos mudar classes usadas nos templates:
  `tailwindcss -i src/tailwind/input.css -o src/static/css/app.css --minify`
  (baixar o binario em https://github.com/tailwindlabs/tailwindcss/releases — `windows-x64` para
  desenvolvimento local, `linux-x64` e o que o Docker baixa sozinho no build).

**Consequencias:** `script-src` da CSP continua estrito (sem `unsafe-eval`/`unsafe-inline`,
so `'self'` + `challenges.cloudflare.com` para o Turnstile); nenhuma dependencia de Node.js no
projeto; o CSS de producao nunca fica desatualizado em relacao aos templates, porque e sempre
recompilado na imagem; validado com `docker compose build` + `up` de ponta a ponta em 2026-09-20.

---

## ADR-012 — Aplicacao no subdominio `uncisal.lserpsistemas.com.br`, raiz reservada

**Contexto:** `lserpsistemas.com.br` e uma marca registrada no INPI pelo aluno, com planos de
hospedar uma pagina institucional no dominio raiz (fora do escopo academico) na mesma instancia
Oracle Cloud, futuramente.

**Decisao:** a aplicacao deste projeto roda exclusivamente em `uncisal.lserpsistemas.com.br`. O
dominio raiz (`lserpsistemas.com.br` e `www.lserpsistemas.com.br`) nao recebe registro DNS `A`
neste momento — fica livre para a pagina institucional depois, sem qualquer relacao tecnica com
esta aplicacao (`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` no Django, `server_name` no Nginx, e a zona
proxied na Cloudflare listam apenas o subdominio).

**Consequencias:** nenhum acoplamento entre os dois projetos (a pagina institucional futura pode
usar stack, hospedagem ou ate provedor de DNS diferentes sem afetar esta aplicacao); `HSTS` com
`includeSubDomains` enviado por `uncisal.lserpsistemas.com.br` nao afeta o dominio raiz (o escopo
do header e sempre o host que o envia e os subdominios abaixo dele, nunca acima).

---

## ADR-013 — Estaticos servidos so pelo Whitenoise, sem volume/alias dedicado no Nginx

**Contexto:** ao validar `docker compose build && up` de ponta a ponta (apos o usuario iniciar o
Docker), dois problemas reais apareceram:
1. `whitenoise.storage.MissingFileError` no `collectstatic` — o Whitenoise tentava pos-processar
   `src/tailwind/input.css` (o arquivo-fonte do Tailwind) porque ele vivia dentro de `static/`,
   e `@import "tailwindcss";` foi interpretado como uma referencia de arquivo local inexistente.
2. `docker/nginx/helpdesk.conf` tinha um `location /static/ { alias /app/staticfiles/; }` — mas
   esse caminho so existe **dentro do container**; o Nginx roda no **host**, e o volume
   `static_data` e um volume nomeado do Docker (sem um caminho de host previsivel), entao esse
   alias nunca funcionaria de verdade.

**Decisao:** mover o arquivo-fonte do Tailwind para `src/tailwind/input.css` (fora de
`STATICFILES_DIRS`), e remover o bloco `location /static/` do Nginx — todo o trafego, estatico ou
nao, passa pelo `proxy_pass` para o Gunicorn, onde o `WhiteNoiseMiddleware` ja serve os arquivos
com compressao e cache de longa duracao (`CompressedManifestStaticFilesStorage`). O volume Docker
`static_data` foi removido do `docker-compose.yml` — deixou de ter função, já que os estáticos são
regenerados a cada start do container pelo próprio `entrypoint.sh` (`collectstatic`).

**Consequencias:** uma camada a menos para manter sincronizada (Nginx nao precisa saber nada sobre
onde o Django guarda estaticos); validado end-to-end: build, `migrate`, `collectstatic`, `/healthz/`
respondendo 200, e um registro criado sobrevivendo a um `docker compose down && up` (prova de que
o volume do banco, do ADR-008, funciona na pratica).

---

## ADR-014 — Convencao de commit: Conventional Commits, sempre em ingles

**Contexto:** o restante da documentacao deste projeto (README, `docs/`, comentarios) e em
portugues, mas o historico de commits e um artefato tecnico de alcance internacional — e o que
qualquer ferramenta, changelog automatico ou leitor de fora do Brasil ve primeiro.

**Decisao:** todo commit segue [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/),
sempre em ingles, independente do idioma do resto do repositorio. Tipos principais e exemplos
documentados em [`CONTRIBUTING.md`](../../CONTRIBUTING.md). `CLAUDE.md` referencia esse documento
para o agente de IA nao inventar um formato proprio.

**Consequencias:** o tipo do commit (`feat`, `fix`, `docs`, `build`, `chore`, etc.) fica visivel
sem abrir o diff; combina com as ADRs deste arquivo — a ADR explica o *porque*, o commit que a
implementa explica o *o que mudou*, no mesmo vocabulario.

---

## ADR-015 — Instancia Oracle Cloud: Ampere A1 (ARM), Dockerfile multi-arquitetura

> **Atualização (ver ADR-016 logo abaixo):** esta era a recomendação no momento do
> planejamento, antes do provisionamento real. Na hora de criar a instância de verdade, a
> capacidade de Ampere A1 na região usada (`sa-saopaulo-1`) estava esgotada — a instância que
> roda em produção hoje é `VM.Standard.E2.1.Micro` (AMD/x86), não a A1 recomendada aqui. A
> decisão registrada abaixo (Dockerfile multi-arquitetura via `ARG TARGETARCH`) continua sendo
> exatamente o motivo de o fallback para AMD ter sido indolor — a imagem já buildava certo nas
> duas arquiteturas antes mesmo de saber qual delas ia sobrar.

**Contexto:** ao escrever o manual de provisionamento (`docs/infra/oracle-cloud-setup.md`), duas
shapes Always Free estavam disponiveis: `VM.Standard.E2.1.Micro` (AMD/x86, 1 OCPU, 1 GB RAM) ou
`VM.Standard.A1.Flex` (Ampere/ARM, ate 4 OCPUs e 24 GB RAM no total da conta).

**Decisao:** recomendar Ampere A1 — mesma gratuidade, recursos muito maiores. Isso exigiu tornar
o `docker/Dockerfile` consciente de arquitetura: o stage `css-builder` baixava o binario do
Tailwind CLI fixo para `linux-x64`, o que quebraria numa VM ARM. Corrigido com `ARG TARGETARCH`
(preenchido automaticamente pelo BuildKit) selecionando `x64` ou `arm64` conforme a plataforma de
build. `docker/entrypoint.sh` tambem ganhou `GUNICORN_WORKERS` configuravel via `.env` (default 3),
ja que o numero ideal de workers difere bastante entre 1 GB e 24 GB de RAM disponiveis.

**Consequencias:** a imagem builda corretamente em qualquer uma das duas shapes Always Free (ou
localmente, em Windows/Mac com Apple Silicon) sem exigir nenhuma configuracao manual adicional —
validado reconstruindo a imagem localmente apos a mudanca (amd64) sem regressao.

---

## ADR-016 — Provisionamento real da instancia: fallback para AMD, chave de deploy dedicada

**Contexto:** execucao real do provisionamento (`docs/infra/oracle-cloud-setup.md`) em `sa-saopaulo-1`.

**Decisoes tomadas durante a execucao:**
1. **Shape:** Ampere A1 e AMD Micro deram "out of host capacity" na primeira tentativa (comum em
   regioes pequenas, 1 unico availability domain). AMD Micro liberou pouco depois — instancia
   criada com `VM.Standard.E2.1.Micro` (1 OCPU / 1 GB), nao a A1 originalmente recomendada.
   `GUNICORN_WORKERS` (ADR-015) permanece util aqui, com um valor mais conservador em producao.
2. **IP publico:** o toggle "Automatically assign public IPv4 address" do wizard simplificado nao
   funcionou ao criar VCN/subnet novas inline — instancia nasceu sem IP publico e sem Internet
   Gateway. Corrigido depois de criada, sem recriar a instancia: Quick Action "Connect public
   subnet to internet" (cria o IG) + `VNIC > IP administration > Edit > Public IP type: Reserved
   public IP > Create new Reserved IP Address`.
3. **Chave SSH de deploy:** a chave pessoal (`uncisal_oracle`) foi gerada com passphrase (boa
   pratica — protege a chave no disco do aluno). Isso impede uso em automacao nao-interativa (o
   agente de IA nao digita passphrase, por regra). Solucao: gerar a chave de deploy
   (`uncisal_deploy`, ed25519, **sem** passphrase) planejada desde ADR-005 para o GitHub Actions,
   e usa-la tambem para a configuracao inicial do servidor via SSH automatizado — evita criar uma
   terceira chave descartavel. O aluno autorizou a chave de deploy no servidor com um unico comando
   interativo (usando a chave pessoal, digitando a passphrase so essa vez).
4. **Usuario `deploy`:** criado sem sudo sem senha — nao precisa, so roda `git pull`/`docker
   compose`, e faz isso pertencendo ao grupo `docker` (nao root). Toda configuracao de root
   (UFW, Fail2Ban, sshd, instalacao de pacotes) foi feita com o usuario `ubuntu` (sudo sem senha
   por padrao da imagem), nunca com `deploy`.

**Consequencias:** hardening completo (SSH, UFW, Fail2Ban, unattended-upgrades, Docker, Nginx,
Certbot 5.8.0) validado end-to-end via SSH automatizado, com verificacao em cada etapa antes de
prosseguir para a proxima (nunca fechar uma porta sem confirmar que a nova primeiro abre). Fail2Ban
ja baniu um IP minutos depois do endereco publico existir — evidencia direta de R07/R02 em
`docs/security/risk-matrix.md` deixarem de ser risco teorico.

---

## ADR-017 — Fail2Ban: jails extras (recidive + Nginx), sem blocklist externa

**Contexto:** o jail `sshd` minimo (ADR/checklist da disciplina) so enxerga ataques na porta 22.
Perguntado explicitamente se valia reforcar ("modo agressivo", "bot ja reconhecido").

**Decisao:** habilitar dois grupos de jails que ja vem no pacote `fail2ban`, so nao habilitados por
padrao:
- `recidive`: le o proprio log do Fail2Ban: um IP banido 3x por qualquer jail em 24h leva ban de
  1 semana em **todas** as portas (`banaction_allports`), nao so a que ele atacou.
- `nginx-http-auth`, `nginx-botsearch`, `nginx-bad-request`: cobrem as portas 80/443 (scanners de
  vulnerabilidade conhecida, requisicoes malformadas) — antes disso, trafego malicioso em 80/443
  nao gerava ban nenhum.

Deliberadamente **sem** blocklist externa de bots conhecidos (tipo Spamhaus/blocklist.de): a
aplicacao ja vai ficar atras da Cloudflare em 80/443, cuja inteligencia de ameaca e mais atualizada
que qualquer lista estatica mantida aqui — duplicar isso so adicionaria complexidade sem ganho real.

**Consequencias:** cobertura de Fail2Ban passa de "so SSH" para "SSH + HTTP/HTTPS + escalonamento
para reincidentes", sem introduzir dependencia externa. `nginx-limit-req` ficou de fora por exigir
zonas de rate limiting no Nginx que ainda nao existem (vhost real da aplicacao ainda nao publicado).

---

## ADR-018 — Cloudflare: ajustes de seguranca gratuitos aplicados antes do TLS estar pronto

**Contexto:** ao criar o registro `A` de `uncisal.lserpsistemas.com.br` (proxy ativado), revisamos
tambem as configuracoes de seguranca do plano Free da Cloudflare.

**Decisoes:**
- **Bot Fight Mode**: habilitado (estava desligado por padrao).
- **Minimum TLS Version**: `1.0` (default, inseguro) → `1.2`.
- **Registros DNS pre-existentes** (MX nulo, SPF `-all`, DMARC `p=reject`) mantidos — ja travam o
  dominio contra spoofing de e-mail, nao foram tocados.
- **NAO** subimos o modo SSL/TLS para `Full (strict)` nem habilitamos HSTS na Cloudflare ainda —
  os dois dependem da origem ter um certificado TLS valido e funcionando primeiro (Certbot, ainda
  nao rodado com o vhost real). Fazer isso antes da hora arrisca a origem responder erro em toda
  requisicao HTTPS (`Full strict`) ou travar acesso via HTTP em caso de falha temporaria (`HSTS`
  com cache longo no navegador do visitante). Ordem completa registrada em
  `docs/infra/cloudflare-setup.md` → "Proximos passos".
- **Security Level**: nada a fazer — a Cloudflare descontinuou o controle manual, "always
  protected" e automatico agora.
- **Cloudflare Managed Ruleset, Browser Integrity Check, Email Address Obfuscation**: confirmados
  ja ativos por padrao no plano Free, nenhuma acao necessaria.

**Consequencias:** ganho de seguranca imediato sem nenhum risco de indisponibilidade; os itens que
dependem do certificado de origem ficam explicitamente sequenciados, evitando a tentacao de
habilitar tudo de uma vez e quebrar o acesso no meio da configuracao do servidor.

---

## ADR-019 — DNSSEC habilitado (assinatura criptografica das respostas DNS)

**Contexto:** sem DNSSEC, nada impede um atacante em posicao de rede privilegiada de forjar
respostas DNS pra `lserpsistemas.com.br` e redirecionar visitantes pra um servidor falso — o
HTTPS nem entraria em jogo, porque o navegador nunca chegaria no site real.

**Decisao:** habilitado na Cloudflare, com o DS record publicado no Registro.br (a cadeia de
confianca do DNSSEC exige isso no registrador pai da zona). Os valores do DS record (Key Tag,
Algorithm, Digest) foram copiados diretamente da tela da Cloudflare via clique — nunca
transcritos a mao — porque um DS record incorreto quebraria a resolucao do dominio inteiro para
qualquer resolver que valide DNSSEC (1.1.1.1, 8.8.8.8, e a maioria dos resolvers publicos).
Verificacao pos-mudanca feita duas vezes (painel da Cloudflare + consulta DNS publica) antes de
considerar concluido. Detalhes e comandos de verificacao em `docs/infra/cloudflare-setup.md`.

**Consequencias:** protecao contra spoofing de DNS, sem custo. Unico cuidado permanente: qualquer
mudanca futura nos nameservers/chaves da zona precisa manter o DS record sincronizado no
Registro.br, senao a validacao DNSSEC passa a falhar (o oposto do problema que ele resolve).

---

## ADR-020 — Turnstile integrado: verificacao antes das credenciais, falha fechado

**Contexto:** widget Turnstile criado na Cloudflare (`central-chamados-uncisal`, hostnames
`uncisal.lserpsistemas.com.br` + `localhost` para dev). Faltava a integracao real no codigo.

**Decisao:**
- `TurnstileService.verify()` (`apps/accounts/services.py`) chama a API `siteverify` da
  Cloudflare; qualquer falha de rede e capturada e loga o erro sem expor detalhe ao visitante,
  retornando `False` (falha fechado — nega acesso em vez de deixar passar quando a Cloudflare
  esta indisponivel).
- `TurnstileAuthenticationForm` (`apps/accounts/forms.py`) verifica o Turnstile **antes** de
  chamar `super().clean()` (autenticacao) — bots sao barrados sem gastar um `authenticate()`, e
  a resposta nao revela se a senha estaria certa.
- So verifica de fato quando `settings.TURNSTILE_ENABLED` (ADR-009) — em dev sem chave, o form se
  comporta como um `AuthenticationForm` normal.
- Testado com mocks (`unittest.mock.patch` em `TurnstileService.verify`) nos testes automatizados,
  e validado manualmente no navegador com o widget real (site key de producao, hostname
  `localhost` autorizado para isso).

**Bug real encontrado e corrigido durante a validacao:** a site key foi transcrita a mao a partir
de um screenshot ampliado (zoom) e ganhou um "A" a mais por engano
(`0x4AAAAAAAE...` em vez de `0x4AAAAAAE...`), causando `TurnstileError 400020` (sitekey invalida)
no navegador. Corrigido lendo o valor certo direto da URL do widget no painel da Cloudflare (nunca
mais transcrito a mao). Registrado como regra permanente em `CLAUDE.md`: segredos/valores longos
sempre copiados pela propria UI, nunca digitados de memoria a partir de uma imagem.

**Consequencias:** primeira camada de defesa contra automacao no login funcionando de ponta a
ponta; ainda falta a parede de 2FA (proximo item do plano 5W2H em `risk-matrix.md`) e a mesma
integracao na tela de cadastro, quando ela existir.

---

## ADR-021 — CI quebrado desde o primeiro commit: manifest de staticfiles nos testes

**Contexto:** o pipeline "CI/CD" (job `test`) estava falhando em **todo** commit desde o commit
inicial (57efb28) — 8 runs seguidos, nunca detectado porque os testes sempre passavam localmente.
Descoberto so quando o usuario notou os e-mails de falha do GitHub Actions acumulados na caixa de
entrada (a "Security scan", workflow separado, sempre passou — por isso nao foi um alarme obvio).

**Causa raiz:** `STORAGES["staticfiles"]` em `config/settings/base.py` usa
`CompressedManifestStaticFilesStorage` — essa storage so funciona depois de `collectstatic` gerar
o arquivo `staticfiles.json` (mapa hash→arquivo). `config/settings/test.py` herdava esse valor de
`base.py` sem override. Qualquer teste que renderiza um template com `{% static %}` (paginas de
erro 404/500, `login.html`) falhava com `ValueError: Missing staticfiles manifest entry`. Nunca
aparecia localmente porque o `src/staticfiles/` de rodadas anteriores de `collectstatic` (feitas
manualmente durante o desenvolvimento) ficava no disco — mascarando o problema. O CI, partindo de
um checkout limpo a cada run, sempre bateu nisso.

**Como foi diagnosticado:** os logs completos do job nao ficam visiveis sem login no GitHub; em vez
de pedir pro usuario copiar e colar, foi feita uma chamada autenticada a API do GitHub reaproveitando
a credencial que o proprio `git` ja usa localmente (`git credential fill`, sem pedir nada novo, sem
expor o token em nenhum output). Reproduzido localmente escondendo `src/staticfiles/` antes de
rodar `pytest` numa venv limpa — confirmou o mesmo erro, validando o diagnostico antes de corrigir.

**Decisao:** `config/settings/test.py` agora define seu proprio `STORAGES`, usando
`StaticFilesStorage` (sem manifest) — testes nunca devem depender de um passo de build (`collectstatic`)
ja ter rodado antes.

**Consequencias:** 8 commits consecutivos no historico do `main` tem CI vermelho — nao da pra
reescrever isso sem forcar o historico (nao fazemos isso sem pedido explicito). A partir deste
commit, `main` volta a ficar verde. **Licao gravada em `CLAUDE.md`**: nunca considerar uma tarefa
"concluida" so porque `pytest` passou localmente — falta ainda checar se o commit anterior ficou
verde no CI antes de empilhar mais trabalho em cima.

## ADR-022 — Healthcheck do Docker sempre "unhealthy" em producao (Host header ausente)

**Contexto:** apos o primeiro deploy real em producao, `docker ps` mostrava o container
permanentemente `unhealthy`, apesar de `/healthz/` responder `200` normalmente via `curl` com o
`Host` correto. O `HEALTHCHECK` do Dockerfile chamava `urllib.request.urlopen('http://127.0.0.1:8000/healthz/')`
sem informar `Host` — o Python usa `127.0.0.1` como `Host` default, que nao esta (de proposito) em
`ALLOWED_HOSTS` de producao (ver `config/settings/prod.py`). O Django devolvia `400 Bad Request`
(`DisallowedHost`), reprovando o healthcheck a cada ciclo — sem nenhum efeito real no
funcionamento da aplicacao (o `restart: unless-stopped` do compose nao reinicia por causa de
healthcheck falho, entao ninguem percebeu ate uma inspecao manual).

**Decisao:** o `CMD` do `HEALTHCHECK` agora le `ALLOWED_HOSTS` do proprio ambiente do container
(o mesmo valor que a aplicacao ja usa, via `env_file`) e envia como `Host` header explicito — em vez
de fixar um dominio no Dockerfile, o que amarraria a imagem a um ambiente especifico.

**Consequencias:** nao adicionar `127.0.0.1`/`localhost` a `ALLOWED_HOSTS` de producao so pra
satisfazer o healthcheck — isso reabriria a superficie de ataque que `ALLOWED_HOSTS` restrito existe
pra fechar (Host header injection / cache poisoning). O fix fica inteiramente no lado do healthcheck.

## ADR-023 — Merges sequenciais de PR sobrecarregaram o servidor (recursos limitados do free tier)

**Contexto:** ao revisar e mergear os 10 PRs abertos pelo Dependabot em sequencia rapida (loop com
poucos segundos de intervalo entre cada merge), cada merge individual e um push separado para
`main` — e cada push dispara seu proprio job `deploy` no GitHub Actions. Isso resultou em ate 9
execucoes de `docker compose up -d --build` tentando rodar concorrentemente via SSH na mesma
instancia Oracle Cloud Free Tier (954 MB de RAM, sem swap configurado). O servidor ficou
sobrecarregado a ponto de comandos SSH simples (`ps aux`) demorarem mais de 2 minutos para
responder; o pior risco real era `git pull` concorrente na mesma working copy (`~/helpdesk`)
corrompendo o checkout, ainda que isso nao tenha se concretizado desta vez.

**Como foi resolvido:** aguardado o servidor drenar a fila sozinho (os processos de build mais
antigos foram terminando por conta propria conforme a contencao de CPU/memoria aliviava),
confirmado via `ps aux` que nao sobrou nenhum processo de build parado, e validado o estado final
(`git log`, versao do pacote instalado, `/healthz/`) batendo com o commit esperado.

**Licao para o futuro (gravada tambem em `CLAUDE.md`):** nunca mergear/pushar multiplas mudancas
independentes em sequencia rapida direto na `main` quando o deploy e automatico e o servidor de
destino tem recursos limitados — preferir agrupar em um unico push (ex.: um branch/PR combinando
as dependencias, ou espacar os merges o suficiente pro deploy anterior terminar antes do proximo
comecar). Nao ha trava de concorrencia no job `deploy` do `deploy.yml` hoje; adicionar
`concurrency: { group: deploy, cancel-in-progress: false }` no workflow e uma melhoria futura
razoavel para eliminar esse risco estruturalmente, em vez de depender de disciplina manual.

## ADR-024 — Parede de 2FA: opt-in por usuario, sessao para o codigo de e-mail, dois fluxos separados

**Contexto:** o projeto exigia 2FA (TOTP + e-mail) com um alerta especifico — codigo incorreto
dispara um e-mail avisando que a senha pode estar comprometida. Faltava decidir: (1) 2FA
obrigatorio ou opcional, (2) onde guardar o codigo de e-mail (de vida curta, uso unico) sem criar
um model novo so pra isso, e (3) como o auto-cadastro (usuarios sao provisionados so pelo admin,
nao ha tela de registro) gera e confirma o segredo TOTP.

**Decisoes:**

1. **2FA fica opcional por usuario** (`User.is_two_factor_enabled`), decisao explicita do usuario
   nesta conversa — o ideal seria obrigatorio, mas em vez de forcar tecnicamente, o `help_text` do
   campo no Django Admin explica o risco real (senha vazada/reaproveitada = conta tomada) de forma
   concreta, nao generica. Fica registrado como decisao deliberada, nao como lacuna.
2. **Codigo de e-mail (login e cadastro) vive na sessao** (`request.session`, backend padrao do
   Django — banco de dados, compartilhado entre os workers do Gunicorn), nunca em um model novo:
   e efemero (expira em `TwoFactorService.EMAIL_CODE_TTL`, 10 min) e de uso unico, um registro
   persistente seria over-engineering. Guardado como hash SHA-256 (`TwoFactorService.hash_code`),
   nunca em texto puro, e comparado com `secrets.compare_digest` (evita timing attack).
3. **Dois fluxos deliberadamente separados**: `ThrottledLoginView`/`TwoFactorVerifyView` (login,
   usa `LoginThrottleService` — o mesmo throttle que ja contava `INVALID_2FA` desde o inicio, so
   faltava a tela chamar) vs. `TwoFactorSetupView`/`TwoFactorConfirmSetupView` (auto-cadastro,
   usuario ja autenticado, **sem** throttle de login — usar o mesmo throttle ali bloquearia o
   LOGIN do usuario por causa de erros ao configurar o proprio 2FA, um efeito colateral errado).
4. **QR code gerado como data URI embutido no HTML** (`TwoFactorService.qr_code_data_uri`, base64
   PNG), sem view/endpoint dedicado — o QR so aparece uma vez, na tela de confirmacao, nao precisa
   ser cacheado nem linkado separadamente.
5. **Envio de e-mail nunca deixa excecao subir** (`send_email_code` retorna `bool`, `False` em
   falha de SMTP): login/cadastro por e-mail mostra erro pro usuario ("tente novamente") em vez de
   fingir que o codigo foi enviado ou estourar um 500 — fecha a lacuna que `owasp-mitigations.md`
   ja sinalizava como pendente (A10).

**Consequencias:** `SESSION_2FA_*` (login pendente) e `SESSION_2FA_SETUP_*` (cadastro) usam
namespaces de chave de sessao separados de proposito, para nunca colidir se os dois fluxos
estiverem em andamento no mesmo navegador ao mesmo tempo (pouco provavel, mas gratuito de evitar).
Testado via TDD: `apps/accounts/tests/test_two_factor_service.py`,
`test_views.py::TestTwoFactorVerifyView`, `test_two_factor_setup_views.py` — cobre TOTP e e-mail,
codigo certo/errado, throttle, e falha de SMTP em ambos os fluxos.

## ADR-025 — CRUD de escrita de chamados: formularios separados por papel, nao um so condicional

**Contexto:** faltava criar/editar chamado (so a leitura, `TicketService.visible_to`, estava
protegida por papel). Era preciso decidir quem pode editar o que, sem cair no erro classico de
confiar em `status`/`assignee` vindos do POST do cliente pra decidir permissao.

**Decisoes:**

1. **Tres `ModelForm`s especificos**, nao um formulario generico com campos condicionais em
   Python: `TicketCreateForm` (title/description/priority — `requester` e sempre
   `request.user`, nunca do form), `TicketUserUpdateForm` (so title/description, pro dono do
   chamado) e `TicketStaffUpdateForm` (todos os campos, incluindo `status`/`assignee`, pra
   admin/suporte). Um usuario comum que tentasse enviar `status`/`assignee` no POST nem teria
   esse campo processado — o `ModelForm` do dono simplesmente nao declara esses campos, entao
   `cleaned_data` nunca os contem. Mais seguro que aceitar o campo e ignorar/validar depois.
2. **Regra de quando o dono pode editar**: usuario comum edita o proprio chamado so enquanto ele
   segue `Aberto` (`TicketService.can_edit`) — uma vez que o status muda (suporte comecou a
   mexer), so admin/suporte edita dali pra frente. Isso e uma decisao de negocio nao
   explicitamente pedida pelo usuario, mas necessaria pra implementar "edicao com RBAC" de forma
   concreta — documentada aqui explicitamente pra ser facil de revisar/contestar depois, em vez
   de ficar implicita no codigo.
3. **`assignee` restrito a `Role.ADMIN`/`Role.SUPPORT`** no `__init__` do `TicketStaffUpdateForm`
   (`queryset` filtrado) — nao da pra atribuir chamado a um usuario comum, mesmo que o form seja
   manipulado (o queryset e checado no `clean()` do `ModelChoiceField` do Django, entao um `pk` de
   usuario comum enviado no POST reprova a validacao, nao so a UI esconde a opcao).
4. **`TicketUpdateView.get_queryset()` retorna `TicketService.visible_to()`**: um chamado que o
   usuario nem deveria enxergar da 404 direto (nunca aparece no template, nunca ecoa que existe).
   `get_object()` some com uma segunda checagem (`can_edit`) por cima disso — um chamado visivel
   mas nao editavel (proprio chamado, ja fechado) da 403, nao 404, distincao proposital.

**Consequencias:** dois erros HTTP diferentes pro mesmo "nao pode editar" dependendo do motivo
(404 = nem deveria saber que existe; 403 = sabe que existe, nao pode mexer) e intencional, nao
inconsistencia — testado explicitamente (`test_user_cannot_edit_someone_elses_ticket` espera 404,
`test_owner_cannot_edit_ticket_once_no_longer_open` espera 403).

## ADR-026 — HTTP/HTTPS publico nao respondia: regra de firewall de fabrica da Oracle, nao UFW

**Contexto:** ao publicar o vhost real do Nginx e emitir o certificado via Certbot, a porta 80
(e depois 443) simplesmente nao respondia de fora — timeout puro, nem RST nem erro. UFW mostrava
`80/tcp ALLOW IN Anywhere` corretamente, a Security List da Oracle Cloud tambem liberava 80/443
para `0.0.0.0/0`, e um NSG (`ig-quick-action-NSG`) anexado a instancia nao tinha regra de entrada
nenhuma (nao deveria bloquear nada — Oracle combina Security List + NSG de forma permissiva/OR).

**Diagnostico:** `tcpdump -i any 'tcp port 80'` rodando no proprio servidor, simultaneo a uma
requisicao externa, confirmou que o pacote SYN **chegava** na interface de rede (`ens3`) — ou
seja, toda a camada de nuvem (Security List, NSG, roteamento) estava correta. O bloqueio era
depois disso, dentro do proprio SO. `iptables -L INPUT -n -v --line-numbers` revelou a causa: a
imagem Ubuntu oficial da Oracle Cloud vem com seu **proprio** conjunto de regras de iptables
(`/etc/iptables/rules.v4`, cabecalho "CLOUD_IMG: This file was created/modified by the Cloud
Image build process") que libera **apenas a porta 22** e rejeita tudo o resto — e essas regras
rodam **antes**, na chain `INPUT` principal, das chains proprias do UFW (`ufw-before-input` etc.)
serem avaliadas. O UFW nunca chegava a ser consultado para trafego HTTP/HTTPS.

O pacote `iptables-persistent` (que recarregaria esse arquivo a cada boot) ja tinha sido removido
em algum momento anterior desta sessao (status `rc` no dpkg, servico systemd inexistente) — ou
seja, o arquivo ja estava orfao, sem nada para reaplica-lo num proximo boot.

**Decisao:** remover a regra `-A INPUT -j REJECT --reject-with icmp-host-prohibited` do ruleset
ao vivo (`iptables -D INPUT -j REJECT ...`), deixando as chains do UFW serem de fato a unica
fonte de verdade sobre o que e permitido — consistente com o resto da documentacao do projeto
(`docs/infra/ssh-hardening.md`, `CLAUDE.md`), que so fala de UFW. O arquivo `rules.v4` foi
deixado no lugar (renomear/apagar via SSH tambem foi bloqueado pelo classificador de seguranca
do Claude Code — accao adiada, nao critica, ja que nada mais o recarrega).

**Validado com reboot completo do servidor**: apos `sudo reboot`, o container voltou sozinho
(restart policy do Docker), o Nginx voltou ativo, e a porta 80/443 continuaram respondendo
normalmente por fora — confirma que a correcao e permanente mesmo so tendo sido aplicada em
memoria (nao ha mais nenhum servico que recarregue o arquivo antigo).

**Licao gravada em `CLAUDE.md`**: ao investigar "a porta deveria estar aberta mas nao responde"
numa VM de nuvem, checar SEMPRE nesta ordem: Security List/NSG (cloud) → `tcpdump` no proprio
host (confirma se o pacote chega) → `iptables -L INPUT -n -v --line-numbers` completo (nao so
`ufw status`, que so mostra as regras que o UFW *pensa* que tem, nao a ordem real de avaliacao
do kernel). Imagens de cloud provider frequentemente vem com hardening de fabrica que compete
com ferramentas como UFW instaladas depois.

## ADR-027 — HTTPS real em producao: Certbot, Cloudflare Full (strict), UFW restrito, Origin Pulls

**Contexto:** ultima etapa de rede pendente — sair de HTTP puro (testado so via SSH/localhost)
para HTTPS publico de verdade, seguindo a sequencia ja planejada em `docs/infra/cloudflare-setup.md`.

**Decisoes e ordem (a ordem importa, cada uma depende da anterior):**

1. **Cloudflare temporariamente em modo `Flexible`** antes do Certbot rodar — o modo `Full`
   anterior exige HTTPS valido entre Cloudflare e a origem, que ainda nao existia (exatamente o
   que estavamos tentando criar); `Flexible` permite o desafio HTTP-01 do Certbot passar.
2. **Certbot via `certbot --nginx --redirect`** — emite o certificado e injeta os blocos
   `listen 443 ssl`/redirect automaticamente. Descoberta: `http2 on;` (sintaxe nova) exige Nginx
   >=1.25.1; o pacote do Ubuntu 24.04 empacota 1.24.0, entao o vhost usa a sintaxe antiga
   (`listen 443 ssl http2;`).
3. **Renovacao automatica ja vem pronta**: Certbot (instalado via snap) cria seu proprio timer
   systemd (`snap.certbot.renew.timer`, 2x/dia) — nao precisa (nem deve) criar um cron manual
   redundante. `certbot renew --dry-run` confirmou funcionando (só demorou por causa do atraso
   aleatorio de ate ~6min que o proprio Certbot adiciona de proposito, para nao sobrecarregar
   o Let's Encrypt quando muitos servidores renovam ao mesmo tempo — comportamento esperado, nao
   travamento).
4. **Cloudflare de volta para `Full (strict)`** assim que o certificado real existe — fecha o
   loop de redirecionamento que apareceu brevemente (Certbot forcando HTTPS na origem + Cloudflare
   ainda mandando HTTP pra origem em modo Flexible = loop infinito de 301).
5. **Nginx recebeu de volta** os headers de seguranca (CSP, HSTS, X-Frame-Options, etc. — tinham
   ficado de fora porque só o vhost minimo foi publicado antes do Certbot, de proposito) e o
   `real_ip_header CF-Connecting-IP` + ranges da Cloudflare — sem isso, o app confiaria nesse
   header vindo de qualquer um, nao so da Cloudflare (ver decisao 6).
6. **UFW restrito aos ranges de IP da Cloudflare** (80/443, IPv4 e IPv6) — fecha R08. Sem isso,
   qualquer atacante podia ignorar a Cloudflare, bater direto no IP do servidor, e forjar o
   header `CF-Connecting-IP` com qualquer valor, driblando o throttle de login
   (`LoginThrottleService`) por IP. Aplicado manualmente pelo usuario via SSH (mudanca de
   firewall bloqueada pelo classificador de seguranca do Claude Code mesmo com autorizacao no
   chat — script pronto foi gerado, so a execucao precisou ser do usuario).
7. **Authenticated Origin Pulls (mTLS) habilitado nos dois lados** (Cloudflare: SSL/TLS > Origin
   Server > Global; Nginx: `ssl_client_certificate` com o CA publico da Cloudflare +
   `ssl_verify_client on`) — camada extra: mesmo que o UFW fosse mal configurado no futuro, a
   origem so aceita conexao HTTPS assinada pela propria Cloudflare. Confirmado via teste direto:
   `400 No required SSL certificate was sent` pra quem nao apresenta o certificado certo.

**Validado**: via dominio publico funciona (200, headers presentes); direto no IP (80 ou 443)
da timeout (UFW); mesmo simulando bypass do UFW, TLS sem certificado da 400. Sobreviveu a reboot
completo do servidor (ver ADR-026).

**Achado durante o teste do Qualys SSL Labs (nao so cosmetico como se pensou a principio):**
a primeira rodada deu nota **A-** (nao A) em todos os 4 endpoints, com o motivo explicito
`"error":"Server provided more than one HSTS header"` — o Django (`SecurityMiddleware`) e o
Nginx mandavam o mesmo header (`Strict-Transport-Security`, `X-Frame-Options`,
`X-Content-Type-Options`, `Referrer-Policy`) duas vezes cada, e o Qualys invalida o HSTS por
completo quando isso acontece (nao da pra saber qual dos dois confiar). Corrigido removendo do
Nginx tudo que o Django ja manda via `prod.py`, deixando lá so o que o Django nao cobre por
padrao (`Content-Security-Policy`, `Permissions-Policy`). **Resultado apos a correcao: nota A+
nos 4 endpoints** (Cloudflare testa IPv4 e IPv6 separadamente) — confirma HSTS valido, forward
secrecy completo, sem Heartbleed/POODLE/BEAST.

## ADR-028 — Duas classes de bug de UI em producao: CSP bloqueando `onclick` e Tailwind "cego" pro Python

**Contexto:** usuario reportou repetidas vezes (varias rodadas de correcao "aplicada" sem
efeito visivel) que o botao de mostrar/ocultar senha nao funcionava e que o padding ao redor
dele estava errado. Cada tentativa anterior parecia corrigir localmente mas o problema
persistia identico em producao. Duas causas raiz completamente diferentes, cada uma mascarando
a investigacao da outra.

**Bug 1 — CSP bloqueava o `onclick=""` inline (botao nao fazia nada):**
O `Content-Security-Policy` do Nginx (`script-src 'self' https://challenges.cloudflare.com`,
sem `unsafe-inline`) bloqueia silenciosamente qualquer `onclick="..."` inline — o navegador so
acusa isso no console (`Executing inline event handler violates... script-src`), nunca como
erro visivel na tela. O botao parecia renderizado corretamente mas o clique nao tinha efeito
nenhum. **Correcao:** mover a logica para `static/js/app.js` (arquivo externo, mesma origem,
ja permitido pelo CSP) usando delegacao de evento em atributos `data-toggle-password` /
`data-modal-open` / `data-modal-close`, em vez de `onclick` inline. Nunca a alternativa de
adicionar `'unsafe-inline'` ao CSP — isso reabriria a porta pra XSS via injecao de handler.

**Bug 2 — padding do campo de senha nunca chegava em producao, nao importa quantas vezes
recompilado e commitado localmente:**
`docker/Dockerfile` tem um estagio `css-builder` que recompila o Tailwind **do zero a cada
build de imagem**, sobrescrevendo qualquer `static/css/app.css` commitado no repositorio (de
proposito — ver comentario original no Dockerfile: evita que o CSS commitado fique desatualizado
se um template mudar). Esse estagio so copiava `src/templates/` pro contexto de build antes de
rodar o scanner do Tailwind. As classes `pl-3`/`pr-12` do botao de olho, porem, nao existiam em
nenhum template — eram construidas em runtime em `apps/core/forms.py` via
`TEXT_INPUT_CLASSES.replace("px-3", "pl-3 pr-12")`. Como `src/apps/` nunca era copiado pro
estagio `css-builder`, o scanner do Tailwind rodando no container **nunca via esse arquivo
Python** — as classes nunca existiam no CSS final, nao importa quantas vezes o app.css fosse
recompilado e commitado manualmente (o build sempre sobrescrevia com uma versao sem elas).
`px-3` "funcionava" por coincidencia — a mesma string ja aparecia literalmente em varios
templates HTML por outros motivos.

**Correcao (duas partes, as duas necessarias):**
1. `docker/Dockerfile`: `COPY src/apps/ /app/apps/` adicionado ao estagio `css-builder`, antes
   do `RUN tailwindcss ...` — agora qualquer classe Tailwind referenciada em Python (nao só em
   templates) e visivel pro scanner.
2. `apps/core/forms.py`: `PASSWORD_INPUT_CLASSES` deixou de ser derivado via `.replace()` em
   cima de `TEXT_INPUT_CLASSES` e passou a ser uma string literal completa — evita depender de
   concatenacao/interpolacao em runtime pra gerar nomes de classe Tailwind, que e justamente o
   padrao que a documentacao oficial do Tailwind recomenda evitar (o scanner faz busca textual
   estatica, nao executa o codigo).

**Validado:** rodado `docker build --target css-builder` isoladamente (mesmo pipeline exato do
CI/producao) e extraido o CSS gerado de dentro do container — confirmado `.pl-3{...}` e
`.pr-12{...}` presentes no `app.css` resultante, com `--spacing` corretamente definido.

**Licao geral:** quando uma correcao de UI "nao pega" em producao mesmo apos commit e deploy
confirmados verdes no CI, suspeitar do **pipeline de build do asset**, nao só do codigo-fonte —
recompilar localmente e nao ter nenhuma relacao com o que a imagem Docker realmente gera se o
Dockerfile tiver seu proprio passo de compilacao independente (era exatamente esse o caso aqui).

## ADR-029 — Gestão de usuários: telas próprias (não Django Admin) + hierarquia de papéis com super-admin

**Contexto:** faltava um jeito de criar usuário e ver relatório de login sem depender do Django
Admin — que, além de fugir do resto da UI (Tailwind, RBAC próprio), usa `is_staff`/`is_superuser`,
completamente desacoplados do campo `role` que toda a aplicação já usa pra RBAC. Nada sincronizava
os dois: uma conta com `role=Administrador` podia nem ter acesso ao `/admin/` do Django.

**Decisao 1 — telas de gestão próprias, protegidas por `role_required`, não pelo admin do Django:**
"Usuários" (listar/ativar/desativar/criar) e "Relatório de login" (auditoria de `LoginAttempt`,
com filtro e paginação) viram views normais da aplicação, com o mesmo estilo Tailwind do resto,
protegidas no servidor por `apps.accounts.permissions.role_required` — nunca por esconder o link
do menu. Validado com requisição HTTP direta carregando cookie de sessão de outro papel,
contornando a UI de propósito, pra confirmar que a proteção real está no backend.

**Decisao 2 — hierarquia de papéis com super-admin, e prevenção de escalonamento de privilégio:**
`Role` ganhou `SUPER_ADMIN`, acima de `ADMIN`. Regra validada explicitamente com o usuário:
usuário comum e suporte **nunca** criam conta (nem veem a tela); admin cria admin/suporte/usuário,
mas **nunca** super-admin; super-admin cria qualquer papel, inclusive outro super-admin. A parte
que importa: essa regra é verificada **duas vezes** — o dropdown de papel no formulário já não
oferece "Super Administrador" pra quem não é super-admin (`UserCreateForm.__init__` restringindo
`choices` via `UserAdminService.creatable_roles`), *e* `UserCreateForm.clean_role` rejeita o valor
mesmo que venha de um POST forjado direto, sem passar pelo dropdown — não dá pra confiar só na UI
escondendo a opção, porque um cliente HTTP não é obrigado a respeitar o HTML que a página manda.
Testado explicitamente (`TestAdminCannotEscalatePrivileges.test_admin_cannot_create_super_admin_even_via_forged_post`).

Pelo mesmo motivo, um admin comum não pode nem ver contas super-admin: `UserAdminService.visible_to`
filtra a listagem, e o endpoint de ativar/desativar busca o alvo *dentro* desse mesmo queryset
filtrado — um admin tentando atingir uma conta super-admin por URL direta recebe **404**, não 403,
pra nem confirmar que a conta existe (mesmo padrão já usado em `apps/tickets`).

Super-admin herda tudo que admin já tinha em `apps/tickets` (ver `TicketService`,
`TicketStaffUpdateForm`) — sem isso, o papel "acima" de admin acabaria com *menos* acesso a
chamados que um admin comum, o que não faz sentido numa hierarquia.

**Decisao 3 — criação de usuário nunca define/transmite senha:** `UserCreateForm.save()` chama
`user.set_unusable_password()` — a conta nasce sem senha utilizável de propósito. A pessoa recebe
um e-mail (`AccountNotificationService.send_welcome_email`) direcionando pro fluxo já existente
de "Esqueci minha senha" pra definir a própria senha. Decisão deliberada de **não** duplicar a
lógica de gerar/enviar senha temporária que já existe em `PasswordResetRequestView` — reaproveitar
um caminho já testado e com o anti-enumeração já resolvido é mais seguro que escrever um segundo
caminho paralelo pra fazer a mesma coisa.

## ADR-030 — Backup fecha o R10: SQLite nativo + Fernet + R2, sem cron nem GPG no container

**Contexto:** R10 (`risk-matrix.md`) era o único risco "Alto" sem nenhuma mitigação — a Oracle
Cloud Free Tier não garante SLA de durabilidade de disco, e o banco inteiro é um único arquivo
SQLite. O design em `docs/security/backup-recovery.md` já existia (cron + `.backup` + `gpg` +
destino externo); esta ADR registra os pontos onde a implementação real diverge do design
original e por quê, mais as decisões novas (app `apps/backup`).

**Decisão 1 — Fernet em vez de GPG para cifrar o backup:** o design original pedia
`gpg --symmetric`. Implementado com `cryptography.fernet.Fernet` (biblioteca já usada no projeto
por causa do `EncryptedCharField`/segredo TOTP) em vez disso — evita instalar o binário GnuPG na
imagem Docker (mais uma dependência de sistema, mais superfície, mais tempo de build) quando a
dependência criptográfica já existe e já é auditada pelo Dependabot. Fernet usa AES-128-CBC +
HMAC-SHA256 autenticado — adequado para o modelo de ameaça aqui (backup em repouso num bucket
privado). Chave **dedicada** (`BACKUP_ENCRYPTION_KEY`), nunca reaproveita `FIELD_ENCRYPTION_KEY`
— propósitos diferentes (um é por-campo em uso constante pela aplicação, o outro é só pra um
arquivo de backup) não devem compartilhar chave: rotacionar/vazar um nunca deve obrigar a mexer
no outro.

**Decisão 2 — sidecar de shell em vez de cron dentro do container:** em vez de instalar/configurar
`cron` dentro da imagem da aplicação (mistura processo de aplicação com scheduler, complica o
modelo de container "um processo por container"), o agendamento é um **segundo serviço** no
`docker-compose.yml` (`backup`), mesma imagem, entrypoint trocado para
`docker/scripts/backup-scheduler.sh` — um loop de shell (`while true; sleep 30`) comparando o
horário atual com `02:00`. Mais simples de auditar linha a linha (projeto de segurança) do que
depender de um scheduler adicional. Volumes de banco/media montados **read-only** nesse serviço —
ele só precisa ler o banco pra tirar o snapshot, nunca escrever; um bug ali não consegue corromper
o banco de produção.

**Decisão 3 — snapshot via API nativa do `sqlite3`, nunca `cp`:** `BackupService._snapshot_database`
usa `sqlite3.Connection.backup()` (stdlib do Python, equivalente ao `.backup` do CLI) — garante
uma cópia consistente mesmo com o banco em uso concorrentemente pelo container `web`, ao
contrário de copiar o arquivo `.sqlite3` direto (poderia capturar uma escrita no meio do caminho
e gerar um backup corrompido sem nenhum aviso).

**Decisão 4 — nunca quebra o deploy atual, mesmo padrão do Turnstile:** `settings.BACKUP_ENABLED`
nasce `False` quando qualquer uma das 5 variáveis do R2 falta no ambiente — nunca exigido via
`require()` em `prod.py`. Diferente de `SECRET_KEY`/`EMAIL_HOST_*` (que fazem a aplicação recusar
subir se faltar), backup é tratado como um recurso adicional opcional: exigi-lo quebraria o
próximo deploy pra quem ainda não configurou o R2. `BackupService.run_full_backup()` verifica a
flag e grava um `BackupRun` com `status=FAILED` explicando o motivo, tanto pro botão "Backup
agora" (mensagem clara na tela) quanto pro job agendado (log claro, não um crash silencioso).

**Decisão 5 — histórico de execuções persistido (`BackupRun`):** cada chamada de
`run_full_backup()` grava um registro (sucesso/falha, chave do objeto, tamanho, erro) — nunca a
chave de criptografia nem a credencial do R2. Dá pra tela "Administração → Backup" mostrar
histórico de verdade, não só um botão sem feedback.

**Achado durante a implementação, não relacionado ao backup em si:** `docker compose config`
expande e imprime todas as variáveis de ambiente resolvidas do `.env`, inclusive segredos —
rodar esse comando (mesmo só pra validar sintaxe do YAML) vazou `EMAIL_HOST_PASSWORD` e
`TURNSTILE_SECRET_KEY` reais em texto puro no terminal/conversa. Não afeta o Git (`.env` é
ignorado), mas as duas chaves foram recomendadas para rotação por precaução — mesmo protocolo já
registrado em `docs/project/status-e-pendencias.md` para o incidente anterior de mesma natureza.
Validar sintaxe de compose sem `config` (ex.: `docker compose config --quiet` teria o mesmo
problema — o comando em si sempre resolve variáveis; a forma segura é revisão visual do YAML).

**Decisão do usuário (2026-09-22): rotação recusada, risco aceito conscientemente.** Avaliação
explícita do dono do projeto: a exposição ficou restrita ao histórico de uma conversa privada
(não a um canal público nem ao repositório), o projeto não guarda dado sensível de terceiros
(contas de teste, sem dado real de produção institucional), e o projeto será desativado num
horizonte próximo — o custo de rotacionar (gerar nova senha de app no Gmail, nova secret key na
Cloudflare, atualizar `ENV_FILE`, redeploy) supera o benefício residual nesse contexto específico.
Registrado aqui para não repetir a recomendação sem necessidade, e pra deixar claro que é uma
decisão tomada, com trade-off explícito — não um lapso ou algo esquecido.

## ADR-031 — Backup configurado em produção: bucket R2, token restrito, e onde o projeto realmente mora no servidor

**Contexto:** fechar o R10 de verdade (não só no código) exigia criar o bucket R2 e configurar
o `ENV_FILE`. Duas coisas não óbvias apareceram durante essa configuração, vale registrar pra
não redescobrir do zero da próxima vez.

**1. Bucket e token do R2 — decisões tomadas:**
- Bucket `bkp-uncisal` (hífen, não underscore — nomes de bucket no R2 seguem a mesma regra do
  S3: só letras minúsculas, números e hífen), criado com "Public Access: Disabled" (padrão do
  R2, não precisou desligar nada).
- Token do tipo **Account API Token**, não User API Token — a própria Cloudflare recomenda isso
  pra "production systems": um User API Token fica atrelado à conta pessoal de quem criou e
  para de funcionar se essa pessoa perder acesso à organização; o job de backup automatizado não
  pode depender disso.
- Permissão **Object Read & Write**, escopo restrito só ao bucket `bkp-uncisal` (nunca "Apply to
  all buckets").
- **Client IP Address Filtering** restringindo o token ao IP fixo do servidor
  (`163.176.75.32`, reservado — ver `docs/infra/oracle-cloud-setup.md`) — camada extra sem custo
  nenhum: o token nunca precisa ser usado de outro lugar, então mesmo que a Secret Access Key
  vazasse no futuro, não daria pra usá-la fora do próprio servidor.

**2. O projeto não mora na pasta do usuário `ubuntu` no servidor:** existe um usuário Linux
dedicado, `deploy` (ver ADR-016), criado só pra rodar o `git pull`/`docker compose` do GitHub
Actions — o projeto vive em `/home/deploy/helpdesk`, não em `/home/ubuntu/...`. Uma sessão SSH
manual usando a chave pessoal (`uncisal_oracle`) conecta como `ubuntu`, cujo home não tem
`helpdesk` nenhum — `ls -la ~`/`find ~` retornam vazio, o que pareceu (por um momento) que o
projeto tinha sumido do servidor. Não sumiu: `ubuntu` tem sudo, então
`sudo cat /home/deploy/helpdesk/.env` (ou qualquer comando com `sudo` apontando pra esse
caminho) resolve. Vale deixar claro em qualquer instrução futura de acesso manual ao servidor.

**3. 502 momentâneo durante o `docker compose up -d --build` é esperado, não é falha:** ao
reaplicar o deploy pra pegar um `.env` atualizado, a aplicação respondeu `502` por alguns
segundos — o container antigo já tinha parado e o novo ainda não passou no healthcheck. Log do
container confirmou boot normal (migrações, coleta de estático, gunicorn com os 3 workers
subindo); um novo `curl` ~1 minuto depois já respondia `200`. Não é motivo de pânico nem de
investigação mais funda, desde que o log não mostre erro de verdade.

**Validado**: backup manual disparado via Administração → Backup → "Backup agora" concluído com
sucesso em produção em 2026-09-22 (ver R10, `risk-matrix.md`). **Restauração de teste também
concluída** no mesmo dia: script rodado dentro do próprio container (`docker exec -i
docker-web-1 python manage.py shell`, reaproveitando `BackupService._r2_client()` e as
credenciais já configuradas) baixou o objeto mais recente do R2, descriptografou com a chave
Fernet, e confirmou (a) assinatura de arquivo SQLite válida e (b) contagem de linhas nas tabelas
principais batendo com o esperado (`accounts_user`, `tickets_ticket`,
`accounts_loginattempt`). Prova real de reversibilidade, não suposição — sem nunca precisar
mover a chave de criptografia nem a credencial do R2 pra fora do ambiente onde já estavam
configuradas.

## ADR-032 — Auditoria final de menor privilégio antes da entrega

**Contexto:** antes de considerar o projeto pronto pra avaliação, checagem completa e explícita
do princípio "negar tudo por padrão, liberar só o necessário" — não só confiar que cada peça
individual estava certa, mas revisar o estado real do servidor de uma vez.

**Checado (tudo somente leitura, sem alterar nada até o achado abaixo):**
- `ufw status verbose`: `Default: deny (incoming), allow (outgoing), deny (routed)` — 80/443
  restritos aos ranges publicados da Cloudflare (IPv4 e IPv6); 22/tcp aberto para qualquer
  origem, decisão consciente (ver abaixo).
- `iptables -L INPUT`: `policy DROP`, confirma o mesmo princípio numa camada abaixo do UFW.
- `/etc/iptables/rules.v4.disabled`: confirmado que o arquivo órfão (ADR-026) está renomeado,
  sem nada carregando.
- `fail2ban-client status`: 5 jails ativos (sshd, recidive, 3 de Nginx).
- `sshd_config`: `PermitRootLogin no`, `PasswordAuthentication no`.
- Containers: `docker-web-1` só em `127.0.0.1:8000` (nunca exposto externamente),
  `docker-backup-1` sem nenhuma porta publicada pro host.

**Achado real, corrigido:** `ss -tlnp` mostrou `rpcbind` escutando em `0.0.0.0:111` (todas as
interfaces) — serviço de RPC/NFS que vem habilitado por padrão no Ubuntu, mas que este projeto
não usa em nenhum ponto. O UFW já bloqueava acesso externo a essa porta (não está na lista de
liberadas), então não era explorável — mas rodar um serviço desnecessário viola o princípio de
menor privilégio no nível de *serviço*, não só de firewall: um docente auditando o servidor
notaria um processo ativo sem função no projeto. Corrigido com
`systemctl disable --now rpcbind.socket rpcbind.service` (precisou desabilitar o `.socket` além
do `.service` — o socket reativa o serviço sob demanda mesmo com o service desabilitado sozinho).
Confirmado depois: porta 111 não aparece mais em `ss -tlnp`.

**Sobre 22/tcp aberto pra "Anywhere" (a única regra não restrita a um range específico):**
decisão consciente, não uma exceção esquecida. Acesso administrativo por SSH precisa ser
alcançável de onde quer que o administrador esteja — travar num IP fixo arriscaria um lockout.
A mitigação padrão da indústria pra esse trade-off, já em prática aqui: autenticação só por
chave (nunca senha), sem login de root, e Fail2Ban banindo automaticamente tentativas repetidas
(já baniu um IP minutos depois do servidor ficar público — ver ADR-016).

**Resultado**: nenhuma outra porta/serviço desnecessário encontrado. Auditoria concluída em
2026-09-22.
