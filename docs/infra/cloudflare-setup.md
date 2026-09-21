# Configuracao — Cloudflare (DNS, Proxy, Turnstile)

## Dominio

- Dominio raiz: `lserpsistemas.com.br` (registrado via Registro.br, marca registrada no INPI).
  **Reservado para uma futura pagina institucional** — fora do escopo deste projeto.
- Subdominio da aplicacao: **`uncisal.lserpsistemas.com.br`** (este projeto).
- Nameservers apontados para a Cloudflare em 2026-09-20; zona confirmada `Active`.

## Checklist

- [x] Site (zona) `lserpsistemas.com.br` adicionado ao Cloudflare (plano Free)
- [x] Nameservers do Registro.br atualizados para os da Cloudflare
- [x] Registro `A` de `uncisal` → `163.176.75.32`, proxy **ativado** (nuvem laranja) — o `@`/raiz
      fica sem registro por enquanto, reservado para a pagina institucional futura
- [x] Bot Fight Mode habilitado
- [x] Minimum TLS Version: `1.0` (default inseguro) → **`1.2`**
- [x] Cloudflare Managed Ruleset (WAF) — ja vem ativo por padrao no plano Free
- [x] Browser Integrity Check — ja vem ativo por padrao
- [x] Email Address Obfuscation — ja vem ativo por padrao
- [x] TLS 1.3, Opportunistic Encryption, Automatic HTTPS Rewrites — ja vem ativo por padrao
- [x] DNSSEC — habilitado na Cloudflare (2026-09-20); DS record cadastrado no Registro.br,
      aguardando propagacao (confirmar depois com `Resolve-DnsName -Type DS -Server 8.8.8.8`)
- [ ] SSL/TLS mode: hoje em **`Full`** (nao strict) — sobe para **`Full (strict)`** so depois que
      o Certbot emitir certificado real no servidor (ver `oracle-cloud-setup.md`, secao 9-10, e o
      vhost real em `docker/nginx/helpdesk.conf`)
- [ ] HSTS na Cloudflare — **de proposito ainda nao habilitado**: exige HTTPS confiavel na origem
      primeiro; habilitar cedo demais pode travar acesso se a origem falhar no meio da configuracao
- [ ] Authenticated Origin Pulls (mTLS) — depois do Full (strict)
- [ ] UFW no servidor restrito aos ranges de IP da Cloudflare em 80/443 (hoje esta aberto pra
      qualquer origem nessas portas — ver `docs/infra/ssh-hardening.md`)
- [ ] Nginx configurado para restaurar o IP real do visitante (`CF-Connecting-IP`)
- [x] Cloudflare Turnstile criado (widget `central-chamados-uncisal`, hostnames
      `uncisal.lserpsistemas.com.br` + `localhost`) e integrado no formulario de login
- [ ] Teste publico executado (Qualys SSL Labs — nota A + suporte a PQC)

## Registros de DNS existentes (nao mexer)

Vieram configurados por padrao (provavelmente do proprio Registro.br) e sao uma boa pratica —
travam o dominio contra spoofing de e-mail, mesmo nao usando e-mail nenhum:

| Nome | Tipo | Conteudo | Por que manter |
|---|---|---|---|
| `lserpsistemas.com.br` | MX | `.` | MX nulo (RFC 7505) — declara formalmente "este dominio nao recebe e-mail" |
| `lserpsistemas.com.br` | TXT | `v=spf1 -all` | SPF: nenhum servidor autorizado a enviar e-mail como este dominio |
| `_dmarc.lserpsistemas.com.br` | TXT | `v=DMARC1; p=reject;` | Rejeita e-mail que falhe autenticacao — anti-phishing |

O painel de "Recommendations" da Cloudflare sugere criar A/AAAA/CNAME para `www` e para a raiz —
**ignorar as duas**: nem `www` nem a raiz fazem parte do plano (raiz reservada pra pagina
institucional futura).

## DNSSEC — por que habilitar

Sem DNSSEC, nada impede um atacante em posição de rede privilegiada (ex.: Wi-Fi público malicioso,
provedor comprometido) de forjar respostas DNS para `lserpsistemas.com.br` e redirecionar
visitantes para um servidor falso — o cadeado HTTPS nem entraria em jogo, porque o navegador
nunca chegaria no site real. DNSSEC assina criptograficamente as respostas DNS, permitindo que o
resolver do visitante detecte e rejeite respostas adulteradas.

Configuracao (gratuita no plano Free):
1. Cloudflare gera o par de chaves da zona e mostra os dados do **DS record**
   (Key Tag, Algorithm, Digest Type, Digest).
2. Esses dados precisam ser publicados no **pai** da zona — nesse caso, o Registro.br, dono do
   `.com.br` — porque é isso que faz a cadeia de confianca do DNSSEC funcionar (o resolver confia
   na raiz, a raiz confia no `.br`, o `.br` confia na Cloudflare via esse DS record).
3. Propagacao pode levar ate 1 hora. Confirmar com:
   ```powershell
   Resolve-DnsName -Name lserpsistemas.com.br -Type DS -Server 8.8.8.8
   ```
   Um DS record retornado confirma que propagou; enquanto isso, a consulta volta so com o SOA do
   `.com.br` (resposta negativa padrao).

**Risco explicito assumido:** um DS record incorreto quebra a resolucao do dominio inteiro para
qualquer resolver que valide DNSSEC (a maioria dos publicos, como 1.1.1.1 e 8.8.8.8) — por isso os
valores foram copiados diretamente da tela da Cloudflare (nunca digitados a mao) antes de salvar
no Registro.br.

## Security Level

A Cloudflare descontinuou o controle manual — "the security level is now fully automated and is
set to 'always protected' by default". Nada a configurar aqui.

## Chaves do Turnstile

Ver [`docs/security/nao-commitar.md`](../security/nao-commitar.md): a `SITE_KEY` pode aparecer aqui
(é publica), a `SECRET_KEY` nunca — fica apenas no `.env` do servidor / GitHub Secrets.

## Verificado e nao vale a pena por enquanto

- **Rate Limiting Rules** e **Page Shield** existem no plano Free, mas com escopo limitado.
  Melhor avaliar depois que a aplicacao real estiver publicada (paths reais de login/API para
  mirar as regras) — configurar agora seria adivinhar rotas que ainda nao existem.

## Proximos passos (em ordem)

1. Publicar a aplicacao real no servidor (`docker compose up`) + vhost real do Nginx
   (`docker/nginx/helpdesk.conf`) com `server_name uncisal.lserpsistemas.com.br`.
2. Rodar Certbot no servidor para emitir certificado real (funciona com o modo `Full` atual —
   o desafio HTTP-01 passa pela Cloudflare normalmente).
3. Subir o modo SSL/TLS para `Full (strict)`.
4. Habilitar HSTS na Cloudflare.
5. Restringir UFW/Security List aos ranges de IP da Cloudflare em 80/443 + Authenticated Origin
   Pulls (mTLS).
6. ~~Criar o Turnstile e integrar no login/cadastro.~~ Feito — falta so integrar no cadastro
   quando essa tela existir.
7. Rodar o teste do Qualys SSL Labs.
