# Hardening — Acesso SSH e Firewall

> Antes de colar comandos/capturas aqui, conferir [`docs/security/nao-commitar.md`](../security/nao-commitar.md)
> — em especial: nunca colar o conteudo da chave privada SSH, apenas a publica (se necessario).

## Checklist

- [ ] `PasswordAuthentication no` em `/etc/ssh/sshd_config`
- [ ] `PermitRootLogin no`
- [ ] Usuario nao-root dedicado, com `sudo`, usado para toda administracao
- [ ] Chave SSH (ed25519) gerada localmente, nunca a chave privada enviada ao servidor
- [ ] UFW: `deny incoming` por padrao, liberando apenas 22 (restrito, se possivel, ao IP do administrador), 80 e 443
- [ ] Fail2Ban:
  - `jail.local` configurado para `sshd`
  - `maxretry = 4`
  - `bantime = 24h`
  - `findtime` ajustado de forma coerente com o maxretry
- [ ] Atualizacoes automaticas de seguranca (`unattended-upgrades`) habilitadas

## Comandos de referencia

_(a preencher com os comandos exatos usados no servidor, para reprodutibilidade)_
