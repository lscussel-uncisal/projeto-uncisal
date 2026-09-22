# Backup e Recuperação

Cobre o risco R10 de `risk-matrix.md`: a Oracle Cloud Free Tier não garante SLA de durabilidade
de disco, e o banco é um único arquivo SQLite — perder a VM sem backup externo perde todos os
chamados e contas cadastradas.

## Status

✅ Implementado e configurado em produção (`apps/backup`, ver ADR-030). Bucket privado
`bkp-uncisal` no Cloudflare R2, criado com "Public Access: Disabled"; token de API do tipo
**Account API Token** (não fica preso a nenhuma conta de pessoa), permissão só **Object Read &
Write**, escopo restrito a esse bucket, e **filtrado por IP** (só aceita requisições vindas do
IP fixo do servidor, `163.176.75.32`) — mesmo que a credencial vazasse, não daria pra usá-la de
outro lugar. Testado com sucesso via botão "Backup agora" (Administração → Backup) em
2026-09-22. Sem as variáveis de ambiente configuradas, `settings.BACKUP_ENABLED = False` e a
tela mostra um aviso — não quebra o resto da aplicação (mesmo padrão do Turnstile).

## O que é salvo

- `db.sqlite3` inteiro (contém: hashes de senha — já seguros por si só —, segredo TOTP **já
  criptografado** em repouso, dados dos chamados, auditoria de login).
- `media/` **não** está incluído hoje de propósito — o projeto ainda não tem nenhuma feature de
  upload (ver `CLAUDE.md`), então a pasta está sempre vazia; o código deixa espaço pra incluir
  isso depois se um dia ganhar upload.
- `.env` de produção — **não** faz parte deste backup automatizado; guardar separadamente, uma
  única vez, em um gerenciador de senhas (1Password/Bitwarden ou similar), não em texto solto.

## Como funciona (implementado)

1. **Frequência:** diária às 02:00, via um container sidecar dedicado (`docker-compose.yml`,
   serviço `backup`) rodando `docker/scripts/backup-scheduler.sh` — um loop de shell simples
   (sem cron/supervisord dentro do container, mais fácil de auditar). Ver também o botão
   "Backup agora" no menu Administração → Backup, síncrono, para rodar fora do horário agendado.
2. **Snapshot consistente:** `sqlite3.Connection.backup()` (API nativa do Python `sqlite3`,
   equivalente ao `.backup` do CLI) — nunca um `cp`/`shutil.copy` direto do arquivo, que
   poderia capturar uma escrita no meio do caminho (`apps/backup/services.py BackupService`).
3. **Criptografia do backup:** Fernet (biblioteca `cryptography`, já uma dependência do projeto
   por causa do `EncryptedCharField`) com uma chave **dedicada** (`BACKUP_ENCRYPTION_KEY`) —
   nunca reaproveita `FIELD_ENCRYPTION_KEY` (essa é só pro segredo TOTP; propósitos diferentes
   não compartilham chave). Decisão de usar Fernet em vez de `gpg` (design original desta
   página): evita instalar o binário GnuPG na imagem Docker só pra isso, quando a dependência
   criptográfica já existe no projeto — ver ADR-030.
4. **Destino:** Cloudflare R2 (bucket privado, prefixo `bkp_uncisal/` dentro dele), fora da VM —
   protege contra perda de disco/instância da Oracle Cloud Free Tier (sem SLA de durabilidade).
5. **Retenção:** mantém os `BACKUP_RETENTION_COUNT` (padrão 7) objetos mais recentes no prefixo;
   `BackupService._enforce_retention` apaga os mais antigos a cada execução bem-sucedida.
6. **Histórico consultável:** cada execução (manual ou agendada) grava um `BackupRun` — visível
   em Administração → Backup, para admin/super-admin.

## Como habilitar em produção

O deploy sobrescreve o `.env` do servidor a partir do **GitHub Secret `ENV_FILE`** a cada push
(`.github/workflows/deploy.yml`) — editar o `.env` direto no servidor via SSH funciona até o
próximo deploy, que apaga a mudança. Editar o secret `ENV_FILE` (Settings → Secrets and
variables → Actions, no GitHub) acrescentando as linhas de `.env.example`:

```
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_BACKUP_PREFIX=bkp_uncisal
BACKUP_ENCRYPTION_KEY=
BACKUP_RETENTION_COUNT=7
```

- `R2_ACCOUNT_ID`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`: criar um token de API do R2 em
  dash.cloudflare.com → R2 → "Manage API tokens", permissão **Object Read & Write**, escopo
  restrito só ao bucket usado aqui (nunca "Admin Read & Write" em todos os buckets).
- `BACKUP_ENCRYPTION_KEY`: gerar uma vez e nunca perder — sem ela nenhum backup existente pode
  ser restaurado: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- `R2_BUCKET_NAME`/`R2_BACKUP_PREFIX`: o bucket precisa existir antes (criar em dash.cloudflare.com
  → R2 → "Create bucket", privado — R2 não tem bucket público por padrão a menos que configurado
  explicitamente).

## Teste de restauração

Backup que nunca foi restaurado em teste não é um backup confiável, é uma suposição. Antes da
entrega final, baixar um objeto do bucket e:

```bash
python -c "
from cryptography.fernet import Fernet
f = Fernet(b'SUA_BACKUP_ENCRYPTION_KEY')
open('restaurado.sqlite3', 'wb').write(f.decrypt(open('db-XXXXXXXX.sqlite3.enc', 'rb').read()))
"
sqlite3 restaurado.sqlite3 "SELECT COUNT(*) FROM accounts_user;"
```

E confirmar que o número bate com o esperado.

## O que explicitamente NÃO faz parte do backup

- Segredos (`SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `TURNSTILE_SECRET_KEY` etc.) não devem estar no
  mesmo arquivo/rotina do backup do banco — ver `docs/security/nao-commitar.md`. Eles vivem no
  `.env`, que é responsabilidade de gestão separada (gerenciador de senhas), não de backup
  automatizado recorrente.
