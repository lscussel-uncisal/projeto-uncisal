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
| **A01 — Broken Access Control** | Zero (já construído) | RBAC via `apps/accounts/permissions.py` (`role_required`) e `apps/tickets/services.py` (`TicketService.visible_to`) — autorização sempre checada no backend, nunca confiando em dado do cliente. |
| **A09 — Security Logging and Alerting Failures** | Zero a baixo (já construído) | `apps/accounts/models.py` (`LoginAttempt`) já audita tentativas de login/2FA; o alerta por e-mail em 2FA incorreto (feature já planejada) *é* a mitigação em ação. |
| **A05 — Injection** | Zero (decorrência do stack) | Django ORM elimina SQL injection por padrão (sem `raw()`/string interpolation); autoescape de template elimina XSS refletido (sem `\|safe` em input de usuário). Só precisa documentar a prática, nenhum código novo. |
| **A04 — Cryptographic Failures** | Baixo (~15 min) | Trocar hasher padrão por Argon2id (`pip install argon2-cffi`, 1a posição em `PASSWORD_HASHERS`); `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/HSTS já estão em `prod.py`. |
| **A02 — Security Misconfiguration** | Baixo (já em boa parte construído) | `DEBUG=False`, headers de segurança e `SECRET_KEY` fail-fast já em `prod.py`; falta só documentar. |
| **A07 — Authentication Failures** | Médio (núcleo do projeto) | 2FA (TOTP/e-mail) + Turnstile já são requisito funcional do projeto — mas só fica completo com *rate limiting* no login e na verificação de 2FA (sem isso, o código de 6 dígitos é atacável por força bruta). Vale o custo por ser o coração da aplicação. |
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
- [ ] Rate limiting específico na etapa de verificação do código 2FA (quando a tela existir)
- [ ] `try/except` ao redor do envio de e-mail (quando implementado)
- [ ] Confirmar com o usuário o conjunto final (3 ou 5 categorias)
- [ ] Apontar arquivo/linha exata de cada mitigação após a implementação
- [ ] Copiar o resumo final para a tabela do `README.md`

Dado o volume já implementado, o conjunto final recomendado passa a ser 5 categorias:
**A01, A07, A09** (núcleo) + **A05, A04** (bônus já concluído/quase gratuito) — ver
`docs/security/risk-matrix.md` para o quadro de risco completo por trás dessa escolha.
