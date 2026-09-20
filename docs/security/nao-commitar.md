# O que nunca pode ir para o repositório (mesmo sendo público)

Checklist de referência — usado pelo `CLAUDE.md` (guia do agente de IA) e pelos documentos de
`docs/infra/`. O requisito do Eixo 2 é explícito: vazamento de credencial real gera penalidade
imediata na avaliação.

## Nunca commitar, em hipótese alguma

| Item | Onde deve viver |
|---|---|
| `.env` (qualquer variante) | Apenas no servidor / máquina local, fora do git (`.gitignore` já cobre) |
| Chave privada SSH (`id_ed25519`, `*.pem`) | Chaveiro local / `ssh-agent`; a pública pode ser referenciada, a privada nunca |
| Chave privada do certificado de origem Cloudflare (se usar Origin CA) | Apenas em `/etc/ssl/private/` no servidor, permissão restrita |
| `TURNSTILE_SECRET_KEY` | `.env` no servidor / GitHub Secrets. A `SITE_KEY` (pública) pode aparecer no HTML/JS sem problema |
| Senha de app do Gmail (`EMAIL_HOST_PASSWORD`) | `.env` no servidor / GitHub Secrets |
| Chave SSH de deploy usada pelo GitHub Actions | GitHub Secrets (`SERVER_SSH_KEY`) — nunca em arquivo de workflow |
| `SECRET_KEY` do Django | `.env` no servidor / GitHub Secrets (ver `config/settings/prod.py`: sem valor, a app recusa iniciar) |
| `db.sqlite3` de produção (contém hashes de senha e dados de usuários reais) | Volume Docker no servidor, nunca versionado |
| Chave de API de assinatura da Oracle Cloud (`*.pem` do OCI) e sua senha (se usada) | Local, fora do repositório |
| OCID de tenancy/usuário combinados com a chave de API acima | Evitar publicar; sozinhos têm baixo risco, mas não agregam valor ao relatório |

## Pode ir para o repositório (é exigido pela disciplina)

- IP público da instância e o domínio `uncisal.lserpsistemas.com.br` — a avaliação exige que estejam visíveis.
- Comandos exatos usados (UFW, Fail2Ban, Nginx, Certbot) — evidenciam o processo, sem expor segredo algum.
- `TURNSTILE_SITE_KEY` (chave pública do Turnstile).
- Estrutura de `.env.example` (chaves sem valores reais).

## Capturas de tela nos docs de infra

Antes de colar um screenshot em `docs/infra/*.md`, cobrir/recortar:

- OCID de tenancy, compartment ou usuário na Oracle Cloud
- E-mail de login das contas (Oracle, Cloudflare, GitHub, Gmail)
- Qualquer token ou chave que apareça momentaneamente na tela

## Defesas automatizadas configuradas neste repositório

1. `.gitignore` — bloqueia `.env`, `*.pem`, `*.key`, `db.sqlite3`.
2. `.pre-commit-config.yaml` — `detect-private-key` + `gitleaks` rodam antes de cada commit local.
3. `.github/workflows/security.yml` — `gitleaks` roda de novo em cada push/PR (defesa em profundidade,
   cobre o caso de alguém commitar com `--no-verify`).
4. GitHub Secret Scanning + Push Protection (nativo do GitHub para repositórios públicos).

Nenhuma dessas camadas é 100% infalível sozinha — por isso são quatro, não uma.
