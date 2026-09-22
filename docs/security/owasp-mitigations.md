# Mitigações — OWASP Top 10:2025

> Base para a seção correspondente do `README.md` (requisito obrigatório do Eixo 3: no mínimo
> 3 categorias, com indicação de onde/como o código mitiga cada uma).

## As 10 categorias oficiais (confirmadas em top10.owasp.org/2025)

| Código | Categoria | Tradução |
|---|---|---|
| A01 | Broken Access Control | Quebra de Controle de Acesso |
| A02 | Security Misconfiguration | Configuração Incorreta de Segurança |
| A03 | Software Supply Chain Failures | Falhas na Cadeia de Suprimentos de Software |
| A04 | Cryptographic Failures | Falhas Criptográficas |
| A05 | Injection | Injeção |
| A06 | Insecure Design | Design Inseguro |
| A07 | Authentication Failures | Falhas de Autenticação |
| A08 | Software or Data Integrity Failures | Falhas de Integridade de Software ou Dados |
| A09 | Security Logging and Alerting Failures | Falhas de Registro e Alerta de Segurança |
| A10 | Mishandling of Exceptional Conditions | Tratamento Inadequado de Condições Excepcionais |

## As 5 categorias escolhidas — status: implementadas e documentadas

> Decisão final tomada e fechada (não é mais uma análise de custo prévia à implementação — as
> 5 abaixo estão implementadas, testadas e copiadas para a tabela do `README.md`).

| Categoria | Onde | Como |
|---|---|---|
| **A01 — Broken Access Control** (Quebra de Controle de Acesso) | `apps/accounts/permissions.py` (`role_required`), `apps/tickets/services.py`/`apps/accounts/services.py` (`UserAdminService`) | RBAC sempre checado no backend, nunca em dado do cliente. Hierarquia de papéis (super-admin > admin > suporte > usuário) com prevenção explícita de escalonamento de privilégio: `UserCreateForm.clean_role` + `UserAdminService.creatable_roles` rejeitam um admin tentando criar/forjar uma conta super-admin mesmo via POST direto (não só escondendo a opção no formulário), e `UserAdminService.visible_to` faz admin comum receber 404 (nunca 403, pra não nem confirmar a existência da conta) ao tentar agir sobre uma conta super-admin. |
| **A07 — Authentication Failures** (Falhas de Autenticação) | `apps/accounts/services.py` (`TwoFactorService`, `LoginThrottleService`, `TurnstileService`) | 2FA (TOTP/e-mail) + Cloudflare Turnstile + *rate limiting* no login e na verificação do código 2FA (`LoginThrottleService`, cobre `INVALID_CREDENTIALS` e `INVALID_2FA` pelo mesmo mecanismo) — sem isso, o código de 6 dígitos seria atacável por força bruta. |
| **A09 — Security Logging and Alerting Failures** (Falhas de Registro e Alerta de Segurança) | `apps/accounts/models.py` (`LoginAttempt`), tela "Relatório de login" (`LoginReportView`) | Auditoria de toda tentativa de login/2FA/recuperação de senha, inclusive contra e-mails inexistentes (detecção de enumeração); alerta por e-mail em login bem-sucedido e em código 2FA incorreto (`AccountNotificationService`). Consultável, restrita a admin/super-admin. |
| **A05 — Injection** (Injeção) | ORM do Django (todo o projeto), autoescape de template | Nenhum `.raw()`/SQL com string interpolada em código de aplicação; nenhum `\|safe`/`mark_safe` em conteúdo de usuário — verificado ao vivo com payload de script numa descrição de chamado, sai escapado (`&lt;script&gt;...`), nunca executa. |
| **A04 — Cryptographic Failures** (Falhas Criptográficas) | `config/settings/base.py` (`PASSWORD_HASHERS`), `apps/core/fields.py` (`EncryptedCharField`), `apps/backup/services.py` | Argon2id como hasher de senha (1ª posição em `PASSWORD_HASHERS`); segredo TOTP e backup do banco cifrados em repouso, cada um com sua própria chave Fernet dedicada (nunca reaproveitada entre os dois); `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/HSTS em `prod.py`. |

## As 5 descartadas — e por quê

Analisadas e conscientemente deixadas de fora (não são "esquecidas" — o retorno de documentá-las
como categoria separada não compensava o esforço, dado o que as 5 acima já cobrem):

| Categoria | Por que ficou de fora |
|---|---|
| A02 — Security Misconfiguration (Configuração Incorreta de Segurança) | Sobrepõe com A04 na prática (`DEBUG=False`, headers de segurança e `SECRET_KEY` fail-fast já cobertos ali). |
| A03 — Software Supply Chain Failures (Falhas na Cadeia de Suprimentos de Software) | Já coberto por `.github/dependabot.yml` + `pip-audit` no CI — mitigado, mas documentar como 6ª categoria não agregava narrativa nova. |
| A06 — Insecure Design (Design Inseguro) | Sobrepõe muito com A01 na prática; separá-la exigiria uma narrativa de design mais abstrata sem código novo claramente associado. |
| A08 — Software or Data Integrity Failures (Falhas de Integridade de Software ou Dados) | Exigiria assinatura de commits, pin de digest de imagem Docker, pin de SHA das GitHub Actions — esforço real para um ganho de relatório pequeno neste escopo. |
| A10 — Mishandling of Exceptional Conditions (Tratamento Inadequado de Condições Excepcionais) | Também implementado na prática (páginas de erro customizadas + `try/except` ao redor de Turnstile/SMTP), mas não entrou nas 5 "oficiais" por já haver 5 mais centrais à identidade do projeto (chamados + RBAC + 2FA). |
