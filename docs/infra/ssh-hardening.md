# Hardening — Acesso SSH e Firewall

> Antes de colar comandos/capturas aqui, conferir [`docs/security/nao-commitar.md`](../security/nao-commitar.md)
> — em especial: nunca colar o conteudo da chave privada SSH, apenas a publica (se necessario).

Pré-requisito: instância já criada (ver [`oracle-cloud-setup.md`](oracle-cloud-setup.md)), com o
par de chaves SSH associado na criação e o primeiro acesso já testado com o usuário padrão da
imagem (`ubuntu` no Ubuntu, `debian` no Debian).

## Checklist

- [x] Usuário não-root dedicado (`deploy`), usado para deploy — SEM sudo sem senha de propósito
      (não precisa: só roda `git pull`/`docker compose`, está no grupo `docker`)
- [x] `PasswordAuthentication no` em `/etc/ssh/sshd_config`
- [x] `PermitRootLogin no`
- [x] UFW: `deny incoming` por padrão, liberando apenas 22, 80 e 443
- [x] Fail2Ban: `jail.local` para `sshd`, `maxretry = 4`, `bantime = 24h` — já baniu 1 IP em minutos
- [x] Jail `recidive` (reincidência) habilitado: 3 bans/dia → 1 semana banido em todas as portas
- [x] Atualizações automáticas de segurança (`unattended-upgrades`) habilitadas

## 1. Criar usuário de administração dedicado

Feito logado como o usuário padrão da imagem (`ubuntu`/`debian`). Evita usar esse usuário genérico
(ou o `root`) no dia a dia.

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy      # Debian/Ubuntu: grupo "sudo"

# copiar a MESMA chave publica ja autorizada para o usuario novo
sudo rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Abra um **segundo** terminal (sem fechar o primeiro) e confirme que consegue logar como `deploy`
antes de continuar — se travar aqui e você já tiver fechado a sessão original, perde o acesso.

```bash
ssh -i caminho\para\sua_chave deploy@SEU_IP_PUBLICO
```

## 2. Endurecer o `sshd`

Já como `deploy`, com `sudo`:

```bash
sudo nano /etc/ssh/sshd_config
```

Garantir estas linhas (editar se já existirem, descomentadas):

```
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart ssh
```

**Antes de fechar o terminal atual**, abra um novo e confirme que ainda consegue logar como
`deploy` com a chave. Só depois disso é seguro assumir que a senha está realmente desabilitada.

## 3. UFW (firewall do host)

```bash
sudo apt update && sudo apt install -y ufw

sudo ufw default deny incoming
sudo ufw default allow outgoing

sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

sudo ufw enable      # confirmar com "y" — a sessao SSH atual NAO cai, a regra de 22 ja esta na lista
sudo ufw status verbose
```

> Isto é uma segunda camada, redundante de propósito com a Security List/NSG da Oracle Cloud (ver
> `oracle-cloud-setup.md`) — se uma falhar ou for mal configurada, a outra ainda protege.

## 4. Fail2Ban

```bash
sudo apt install -y fail2ban

sudo tee /etc/fail2ban/jail.local > /dev/null <<'EOF'
[sshd]
enabled = true
port = 22
filter = sshd
logpath = %(sshd_log)s
backend = %(sshd_backend)s
maxretry = 4
findtime = 10m
bantime = 24h
EOF

sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

`maxretry = 4` + `bantime = 24h`: exatamente a meta mínima da disciplina. `findtime = 10m` define
a janela em que essas 4 tentativas precisam ocorrer para contar como ataque.

### Jail reincidente (`recidive`) — escalonamento além do mínimo

O pacote do Fail2Ban já traz um jail pronto para reincidência, só não vem habilitado por padrão.
Um IP que é banido repetidamente (por qualquer jail) leva um ban muito mais longo, em todas as
portas, não só a que ele atacou:

```bash
sudo tee -a /etc/fail2ban/jail.local > /dev/null <<'EOF'

[recidive]
enabled = true
logpath = /var/log/fail2ban.log
banaction = %(banaction_allports)s
bantime = 1w
findtime = 1d
maxretry = 3
EOF

sudo systemctl restart fail2ban
sudo fail2ban-client status recidive
```

3 bans em 1 dia → 1 semana banido em todas as portas. Não usamos blocklist externa de bots
conhecidos (tipo Spamhaus) de propósito — a Cloudflare, na frente das portas 80/443, já cobre isso
com inteligência de ameaça mais atualizada do que qualquer lista estática configurada aqui.

## 5. Atualizações automáticas de segurança

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades   # responder "Yes"
```

## Verificação final

```bash
sudo ufw status verbose
sudo fail2ban-client status sshd
sudo sshd -T | grep -Ei "passwordauthentication|permitrootlogin"
```

Devem aparecer: `passwordauthentication no`, `permitrootlogin no`, UFW `active` com só 22/80/443
liberadas, Fail2Ban com a jail `sshd` ativa.
