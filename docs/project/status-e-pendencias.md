# Status do projeto e pendências

Este documento tem um único objetivo: separar claramente **o que já está pronto** (não repetir
aqui, só apontar onde está registrado) de **o que ainda falta**, com detalhe suficiente para
retomar o trabalho sem precisar redecidir nada — sem inventar requisito novo, só consolidando o
que já foi combinado ao longo do projeto (nesta conversa e nas anteriores).

Atualizado em: 2026-09-21.

## O que já está pronto (não duplicar aqui — ver a fonte)

| Item | Onde está registrado |
|---|---|
| Scaffold Django (services layer, settings por ambiente, TDD) | `README.md`, `docs/architecture/decisions.md` (ADR-001 em diante) |
| Criptografia em repouso (`EncryptedCharField`), Argon2, throttle de login | `docs/architecture/decisions.md`, `docs/security/risk-matrix.md` (R02, R06) |
| Docker + Nginx + Whitenoise (bugs corrigidos: persistência SQLite, CSP do Tailwind) | ADR-008, ADR-011, ADR-013 |
| Provisionamento Oracle Cloud + hardening SSH + Fail2Ban (sshd + recidive + nginx-*) | `docs/infra/oracle-cloud-setup.md`, `docs/infra/ssh-hardening.md` |
| Cloudflare: DNS proxied, Bot Fight Mode, DNSSEC, Turnstile no login | `docs/infra/cloudflare-setup.md`, ADR-019, ADR-020 |
| CI/CD completo (testes + deploy automático via SSH), 4 GitHub Secrets configurados | `.github/workflows/deploy.yml`, ADR-021 |
| Bug do healthcheck do Docker (400 por falta de Host header) | ADR-022 |
| 10 PRs do Dependabot revisados/mergeados + incidente de sobrecarga do servidor corrigido | ADR-023, `CLAUDE.md` |
| Gestão de risco 5W2H | `docs/security/risk-matrix.md` |

## O que falta

Ordenado pela sequência já combinada. Cada item tem a spec mínima pra implementar sem re-perguntar
o óbvio — mas **checar com o usuário antes de qualquer decisão que não esteja aqui**.

### 1. Parede de 2FA (TOTP + e-mail) — próximo item, em andamento

- **Duplo fator**: TOTP via `pyotp` (já na `requirements.txt`) **e** código por e-mail como
  alternativa/fallback — não só um dos dois.
- **Fluxo**: após Turnstile + credenciais válidas (já implementado em `ThrottledLoginView`), redirecionar
  para uma tela de verificação de 2FA antes de criar a sessão autenticada de fato.
- **Feature de segurança específica já combinada com o usuário**: se o código informado (TOTP ou
  e-mail) estiver **incorreto**, disparar um e-mail de alerta pro dono da conta avisando que a
  senha pode estar comprometida e sugerindo troca — isso é diferente do throttle (que já existe,
  `LoginThrottleService` cobre `INVALID_2FA`) e não deve ser confundido com ele.
- **Modelo**: `TwoFactorDevice` com `totp_secret` via `EncryptedCharField` — verificar se já existe
  no código atual (`apps/accounts/models.py`) antes de criar de novo.
- Ver `docs/security/risk-matrix.md`, linha 2b (R03) e `docs/security/owasp-mitigations.md`.
- TDD: escrever teste do fluxo completo (código certo → sessão autenticada; código errado →
  e-mail de alerta disparado + sessão não criada) antes da implementação.

### 2. CRUD de escrita de chamados com RBAC

- Hoje só a **leitura** de chamados está protegida por papel (`TicketService.visible_to`).
  Criar/editar chamado ainda não existe.
- Usar `ModelForm` + `apps.accounts.permissions.role_required` (ou checagem equivalente em
  `TicketService`) antes de qualquer `.save()` — nunca confiar em dado vindo do cliente pra
  decidir permissão.
- Fecha R04 por completo — ver `docs/security/risk-matrix.md`.

### 3. HTTPS real na produção (Certbot → Full strict → HSTS → UFW restrito)

Sequência já definida em `docs/infra/cloudflare-setup.md` ("Próximos passos"), na ordem:

1. Publicar o vhost real do Nginx no host (`docker/nginx/helpdesk.conf`, `server_name
   uncisal.lserpsistemas.com.br`) — hoje só existe o `default` do Nginx no servidor.
2. Rodar Certbot no servidor pra emitir certificado real (funciona com o modo `Full` atual da
   Cloudflare).
3. Subir o modo SSL/TLS da Cloudflare pra `Full (strict)`.
4. Habilitar HSTS na Cloudflare (o Django já manda `Strict-Transport-Security` desde `prod.py`,
   falta o lado da Cloudflare).
5. Restringir UFW aos ranges de IP da Cloudflare em 80/443 + Authenticated Origin Pulls (mTLS) —
   fecha R08.
6. Rodar o teste do Qualys SSL Labs (validação pública exigida pelo enunciado do projeto).

### 4. Backup automatizado, criptografado, fora do servidor

- R10 no `risk-matrix.md`, hoje 🔴 pendente — é o único risco "Alto" sem nenhuma mitigação ainda.
- Design já existe em `docs/security/backup-recovery.md` — falta só a implementação (cron na VM +
  destino externo).

### 5. Housekeeping pequeno, sem pressa

- Confirmar 2FA ativo nas contas de infraestrutura (Oracle Cloud, Cloudflare) — R11.
- Rotacionar a Turnstile **secret key** no painel da Cloudflare — o valor antigo apareceu em texto
  puro nesta conversa por engano do usuário ao colar; não é urgente (só a secret key vazou, e só
  neste chat privado), mas é a prática correta.
- Apagar `prod.env` da pasta temporária de scratch depois que os GitHub Secrets forem conferidos
  (já cumpriu a função, não precisa persistir).

### 6. Manual de estudos + roteiro de apresentação (vídeo de 5–10 min)

Pedido explícito do usuário em 2026-09-21, registrado como **último item**, depois de todo o resto
acima estar pronto. **Importante: este é um artefato local, fora do repositório** — o usuário foi
explícito que não quer isso versionado/publicado no GitHub (o repo é público). Quando for feito,
salvar fora de `C:\Claude\projeto-uncisal` (ou, se dentro, garantir que o caminho está no
`.gitignore` antes de qualquer commit — nunca assumir, conferir com `git status`).

- Um manual/material de estudo que não só documente **o que** foi feito (isso os artefatos em
  Markdown já cobrem bem), mas explique o **porquê** de cada decisão relevante — ótima base pra
  isso: consolidar as ADRs mais importantes em prosa didática, não só a lista técnica.
- Um roteiro de apresentação em vídeo (5–10 minutos) cobrindo os pontos que a disciplina exige:
  hardening do servidor, hygiene de segredos no repositório público, a aplicação (RBAC, 2FA,
  Turnstile), e o CI/CD automatizado.
- Não inventar conteúdo novo aqui — a base é só organizar e explicar o que já está implementado e
  documentado no resto do repositório.
