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
- [x] SSL/TLS mode: **`Full (strict)`** — passou por `Flexible` temporariamente (necessario para
      o desafio HTTP-01 do Certbot: `Full` exige HTTPS valido origem-Cloudflare, que ainda nao
      existia) e voltou para `Full (strict)` assim que o certificado real foi emitido. Ver ADR-027
- [x] HSTS — Django ja manda `Strict-Transport-Security` desde `prod.py`; Nginx tambem manda o
      mesmo header (redundante, nao e problema)
- [x] Authenticated Origin Pulls (mTLS) — ligado dos dois lados (Cloudflare: SSL/TLS > Origin
      Server > Global; Nginx: `ssl_client_certificate` + `ssl_verify_client on`). Testado: sem
      certificado, a origem responde 400
- [x] UFW no servidor restrito aos ranges de IP da Cloudflare em 80/443 (44 regras — IPv4/IPv6 ×
      porta 80/443). Testado: acesso direto ao IP publico da timeout; sobreviveu a reboot completo
- [x] Nginx configurado para restaurar o IP real do visitante (`CF-Connecting-IP`,
      `docker/nginx/helpdesk.conf`) — sem isso, o throttle de login por IP seria contornavel
      (ver ADR-027)
- [x] Cloudflare Turnstile criado (widget `central-chamados-uncisal`, hostnames
      `uncisal.lserpsistemas.com.br` + `localhost`) e integrado no formulario de login
- [x] Teste publico do Qualys SSL Labs — **nota A+** nos 4 endpoints (2026-09-21, apos corrigir
      headers de seguranca duplicados entre Django e Nginx — ver ADR-027)

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

## Sequencia executada (2026-09-21) — ver ADR-026 e ADR-027 para detalhe completo

Concluido, na ordem que realmente funcionou (diferente do plano original — o modo `Full` sozinho
nao bastava para o desafio do Certbot, precisou passar por `Flexible` primeiro):

1. Publicada a aplicacao real no servidor + vhost do Nginx.
2. **Bloqueio inesperado**: porta 80 nao respondia nem publicamente nem via Cloudflare, mesmo com
   Security List/UFW corretos — causa raiz era uma regra de firewall de fabrica da propria imagem
   Ubuntu da Oracle, nao relacionada a Cloudflare (ver ADR-026). Corrigida antes de prosseguir.
3. Cloudflare mudado para `Flexible` temporariamente, Certbot emitiu o certificado real.
4. Cloudflare de volta para `Full (strict)` — resolveu tambem um loop de redirecionamento que
   apareceu no meio do caminho (Certbot forcando HTTPS na origem + Cloudflare ainda em Flexible).
5. Headers de seguranca e `real_ip` (Cloudflare) devolvidos ao Nginx.
6. UFW restrito aos ranges da Cloudflare + Authenticated Origin Pulls (mTLS) — os dois pedidos
   pelo usuario explicitamente, aplicados e testados juntos.
7. ~~Criar o Turnstile e integrar no login/cadastro.~~ Feito — falta so integrar no cadastro
   quando essa tela existir.
8. Teste do Qualys SSL Labs disparado.

**Pendente, nao critico:** headers de seguranca aparecem duplicados (Django + Nginx mandam os
mesmos) — cosmetico, nao e falha de seguranca.
