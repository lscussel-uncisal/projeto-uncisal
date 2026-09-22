# Gestão de Risco — Central de Chamados

Este projeto é tratado como projeto, não como exercício isolado: os riscos abaixo foram
levantados considerando a aplicação em produção (mesmo sendo avaliação acadêmica), e o plano
de ação usa 5W2H (What/Why/Where/When/Who/How/How much) para cada mitigação relevante.

## Matriz de risco

Probabilidade e Impacto em Baixa/Média/Alta/Crítica. Nível = combinação das duas.

| ID | Risco | Categoria relacionada | Prob. | Impacto | Nível | Mitigação | Status |
|---|---|---|---|---|---|---|---|
| R01 | Vazamento de credencial real no repositório público | A02 / requisito Eixo 2 | Média | Alto | **Alto** | `.gitignore`, `gitleaks` (pre-commit + CI), secrets só via `.env`/GitHub Secrets, `CLAUDE.md` como guarda-corrimão para o agente de IA | ✅ Implementado |
| R02 | Força bruta / credential stuffing no login | A07 | Alta | Alto | **Alto** | `LoginThrottleService` (bloqueio por username e por IP), política de senha (mín. 10 caracteres, `CommonPasswordValidator`) | ✅ Implementado |
| R03 | Força bruta no código de 2FA | A07 | Média | Alto | **Alto** | Mesmo `LoginThrottleService` (já cobre `INVALID_2FA`), janela curta do TOTP (30s), alerta por e-mail em código incorreto (`TwoFactorService.send_wrong_code_alert`) | ✅ Implementado — `TwoFactorVerifyView`, TDD completo (login TOTP/e-mail, throttle, falha de SMTP) |
| R04 | Escalonamento de privilégio entre papéis (usuário acessando chamado de outro, ou herdando permissão de admin) | A01 | Média | Alto | **Alto** | `TicketService.visible_to`/`can_edit`, autorização sempre no backend (nunca em dado vindo do form) | ✅ Implementado — leitura e escrita (criar/editar) cobertas, TDD completo |
| R05 | Configuração insegura esquecida em produção (`DEBUG=True`, headers ausentes, segredo fraco) | A02 | Média | Alto | **Alto** | Settings por ambiente, fail-fast em `prod.py`, checklist em `docs/infra/` | ✅ Implementado |
| R06 | Vazamento do segredo TOTP via dump/backup do banco | A04 | Baixa | Alto | **Médio** | `EncryptedCharField` (Fernet) com `FIELD_ENCRYPTION_KEY` dedicada | ✅ Implementado |
| R07 | Comprometimento do servidor via SSH (senha fraca/força bruta) | Infra | Alta | Crítico | **Crítico** | Chave SSH obrigatória, `PasswordAuthentication no`, Fail2Ban (4 tentativas / ban 24h), UFW menor privilégio | ✅ Implementado — Fail2Ban já baniu 1 IP minutos após o servidor ficar público |
| R08 | Bypass da Cloudflare acessando o servidor de origem diretamente | A05-adjacent / Infra | Média | Alto | **Alto** | UFW liberando 80/443 só para ranges de IP da Cloudflare, Authenticated Origin Pulls (mTLS) | ✅ Implementado — UFW restrito aos ranges da Cloudflare (testado: acesso direto ao IP dá timeout), Authenticated Origin Pulls ativo dos dois lados (testado: sem certificado dá 400). Sobreviveu a reboot completo do servidor |
| R09 | Dependência com vulnerabilidade conhecida (supply chain) | A03 | Média | Médio–Alto | **Médio** | Dependabot semanal (pip/Docker/Actions) + `pip-audit` no CI a cada push | ✅ Implementado |
| R10 | Perda de dados (corrupção/exclusão do SQLite, falha da VM Free Tier — sem SLA) | Continuidade | Média | Alto | **Alto** | Backup automatizado, criptografado, fora do servidor (ver `backup-recovery.md`) | ✅ Implementado e confirmado em produção — bucket privado `bkp-uncisal` no Cloudflare R2, token de API restrito a esse bucket + ao IP do servidor, backup manual testado com sucesso via Administração → Backup em 2026-09-22 |
| R11 | Perda de acesso administrativo (chave SSH perdida, conta de nuvem/GitHub/Cloudflare comprometida) | Continuidade | Baixa | Crítico | **Alto** | 2FA em todas as contas de infraestrutura (GitHub já ativo), cópia da chave SSH privada em local seguro (não só no notebook) | ✅ Implementado — 2FA confirmado ativo em Oracle Cloud, Cloudflare e no Gmail dedicado (2026-09-22) |
| R12 | Exceção não tratada expõe detalhe interno (falha na chamada ao Turnstile ou ao SMTP) | A10 | Média | Médio | **Médio** | `DEBUG=False`, `try/except` ao redor de chamadas externas, página de erro genérica | ✅ Implementado — Turnstile (`TurnstileService`) e envio de e-mail (`TwoFactorService.send_email_code`/`send_wrong_code_alert`) cobertos, falha fechado sem vazar detalhe |

