# Mitigações — OWASP Top 10:2025

> Base para a seção correspondente do `README.md` (requisito obrigatório do Eixo 3: no mínimo
> 3 categorias, com indicação de onde/como o código mitiga cada uma).

## As 10 categorias oficiais (confirmadas em top10.owasp.org/2025)

| Código | Categoria |
|---|---|
| A01 | Broken Access Control |
| A02 | Security Misconfiguration |
| A03 | Software Supply Chain Failures |
| A04 | Cryptographic Failures |
| A05 | Injection |
| A06 | Insecure Design |
| A07 | Authentication Failures |
| A08 | Software or Data Integrity Failures |
| A09 | Security Logging and Alerting Failures |
| A10 | Mishandling of Exceptional Conditions |

## Análise de custo/benefício para este projeto

| Categoria | Custo de implementação | Por quê |
|---|---|---|
| **A01 — Broken Access Control** | Zero (já construído) | RBAC via `apps/accounts/permissions.py` (`role_required`) e `apps/tickets/services.py` (`TicketService.visible_to`) — autorização sempre checada no backend, nunca confiando em dado do cliente. Hierarquia de papéis (super-admin > admin > suporte > usuário, `apps/accounts/models.py Role`) com prevenção explícita de escalonamento de privilégio: `UserCreateForm.clean_role` + `UserAdminService.creatable_roles` rejeitam um admin tentando criar/forjar uma conta super-admin mesmo via POST direto (não só escondendo a opção no formulário), e `UserAdminService.visible_to` faz admin comum receber 404 (nunca 403, pra não nem confirmar a existência da conta) ao tentar listar ou agir sobre uma conta super-admin. |
| **A09 — Security Logging and Alerting Failures** | Zero a baixo (já construído) | `apps/accounts/models.py` (`LoginAttempt`) já audita tentativas de login/2FA/recuperação de senha, inclusive contra e-mails inexistentes (detecção de enumeração); alerta por e-mail em 2FA incorreto e em todo login bem-sucedido (`AccountNotificationService`). Auditoria consultável via tela "Relatório de login" (`LoginReportView`), restrita a admin/super-admin. |
| **A05 — Injection** | Zero (decorrência do stack) | Django ORM elimina SQL injection por padrão (sem `raw()`/string interpolation); autoescape de template elimina XSS refletido (sem `\|safe` em input de usuário). Só precisa documentar a prática, nenhum código novo. |
| **A04 — Cryptographic Failures** | Baixo (~15 min) | Trocar hasher padrão por Argon2id (`pip install argon2-cffi`, 1a posição em `PASSWORD_HASHERS`); `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/HSTS já estão em `prod.py`. |
| **A02 — Security Misconfiguration** | Baixo (já em boa parte construído) | `DEBUG=False`, headers de segurança e `SECRET_KEY` fail-fast já em `prod.py`; falta só documentar. |
| **A07 — Authentication Failures** | Concluído | 2FA (TOTP/e-mail, `TwoFactorService`) + Turnstile + *rate limiting* no login e na verificação de 2FA (`LoginThrottleService`, cobre `INVALID_CREDENTIALS` e `INVALID_2FA` pelo mesmo mecanismo) — sem isso, o código de 6 dígitos seria atacável por força bruta. É o coração da aplicação. |
| **A10 — Mishandling of Exceptional Conditions** | Médio | Páginas customizadas de erro (404/500, sem stack trace) + `try/except` ao redor das chamadas externas (verificação do Turnstile, envio de e-mail via SMTP) para não vazar detalhe interno em caso de falha de rede/API. |
| A03 — Software Supply Chain Failures | Baixo, mas cosmético | Já coberto por `.github/dependabot.yml`. Poderia render mais com `pip-audit` no CI, mas o ganho de narrativa é menor que os itens acima. |
| A06 — Insecure Design | Alto para o retorno | Sobrepõe muito com A01 na prática; documentar como categoria separada exigiria uma narrativa de design mais abstrata sem código novo claramente associado. |
| A08 — Software or Data Integrity Failures | Alto para o retorno | Exigiria assinatura de commits, pin de digest de imagem Docker, pin de SHA das GitHub Actions — esforço real para um ganho de relatório pequeno neste escopo. |

## Recomendação

**As 3 obrigatórias:** A01 (Broken Access Control), A07 (Authentication Failures) e A09 (Security
Logging and Alerting Failures) — são as que mais se encaixam na identidade do projeto (chamados +
RBAC + 2FA com alerta) e a maior parte já está ou estará construída de qualquer forma.

**Bônus quase gratuito, se quiser passar de 3:** A05 (Injection) e A04 (Cryptographic Failures) —
custo somado de menos de meia hora, e mostram maturidade extra para uma avaliação de pós em
segurança.

## Pendente

- [x] Implementar rate limiting em login (`LoginThrottleService` + `ThrottledLoginView`)
- [x] Trocar hasher para Argon2id
- [x] Páginas de erro customizadas (403/404/500), sem stack trace
- [x] Cloudflare Turnstile integrado no login (`TurnstileService`, `TurnstileAuthenticationForm`),
      com `try/except` ao redor da chamada HTTP (falha fechado, nunca expõe o motivo real)
- [x] Parede de 2FA (TOTP + e-mail) com alerta por e-mail em código incorreto
      (`TwoFactorService`, `ThrottledLoginView`/`TwoFactorVerifyView`)
- [x] Rate limiting específico na etapa de verificação do código 2FA — reaproveita o mesmo
      `LoginThrottleService` (já contava `INVALID_2FA`, só faltava a tela chamá-lo)
- [x] `try/except` ao redor do envio de e-mail (`TwoFactorService.send_email_code`/
      `send_wrong_code_alert`, falha fechado — nunca deixa a exceção virar 500)
- [x] Confirmar com o usuário o conjunto final (3 ou 5 categorias) — 5 (A01, A07, A09 + A05, A04)
- [x] Apontar arquivo/linha exata de cada mitigação após a implementação
- [x] Copiar o resumo final para a tabela do `README.md` (2026-09-22)

Dado o volume já implementado, o conjunto final recomendado passa a ser 5 categorias:
**A01, A07, A09** (núcleo) + **A05, A04** (bônus já concluído/quase gratuito) — ver
`docs/security/risk-matrix.md` para o quadro de risco completo por trás dessa escolha.
