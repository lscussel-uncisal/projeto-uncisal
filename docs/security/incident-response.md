# Plano de Resposta a Incidentes

Prevenção não é garantia. Este runbook cobre o "e se, mesmo assim, acontecer" — baseado nas
fases clássicas de resposta a incidente (detecção, contenção, erradicação, recuperação, lições
aprendidas), aplicadas aos cenários realistas deste projeto (ver `risk-matrix.md`).

## Contatos e responsabilidades

Projeto de aluno único — mesma pessoa acumula os papéis abaixo. Registrado mesmo assim porque é
assim que se documenta em qualquer projeto real.

| Papel | Responsável |
|---|---|
| Dono da aplicação / decisão final | Aluno |
| Operação de infraestrutura (Oracle Cloud, Cloudflare, DNS) | Aluno |
| Contato de e-mail para reporte externo de vulnerabilidade | Ver `SECURITY.md` |

## Cenário 1 — Segredo vazou no repositório (commit com credencial real)

**Detecção:** alerta do GitHub Secret Scanning, alerta do `gitleaks` no CI, ou percepção manual.

**Contenção (imediata, nesta ordem):**
1. Revogar/rotacionar a credencial vazada na origem (Cloudflare, Gmail, Oracle, GitHub — o que
   for). Um segredo visto em texto público é considerado comprometido, não importa por quanto tempo.
2. Se for `SECRET_KEY` do Django: gerar uma nova e atualizar no `.env` do servidor — isso invalida
   todas as sessões ativas (login forçado de todo mundo, efeito colateral aceitável).
3. Se for `FIELD_ENCRYPTION_KEY`: **não sobrescrever sem migrar os dados antes** — trocar essa
   chave sem re-criptografar os registros existentes os torna ilegíveis (o campo falha alto, não
   silenciosamente — ver `apps/core/fields.py`). Gerar a nova chave, mas só aplicar após um script
   de re-criptografia (descriptografar com a antiga, gravar com a nova).
4. Remover a credencial do histórico do git (`git filter-repo` ou BFG) **depois** de já tê-la
   revogado — remover do histórico sem revogar não resolve nada, a credencial já pode ter sido
   copiada.

**Erradicação:** identificar como o segredo entrou no commit (revisar se `CLAUDE.md`/pre-commit
foram ignorados, se foi `--no-verify`) e corrigir a causa antes de continuar desenvolvendo.

**Recuperação:** confirmar que a aplicação sobe normalmente com as credenciais novas
(`docker compose up`, checar `/healthz/`).

**Lições aprendidas:** registrar um ADR em `docs/architecture/decisions.md` descrevendo o que
vazou, como foi contido, e se alguma camada de defesa (pre-commit, CI) falhou em pegar — se
falhou, essa é a prioridade de correção seguinte.

## Cenário 2 — Força bruta detectada (login ou 2FA)

**Detecção:** `LoginAttempt` acumulando muitas falhas para o mesmo `attempted_username`/IP em
pouco tempo (consultável via Django admin), ou Fail2Ban banindo IPs repetidamente no servidor.

**Contenção:** o `LoginThrottleService` já bloqueia automaticamente (temporário, por janela de
tempo — ver `risk-matrix.md` R02/R03). Se o ataque persistir vindo de poucos IPs, bloquear
manualmente na Cloudflare (Firewall Rules) — mais eficiente que deixar chegar à aplicação.

**Erradicação/Recuperação:** se alguma conta específica foi alvo consistente, considerar forçar
troca de senha nela (`user.set_unusable_password()` + fluxo de redefinição) mesmo que o ataque não
tenha tido sucesso, por precaução.

## Cenário 3 — Usuário recebeu o alerta de "2FA incorreto" e NÃO foi ele

Este é o cenário que a própria aplicação foi desenhada para provocar (ver `owasp-mitigations.md`,
A07/A09). Fluxo esperado, do lado do usuário:

1. E-mail de alerta chega com instrução clara para trocar a senha imediatamente.
2. Usuário troca a senha (invalida a sessão atual, se implementado com `update_session_auth_hash`
   ou logout forçado).
3. Opcionalmente, reconfigurar o 2FA do zero (novo `TwoFactorDevice`, secret antigo descartado).

Do lado do sistema, nada de manual é necessário além de garantir que o e-mail realmente saia (ver
Cenário 5).

## Cenário 4 — Suspeita de comprometimento do servidor (VM Oracle Cloud)

**Detecção:** Fail2Ban com volume anômalo de bans, processo desconhecido, tráfego de saída
inesperado, alerta da própria Oracle Cloud.

**Contenção:**
1. Isolar a instância (Security List temporária bloqueando tudo, ou desligar a VM) — priorizar
   conter antes de investigar, mesmo que isso derrube a aplicação.
2. Rotacionar **todas** as credenciais que aquele servidor conhecia: `SECRET_KEY`,
   `FIELD_ENCRYPTION_KEY` (com o cuidado do Cenário 1), `TURNSTILE_SECRET_KEY`, senha de app do
   Gmail, e a própria chave SSH (gerar um novo par, remover a antiga do `authorized_keys`).

**Erradicação:** não tentar "limpar" uma VM comprometida — provisionar uma instância nova do zero
(Free Tier permite) e reaplicar `docs/infra/` do início. Restaurar dados só a partir do backup
mais recente **anterior** ao indício de comprometimento (ver `backup-recovery.md`).

**Recuperação:** redeploy via o pipeline normal (`git push origin main`) após o `.env` novo estar
no servidor novo.

## Cenário 5 — Falha silenciosa no envio de e-mail de alerta

**Risco:** se o SMTP falhar e a exceção for engolida, o usuário nunca é avisado de uma tentativa
de invasão — a mitigação de A09 vira decorativa sem ninguém perceber.

**Contenção prevista no código:** a chamada de envio de e-mail deve estar em `try/except`
(`smtplib.SMTPException`) que **loga o erro** (nível `ERROR`, nunca engole silenciosamente) mesmo
que a resposta ao usuário permaneça genérica — ver item 8 da tabela 5W2H em `risk-matrix.md`.

**Detecção:** checar logs do container (`docker compose logs web`) periodicamente, ou — se o tempo
do projeto permitir — configurar `ADMINS`/`SERVER_EMAIL` do Django para receber os erros 500
também por e-mail.