## Plano de ação (5W2H)

| # | O quê | Por quê | Onde | Quando | Quem | Como | Quanto custa |
|---|---|---|---|---|---|---|---|
| 1 | Bloqueio de força bruta no login | Mitigar R02 — login é o alvo mais óbvio de ataque automatizado | `apps/accounts/services.py`, `apps/accounts/views.py` | Concluído | Aluno (dev) | `LoginThrottleService` + `ThrottledLoginView`, testado via TDD | ~2h — feito |
| 2a | Turnstile no login | Reduz tráfego automatizado antes mesmo de checar credenciais | `apps/accounts/services.py`, `forms.py`, `views.py`, `templates/accounts/login.html` | Concluído | Aluno (dev) | `TurnstileService` (siteverify) + `TurnstileAuthenticationForm`, testado via TDD (mock) e validado no navegador com o widget real | ~2h — feito, $0 |
| 2b | Parede de 2FA (TOTP/e-mail) com alerta por e-mail em código incorreto | Fechar R03; é o requisito funcional que diferencia o projeto | `apps/accounts/views.py`, `templates/accounts/` | Concluído (2026-09-21) | Aluno (dev) | `TwoFactorService` (TOTP via `pyotp` + código por e-mail) + `ThrottledLoginView`/`TwoFactorVerifyView` + auto-cadastro opcional (`TwoFactorSetupView`/`TwoFactorConfirmSetupView`) com QR code | ~4h — feito, $0 |
| 3 | CRUD de escrita de chamados com RBAC consistente | Fechar R04 por completo (hoje só a leitura está protegida) | `apps/tickets/views.py`, `apps/tickets/forms.py` | Concluído (2026-09-21) | Aluno (dev) | `ModelForm`s separados por papel (`TicketCreateForm`, `TicketUserUpdateForm`, `TicketStaffUpdateForm`) + `TicketService.can_edit` checado antes de qualquer `save()` | ~3h — feito, $0 |
| 4 | Hardening SSH + Fail2Ban na VM | Fechar R07 — é meta mínima obrigatória da disciplina | Instância Oracle Cloud | Concluído (2026-09-20) | Aluno (infra) | Seguido `docs/infra/ssh-hardening.md` via SSH automatizado | ~1h — feito |
| 5 | UFW restrito a IPs Cloudflare + Authenticated Origin Pulls | Fechar R08 — sem isso, a Cloudflare/Turnstile podem ser contornados | VM + painel Cloudflare | Concluído (2026-09-21) | Aluno (infra) | UFW com 44 regras (ranges Cloudflare × 80/443) + Origin Pulls mTLS — ver ADR-027 | ~1h — feito, $0 |
| 6 | Backup automatizado do `db.sqlite3`, criptografado, fora da VM | Fechar R10 — Free Tier não garante durabilidade do disco | Sidecar Docker agendado + Cloudflare R2 | Concluído (2026-09-22) | Aluno (infra) | Ver `docs/security/backup-recovery.md` — inclui restauração de teste real | ~2h, $0 (dentro de free tiers) — feito |
| 7 | `pip-audit` no pipeline de CI | Reforçar R09 além do Dependabot (checa na hora do build, não só semanalmente) | `.github/workflows/security.yml` | Concluído | Aluno (dev) | Job `dependency-audit` novo, `pip-audit -r requirements.txt` | ~20min — feito |
| 8 | Páginas de erro customizadas (404/500) + `try/except` nas integrações externas | Fechar R12, só faz sentido junto com o item 2 | `templates/errors/`, `apps/accounts/services.py` | Concluído (2026-09-21) | Aluno (dev) | Templates simples sem stack trace + captura de `requests.RequestException` (Turnstile) e `OSError` (SMTP) — falha fechado, nunca 500 pro usuário | ~1h — feito, $0 |
| 9 | Confirmar 2FA ativo em todas as contas de infraestrutura (Oracle, Cloudflare, Gmail dedicado) | Fechar R11 | Contas externas (fora do código) | Concluído (2026-09-22) | Aluno (operação) | Ativar 2FA em cada painel | 15min, $0 — feito |
| 10 | Runbook de resposta a incidente | Sem isso, o restante da mitigação é só prevenção — falta o "e se acontecer mesmo assim" | `docs/security/incident-response.md` | Concluído | Aluno (dev) | Ver documento | Feito |

## Como isso se conecta com o restante do repositório

- Cada linha "Como" aponta para arquivo(s) específicos — quando implementado, o código deve
  citar de volta o risco (`R0X`) em comentário ou na ADR correspondente, mantendo rastreabilidade.
- Itens marcados 🔴/🟡 viram TODO explícito em `CLAUDE.md` para o agente de IA não perder de vista.
- `docs/security/owasp-mitigations.md` mantém o recorte específico exigido pela disciplina
  (mínimo 3 categorias); esta matriz é o quadro completo por trás dessa escolha.
