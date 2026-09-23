# Cross-check: enunciado da disciplina × o que foi entregue

Confere, item a item, o [enunciado oficial](https://github.com/ziraldocardoso/Projeto_aplicado-praticas_de_mercado/blob/main/Escopo_e_elementos_obrigatorios.md)
("Escopo e Elementos Obrigatórios") contra o que está implementado neste repositório — com
referência exata de onde cada requisito é atendido, não só uma afirmação solta. Última
verificação: 2026-09-22.

## Eixo 1 — Infraestrutura (Cloud Computing, Free Tier)

| Requisito do enunciado | Atendido? | Onde/evidência |
|---|---|---|
| Provedor de nuvem gratuito (Free Tier), qualquer um | ✅ | Oracle Cloud Always Free — `docs/infra/oracle-cloud-setup.md` |
| SO: Ubuntu Server ou Debian, versão estável recente | ✅ | Ubuntu 24.04.4 LTS |
| Servidor Web: Nginx ou Apache | ✅ | Nginx — `docker/nginx/helpdesk.conf` |
| App acessível publicamente via IP público (domínio não é exigido) | ✅ (excede o pedido) | IP reservado `163.176.75.32` **e** domínio `uncisal.lserpsistemas.com.br` |
| Acesso administrativo só por chave SSH, sem senha | ✅ | `PasswordAuthentication no`, `PermitRootLogin no` — `docs/infra/ssh-hardening.md`, confirmado por auditoria em ADR-032 |
| Firewall expõe só as portas necessárias (least privilege) | ✅ | UFW `default deny incoming`; só 22 (SSH) e 80/443 (restritos aos ranges da Cloudflare) — ADR-027, auditado de novo em ADR-032 |
| Fail2Ban na porta 22, tolerância de 4 erros, banimento de 24h | ✅ (parâmetros exatos confirmados) | `jail.local`: `maxretry = 4`, `bantime = 24h` — `docs/infra/ssh-hardening.md` |
| Certbot ≥ 5.4, autorrenovação automática | ✅ | Certbot 5.8.0, timer systemd nativo (`snap.certbot.renew.timer`) — ADR-027 |
| Redirecionamento automático HTTP → HTTPS | ✅ | Nginx + Cloudflare — ADR-027 |
| Teste de TLS/SSL aprovado + PQC (branch por **domínio**, já que é o caso aqui): Qualys SSL Labs, nota mínima **A**, com PQC Key Exchange confirmado | ✅ (excede: nota **A+**) | 4 endpoints A+ (IPv4/IPv6), `X25519MLKEM768` confirmado — `docs/security/evidencias/qualys-ssl-report-2026-09-22.png`, ADR-027 |

## Eixo 2 — Repositório (GitHub)

| Requisito do enunciado | Atendido? | Onde/evidência |
|---|---|---|
| Repositório no GitHub, acesso público | ✅ | `github.com/lscussel-uncisal/projeto-uncisal`, `visibility: public` confirmado via API |
| Conta GitHub configurada com segurança: chave SSH ou PAT para commit/push | ✅ | HTTPS + Git Credential Manager (PAT), confirmado (`credential.helper = manager`) |
| 2FA na conta do GitHub (recomendação do enunciado, não obrigatório) | ✅ | Já ativo — `docs/security/risk-matrix.md` (R11) |
| README.md como relatório técnico da entrega | ✅ | `README.md` — arquitetura, stack, estrutura, risco, OWASP, checklist |
| `.gitignore` correto; proibido commit de `.env`, chave privada, credencial de nuvem, senha hardcoded, banco local | ✅ | `.gitignore` + hooks `gitleaks`/`detect-private-key` (pre-commit e CI) — `docs/security/nao-commitar.md` |
| Vazamento de credencial real = penalidade imediata | ✅ nenhum vazamento no repositório | Um incidente ocorreu **nesta conversa** (não no repositório): `docker compose config` expôs `EMAIL_HOST_PASSWORD`/`TURNSTILE_SECRET_KEY` em texto puro no chat local — nunca chegou a `.env` versionado nem a nenhum arquivo do repositório. Decisão registrada de não rotacionar (risco aceito) — ADR-030 |

## Eixo 3 — Desenvolvimento (Protótipo Web)

| Requisito do enunciado | Atendido? | Onde/evidência |
|---|---|---|
| Stack livre (qualquer linguagem/framework) | ✅ | Django 5 (Python) — ADR-001 |
| Codificação assistida por IA (IDE indicada: Google Antigravity, **ou ambiente similar baseado em IA**) | ✅ | Claude Code — explicitamente permitido pelo enunciado como alternativa; regras registradas em `CLAUDE.md` — ADR-006 |
| Tela de Login | ✅ | `templates/accounts/login.html` |
| Página interna, só acessível autenticado | ✅ | `tickets:list` e as demais telas pós-login (`LoginRequiredMixin`/`role_required` em toda view) |
| Botão de Logout funcional | ✅ | `accounts:logout`, no menu "Conta" |
| Mínimo 3 categorias do OWASP Top 10:2025 mitigadas, documentadas no README com onde/como | ✅ (5, acima do mínimo) | `README.md` → "Segurança — mitigações OWASP Top 10:2025"; detalhamento em `docs/security/owasp-mitigations.md` |

## Integração e Entrega Contínua (CI/CD)

| Requisito do enunciado | Atendido? | Onde/evidência |
|---|---|---|
| Pipeline automatizado via GitHub Actions, disparado por `git push origin main` | ✅ | `.github/workflows/deploy.yml`, `on: push: branches: [main]` |
| Deploy seguro pro ambiente de nuvem | ✅ | SSH com chave dedicada (`SERVER_SSH_KEY`), `concurrency` evita deploys concorrentes — ADR-023 |
| Nenhuma credencial exposta no código da pipeline; uso do recurso *Secrets* do GitHub | ✅ | 4 GitHub Secrets (`SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`, `ENV_FILE`) — nunca hardcoded no `.yml` |

## Checklist Final de Entrega do próprio enunciado (9 itens) — todos conferidos acima

1. App web no ar, IP público — ✅
2. Web server + HTTPS + redirect automático — ✅
3. Teste de TLS/SSL com nota A (mínimo) + PQC — ✅ (A+)
4. Chave SSH + Fail2Ban (porta 22) — ✅
5. Repositório público no GitHub, conta configurada (2FA incluído) — ✅
6. `.gitignore` sem segredo exposto — ✅
7. Login + página interna + logout, com IA (Antigravity ou equivalente) — ✅
8. README com as 3 (ou mais) categorias OWASP e onde estão — ✅
9. CI/CD automatizado via GitHub Actions — ✅

**Todos os requisitos obrigatórios do enunciado, nos 3 eixos e na
integração CI/CD, estão implementados e verificados** — a maioria com evidência real (comando
rodado, teste automatizado, ou captura de tela), não só declaração.
