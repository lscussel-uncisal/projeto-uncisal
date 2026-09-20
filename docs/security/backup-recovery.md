# Backup e Recuperação

Cobre o risco R10 de `risk-matrix.md`: a Oracle Cloud Free Tier não garante SLA de durabilidade
de disco, e o banco é um único arquivo SQLite — perder a VM sem backup externo perde todos os
chamados e contas cadastradas.

## Status

🔴 Pendente de implementação (documentado agora para já nascer com o deploy; ver item 6 do
plano 5W2H em `risk-matrix.md`).

## O que precisa ser salvo

- `db.sqlite3` (contém: hashes de senha — já seguros por si só —, segredo TOTP **já criptografado**
  em repouso, dados dos chamados).
- `.env` de produção — **não** como backup rotineiro junto do banco; guardar separadamente, uma
  única vez, em um gerenciador de senhas (1Password/Bitwarden ou similar), não em texto solto.

## Estratégia proposta

1. **Frequência:** diária (cron na VM), fora do horário de maior uso (irrelevante aqui, mas é a
   prática correta a documentar).
2. **Como:** `sqlite3 db.sqlite3 ".backup '/tmp/backup.sqlite3'"` (comando nativo do SQLite —
   consistente mesmo com o banco em uso, ao contrário de um `cp` direto do arquivo).
3. **Criptografia do backup:** `gpg --symmetric --cipher-algo AES256` antes de sair da VM — o
   arquivo de backup tem os mesmos dados sensíveis do banco original, não faz sentido protegê-lo
   a menos no repouso e desprotegê-lo em trânsito/no destino.
4. **Destino:** fora da própria VM (backup que fica só no mesmo disco não protege contra perda de
   disco/instância). Opções dentro de free tier: bucket gratuito (Oracle Object Storage tem camada
   Always Free; Cloudflare R2 também tem tier gratis), ou — solução mínima para o escopo acadêmico
   — enviar o arquivo cifrado para si mesmo pela conta Gmail dedicada do projeto.
5. **Retenção:** manter os últimos 7 backups diários (suficiente para o escopo do projeto; um
   ambiente real definiria política maior).

## Teste de restauração

Backup que nunca foi restaurado em teste não é um backup confiável, é uma suposição. Antes da
entrega final, fazer pelo menos uma vez:

```bash
gpg --decrypt backup.sqlite3.gpg > restaurado.sqlite3
sqlite3 restaurado.sqlite3 "SELECT COUNT(*) FROM accounts_user;"
```

E confirmar que o número bate com o esperado.

## O que explicitamente NÃO faz parte do backup

- Segredos (`SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `TURNSTILE_SECRET_KEY` etc.) não devem estar no
  mesmo arquivo/rotina do backup do banco — ver `docs/security/nao-commitar.md`. Eles vivem no
  `.env`, que é responsabilidade de gestão separada (gerenciador de senhas), não de backup
  automatizado recorrente.
