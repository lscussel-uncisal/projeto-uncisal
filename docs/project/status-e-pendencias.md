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
| Parede de 2FA (TOTP + e-mail) com alerta em código incorreto + auto-cadastro com QR code | ADR-024, `docs/security/risk-matrix.md` (R03) |
| CRUD de escrita de chamados (criar/editar) com RBAC — dono edita só enquanto Aberto, staff edita tudo | ADR-025, `docs/security/risk-matrix.md` (R04) |
| HTTPS real em produção (Certbot, Full strict, UFW restrito à Cloudflare, Authenticated Origin Pulls) | ADR-026 (bug do firewall de fábrica da Oracle), ADR-027, `docs/security/risk-matrix.md` (R08) |
| CSS quebrado em produção (CSP bloqueando `onclick` inline; Docker "cego" pra classe Tailwind construída em Python) | ADR-028 |
| Telas próprias de gestão de usuários (criar/listar/ativar-desativar) e relatório de login, sem depender do Django Admin | ADR-029 |
| Hierarquia de papéis com super-admin, prevenção de escalonamento de privilégio (admin nunca cria super-admin, nem forjando POST) | ADR-029 |
| Backup completo (SQLite nativo + Fernet + Cloudflare R2), agendado + botão manual, fecha o R10 no código — falta só configurar credenciais em produção (ver abaixo) | ADR-030, `docs/security/backup-recovery.md` |

## O que falta

Ordenado pela sequência já combinada. Cada item tem a spec mínima pra implementar sem re-perguntar
o óbvio — mas **checar com o usuário antes de qualquer decisão que não esteja aqui**.

### 1. Configurar o backup em produção (código já pronto — ver ADR-030)

- Criar/confirmar o bucket R2 e o token de API (dash.cloudflare.com) — ver
  "Como habilitar em produção" em `docs/security/backup-recovery.md`.
- Adicionar as 6 variáveis novas ao GitHub Secret `ENV_FILE` (o deploy sobrescreve o `.env` do
  servidor a partir dele a cada push — editar só no servidor via SSH não sobrevive ao próximo
  deploy).
- Depois de configurado, testar o botão "Backup agora" (Administração → Backup) e fazer pelo
  menos uma restauração de teste (comando em `backup-recovery.md`).

### 2. Rotacionar dois segredos (precaução, não comprometimento confirmado)

- `EMAIL_HOST_PASSWORD` e `TURNSTILE_SECRET_KEY` apareceram em texto puro nesta conversa por
  causa de um `docker compose config` rodado por engano (ver ADR-030, achado final) — mesmo
  protocolo do incidente anterior de mesma natureza (ver item abaixo). Gerar nova senha de app
  no Gmail e nova secret key no painel da Cloudflare, atualizar `ENV_FILE`.

### 3. Housekeeping pequeno, sem pressa

- Confirmar 2FA ativo nas contas de infraestrutura (Oracle Cloud, Cloudflare) — R11.
- Apagar `prod.env` da pasta temporária de scratch depois que os GitHub Secrets forem conferidos
  (já cumpriu a função, não precisa persistir).
- Renomear/apagar o arquivo órfão `/etc/iptables/rules.v4` no servidor (ver ADR-026) — hoje
  inofensivo (nada mais o recarrega), mas fica limpo remover de vez. Bloqueado pelo classificador
  de segurança do Claude Code quando tentei via SSH; precisa ser o usuário a rodar:
  `sudo mv /etc/iptables/rules.v4 /etc/iptables/rules.v4.disabled`.

### 4. Manual de estudos + roteiro de apresentação (vídeo de 5–10 min)

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
