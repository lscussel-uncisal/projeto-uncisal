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
