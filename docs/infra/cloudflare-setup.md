# Configuracao — Cloudflare (DNS, Proxy, Turnstile)

## Dominio

- Dominio raiz: `lserpsistemas.com.br` (registrado via Registro.br, marca registrada no INPI).
  **Reservado para uma futura pagina institucional** — fora do escopo deste projeto.
- Subdominio da aplicacao: **`uncisal.lserpsistemas.com.br`** (este projeto).
- Nameservers apontados para a Cloudflare em: _(preencher data)_

## Checklist

- [ ] Site (zona) `lserpsistemas.com.br` adicionado ao Cloudflare (plano Free) — a zona e sempre
      o dominio raiz, o subdominio e so um registro DNS dentro dela.
- [ ] Nameservers do Registro.br atualizados para os da Cloudflare
- [ ] Registro `A` de `uncisal` (nao do `@`/raiz) criado apontando para o IP publico da instancia,
      com proxy **ativado** (nuvem laranja) — o `@`/raiz fica sem registro por enquanto, reservado
      para a pagina institucional futura
- [ ] SSL/TLS mode = **Full (strict)**
- [ ] Certificado de origem: Certbot (Let's Encrypt) rodando no servidor
- [ ] Authenticated Origin Pulls habilitado (mTLS entre Cloudflare e o servidor)
- [ ] Regra de firewall / UFW no servidor liberando 80/443 apenas para os ranges de IP da Cloudflare (https://www.cloudflare.com/ips/)
- [ ] Nginx configurado para restaurar o IP real do visitante (`CF-Connecting-IP`) nos logs e no Fail2Ban
- [ ] Cloudflare Turnstile criado (site key + secret key) e integrado no formulario de login/cadastro
- [ ] Teste publico executado (Qualys SSL Labs — nota A + suporte a PQC)

## Chaves do Turnstile

Ver [`docs/security/nao-commitar.md`](../security/nao-commitar.md): a `SITE_KEY` pode aparecer aqui
(é publica), a `SECRET_KEY` nunca — fica apenas no `.env` do servidor / GitHub Secrets.

## Observacoes

_(a preencher)_
