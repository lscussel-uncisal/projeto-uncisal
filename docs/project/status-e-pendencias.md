# Status do projeto e pendências

Este documento tem um único objetivo: separar claramente **o que já está pronto** (não repetir
aqui, só apontar onde está registrado) de **o que ainda falta**, com detalhe suficiente para
retomar o trabalho sem precisar redecidir nada — sem inventar requisito novo, só consolidando o
que já foi combinado ao longo do projeto (nesta conversa e nas anteriores).

Atualizado em: 2026-09-22.

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
| Backup completo (SQLite nativo + Fernet + Cloudflare R2), agendado + botão manual, fecha o R10 — configurado e testado com sucesso em produção, **incluindo restauração de teste real**, em 2026-09-22 | ADR-030, ADR-031, `docs/security/backup-recovery.md`, `docs/security/risk-matrix.md` (R10) |
| Manual de estudos + roteiro de apresentação (vídeo de 5–10 min) | Roteiro/manual: arquivo **local, fora do repositório de propósito** (`docs/apresentacao-uncisal.md`, no `.gitignore`), entregue ao usuário. Vídeo gravado a partir do roteiro: público, linkado no `README.md` — [youtu.be/zeNkYWfGxD4](https://youtu.be/zeNkYWfGxD4) |
| Papel do avaliador promovido para Admin (via `role_required`, sem tocar Django Admin) | ADR-029; e-mail da conta nunca registrado no repositório, por instrução explícita do usuário |
| Auditoria final de menor privilégio (UFW, iptables, Fail2Ban, SSH, serviços do sistema) — achado e corrigido: `rpcbind` escutando desnecessariamente em `0.0.0.0:111` | ADR-032 |
| 2FA ativo nas contas de infraestrutura (Oracle Cloud, Cloudflare) — fecha R11 | `docs/security/risk-matrix.md` (R11) |
| Rotação de `EMAIL_HOST_PASSWORD`/`TURNSTILE_SECRET_KEY` — risco avaliado e aceito conscientemente pelo dono do projeto, não rotacionado | ADR-030 (decisão registrada com data e justificativa) |

## O que falta

Nada crítico pendente pra entrega. Checklist de entrega do `README.md` conferido item a item —
ver seção correspondente lá.
