# Boas práticas para projetos futuros (documento auxiliar)

> **Documento auxiliar.** Não faz parte dos requisitos obrigatórios da disciplina e não descreve
> nada que precise ser corrigido para esta entrega. Registra lições aprendidas neste projeto
> (*Secure by Design* e *Secure by Default*) para que os próximos já comecem num patamar acima.

Registrado em: 2026-09-30.

## Contexto: de onde veio este documento

Depois da entrega, o aluno abriu o console do navegador (DevTools) na tela de Backup e encontrou
duas violações de CSP:

1. `Executing inline script violates the following Content Security Policy directive...`
2. `Loading the script 'https://static.cloudflareinsights.com/beacon.min.js' violates...`

Nenhum dos dois vem do código da aplicação. Os dois scripts são **injetados pela Cloudflare na
borda**, entre o servidor e o navegador:

- o script inline é o `window.__CF$cv$params`, das *JavaScript Detections* (que acompanham o
  Bot Fight Mode). Aparece também na página de login pública e não existe em nenhum template;
- o `beacon.min.js` é o **Cloudflare Web Analytics**, injetado automaticamente quando esse
  recurso está ligado no painel.

O CSP bloqueou código que a aplicação não autorizou, que é exatamente o trabalho dele. Os erros
são cosméticos (a aplicação funciona normalmente), mas revelam decisões que ficaram implícitas.

## O CSP deste projeto está acima da média

A política em produção (`docker/nginx/helpdesk.conf`):

```
default-src 'self';
script-src 'self' https://challenges.cloudflare.com;
frame-src https://challenges.cloudflare.com;
style-src 'self' 'unsafe-inline';
img-src 'self' data:;
connect-src 'self';
base-uri 'self';
form-action 'self';
frame-ancestors 'none'
```

Pontos fortes, pouco comuns em projetos acadêmicos e mesmo em muitos comerciais:

- **Scripts sem `'unsafe-inline'` e sem `'unsafe-eval'`**. Um XSS que consiga injetar
  `<script>` não executa.
- `default-src 'self'` como base restritiva, com liberação só do domínio do Turnstile.
- `frame-ancestors 'none'` contra clickjacking, `form-action 'self'` contra desvio de formulário
  e `base-uri 'self'` contra sequestro de URLs relativas.
- Quando o CSP quebrou o `onclick` inline, a correção foi mover o código para um `.js` externo
  (ADR-028), e **não** afrouxar a política.

## Postura do aluno

Mesmo trabalhando com um assistente de IA agêntico (Claude Code), o aluno participou ativamente
de todas as decisões e **questionou em vez de só aceitar**. Por exemplo:

- conferiu a documentação e apontou inconsistências (status do 2FA do GitHub divergindo entre
  dois documentos, tabela OWASP desatualizada, ADR que descrevia uma máquina diferente da que
  foi provisionada);
- exigiu teste real em vez de afirmação (restauração de backup de verdade, teste de fogo com
  tentativas de IDOR ao vivo);
- tomou decisões explícitas de escopo, registradas com justificativa em vez de esquecidas
  (não rotacionar dois segredos, ADR-030; não implementar rate limiting na criação de chamado
  para evitar overengineering, ADR-033);
- inspecionou o próprio sistema em produção (o console do navegador que originou este documento).

O assistente acelera a execução. A responsabilidade e o senso crítico continuam com quem conduz
o projeto.

## Pontos de atenção encontrados (não corrigidos: fora do escopo da entrega)

| Ponto | Por que importa | Como resolver num projeto futuro |
|---|---|---|
| Scripts injetados pela Cloudflare bloqueados pelo CSP | Conflito entre dois componentes sem decisão explícita | Desligar o que não é usado (ex.: Web Analytics) ou liberar no CSP o que é usado, conforme a documentação da Cloudflare |
| `style-src 'unsafe-inline'` | Ponto mais fraco da política: permite injeção de CSS, que pode vazar dados da página | Evitar `style=""` e `<style>` inline desde o início; com Tailwind, quase sempre é possível |
| Falso alarme: "CSP duplicado" | Uma primeira checagem com `curl -sIL` mostrou o header duas vezes e foi registrada aqui como problema. Reconferido em 2026-09-30: cada resposta envia **um único** CSP; o `-L` segue o redirect e imprime os headers das duas respostas (redirect + destino) | Ao auditar headers, olhar **uma resposta por vez** (`curl -s -D - -o /dev/null URL`, sem `-L`) antes de concluir algo |

## Desenvolvimento mais pragmático: evitar más práticas desde o dia zero

A lição central: **é muito mais barato nunca introduzir uma má prática do que removê-la depois.**
Este projeto corrigiu várias coisas no caminho (ADR-028 é o exemplo). Num próximo, estas regras
valem desde o primeiro commit e ficam registradas no `CLAUDE.md` (ou equivalente), para o
assistente de IA segui-las também.

### Front-end e CSP

1. **Nada de JavaScript inline no template.** Nem `<script>` solto, nem `onclick=""`/`onchange=""`,
   nem `href="javascript:..."`. Todo JS fica em arquivo `.js` externo, com delegação de eventos via
   atributos `data-*`.
2. **Nada de estilo inline** (`style=""`, `<style>` na página), para nunca precisar de
   `style-src 'unsafe-inline'`.
3. **CSP desde o primeiro deploy**, começando em modo
   `Content-Security-Policy-Report-Only` com `report-to`: registra violações sem bloquear nada.
   Depois de um período sem violações inesperadas, passar para o modo que aplica a política.
4. **Nonce ou hash em vez de exceções.** Se um script inline for inevitável, usar `nonce` (valor
   aleatório por requisição, no header e na tag) ou o hash `sha256-...` do script, nunca
   `'unsafe-inline'`. No Django, o `django-csp` gera nonces. Padrão mais moderno: *Strict CSP*
   (`nonce` + `'strict-dynamic'`).
5. **Scripts de terceiros no mínimo possível** e, quando tiverem versão fixa, com **SRI**
   (`integrity="sha384-..."`): se o arquivo no CDN for adulterado, o navegador se recusa a
   executá-lo. Exceção conhecida: scripts que mudam sozinhos, como o `api.js` do Turnstile, que a
   própria Cloudflare pede para não fixar com SRI.
6. **Decidir explicitamente o que o CDN/proxy pode injetar** (analytics, detecção de bot,
   Rocket Loader, ofuscação de e-mail). Cada recurso ligado no painel é código que chega ao
   navegador sem passar pelo repositório.
7. **Classes CSS sempre escritas por extenso** em arquivos que o build de CSS enxerga, nunca
   montadas em tempo de execução (ADR-028).

#### Tailwind CSS e CSP estrito: aliados, não conflito

Classes utilitárias do Tailwind são uma ótima prática: agilizam a escrita, mantêm o visual
consistente e dispensam CSS avulso espalhado pelo projeto. **Usar muitas classes utilitárias não
tem nada a ver com "estilo inline" no sentido do CSP.** A palavra "inline" aparece nos dois
contextos com significados diferentes:

| | Estilo inline (CSP) | Classes utilitárias (Tailwind) |
|---|---|---|
| Exemplo | `<div style="text-align: center">` | `<div class="text-center">` |
| Onde fica a regra CSS | Dentro do próprio HTML | No `app.css` gerado no build, servido pelo próprio domínio |
| O que o CSP exige | `style-src 'unsafe-inline'` | Nada além de `'self'` |
| Risco | HTML injetado também injeta CSS | Nenhum adicional |

O Tailwind é justamente o que torna fácil **nunca precisar** de `style=""`, porque quase toda
declaração CSS tem uma classe equivalente. Um exemplo real deste projeto: as páginas de erro
(`403.html`, `404.html`, `500.html`) têm

```html
<div class="max-w-sm mx-auto mt-16 bg-white shadow rounded-lg p-6" style="text-align: center;">
```

que fica, sem nenhuma perda:

```html
<div class="max-w-sm mx-auto mt-16 bg-white shadow rounded-lg p-6 text-center">
```

Cuidados para manter o Tailwind compatível com um CSP estrito:

- **Compilar com o CLI (ou build do framework), nunca usar o Play CDN** (`cdn.tailwindcss.com`).
  O Play CDN gera o CSS no navegador e o injeta num `<style>` em tempo de execução, o que exige
  `'unsafe-inline'`. Este projeto usa o CLI por isso (ADR-011).
- **Valores arbitrários são seguros.** `bg-[#1e40af]` ou `w-[37px]` viram regras dentro do
  `app.css` no build, como qualquer outra classe.
- **Valores dinâmicos vindos do servidor** são o único ponto de atenção. Numa barra de progresso,
  por exemplo, a tentação é escrever `style="width: {{ pct }}%"`. Alternativas compatíveis:

  ```html
  <!-- 1. Elemento nativo -->
  <progress value="73" max="100" class="w-full h-2"></progress>

  <!-- 2. Degraus fixos de classe, quando a precisão não importa -->
  <div class="h-2 bg-blue-600 w-3/4"></div>

  <!-- 3. Valor num data-attribute, aplicado por JS externo -->
  <div class="h-2 bg-blue-600" data-progress="73"></div>
  ```

  ```js
  // static/js/app.js — alterar estilo via JavaScript não é bloqueado pelo CSP
  document.querySelectorAll("[data-progress]").forEach((el) => {
    el.style.width = `${el.dataset.progress}%`;
  });
  ```

- **Classes escritas por extenso.** O Tailwind só gera as classes que encontra como texto nos
  arquivos que ele varre. `"bg-" + cor` montado em Python ou JS nunca entra no CSS final
  (ADR-028). Para variar a classe, escrever as opções completas (ex.: um dicionário
  `{"aberto": "bg-green-100", "fechado": "bg-gray-100"}`).

### Configuração e infraestrutura

8. **Headers de segurança num lugar só** (proxy *ou* aplicação), conferidos com `curl -I` depois
   de cada deploy.
9. **Configurações seguras por padrão.** Produção falha alto se faltar uma variável sensível
   (`ImproperlyConfigured`), nunca cai num valor de desenvolvimento. Segredos só via variável de
   ambiente, desde o início.
10. **Hooks de segredo no primeiro commit** (gitleaks, detect-private-key). Vazamento no
    histórico do Git é muito mais caro de limpar do que de evitar.
11. **Cada processo com o mínimo de permissão que precisa, verificado na prática.** O ADR-034 é
    o contraexemplo: o volume foi montado como somente leitura por segurança, mas o processo
    precisava gravar um registro, e isso só foi percebido uma semana depois. Menor privilégio é
    uma hipótese a testar, não algo para presumir.
12. **Toda verificação automática precisa ser real.** Um healthcheck que nunca passa (ou um teste
    que passa sem verificar nada) é pior do que nenhum, porque ensina a ignorar o alarme.

## Ferramentas: qual testa o quê

Cada ferramenta cobre uma camada. O Qualys SSL Labs, por exemplo, avalia **TLS** (certificado,
protocolos, cifras, PQC), não os headers HTTP. Por isso a nota A+ dele não diz nada sobre o CSP.

**✅ = já usado neste projeto.**

### TLS e headers HTTP

| Ferramenta | O que avalia |
|---|---|
| **Qualys SSL Labs** ✅ | Configuração TLS: certificado, protocolos, cifras, troca de chaves pós-quântica |
| **testssl.sh** | O mesmo, via linha de comando (dá para rodar em CI ou contra servidores internos) |
| **Mozilla HTTP Observatory** | Headers de segurança (CSP, HSTS, X-Frame-Options, cookies etc.), com nota e explicação |
| **securityheaders.com** | Checagem rápida dos headers de segurança, com nota |
| **Google CSP Evaluator** | Analisa a política CSP em si e aponta brechas (ex.: domínios liberados que permitem contornar a política) |

### Código e dependências

| Ferramenta | O que avalia |
|---|---|
| **Gitleaks** ✅ | Segredos commitados (pre-commit e CI) |
| **pip-audit** ✅ | Dependências Python com vulnerabilidade conhecida (CI) |
| **Dependabot** ✅ | Atualização automática de dependências e alertas de segurança |
| **Ruff** ✅ | Lint; com as regras `S` (derivadas do Bandit) também encontra padrões inseguros |
| **Bandit** | Análise estática de segurança específica para Python |
| **Semgrep** | Análise estática com regras prontas para Django/OWASP |
| **GitHub CodeQL** | Análise estática profunda, gratuita para repositórios públicos, integrada à aba *Security* do GitHub |
| **GitHub secret scanning + push protection** | Bloqueia o push quando detecta um segredo conhecido (gratuito para repositórios públicos) |
| **OSV-Scanner** | Dependências vulneráveis usando a base aberta OSV (multi-linguagem) |
| **`python manage.py check --deploy`** | Checagem nativa do Django para configurações inseguras de produção |

### Containers e infraestrutura como código

| Ferramenta | O que avalia |
|---|---|
| **Trivy** | Vulnerabilidades na imagem Docker (pacotes do sistema e das bibliotecas), configurações e segredos |
| **Hadolint** | Boas práticas no `Dockerfile` |
| **Docker Scout** | Vulnerabilidades em imagens, integrado ao Docker |
| **Checkov** | Más configurações em IaC (Docker Compose, Terraform, workflows do GitHub Actions) |

### Aplicação em execução (DAST) e servidor

| Ferramenta | O que avalia |
|---|---|
| **OWASP ZAP** | Scanner dinâmico da aplicação no ar; o *baseline scan* roda em GitHub Actions e é passivo (não ataca) |
| **Nuclei** | Varredura baseada em templates de vulnerabilidades e más configurações conhecidas |
| **Nikto** | Scanner clássico de servidor web (arquivos expostos, versões antigas) |
| **Playwright** | Testes end-to-end; dá para falhar o CI se aparecer violação de CSP no console |
| **Lynis** | Auditoria de hardening do Linux do servidor |
| **ssh-audit** | Algoritmos e configuração do servidor SSH |
| **nmap** | Confirma de fora quais portas estão realmente abertas (complementa o `ufw status`) |

> DAST e varredura de portas só contra sistemas **próprios** ou com autorização explícita.

### Gestão de vulnerabilidades

| Ferramenta | Para que serve |
|---|---|
| **GitHub Security (aba *Security*)** | Centraliza alertas do Dependabot, CodeQL e secret scanning |
| **CycloneDX (`cyclonedx-py`)** | Gera o SBOM: inventário de todos os componentes do software |
| **OWASP Dependency-Track** | Consome o SBOM e acompanha continuamente quais componentes ganharam vulnerabilidade nova |
| **DefectDojo** | Agrega os achados de várias ferramentas num só lugar, com triagem e acompanhamento |

### Referências (o "o quê" e o "porquê")

- **OWASP Top 10**: os riscos mais comuns (usado neste projeto).
- **OWASP ASVS**: checklist detalhado de requisitos de segurança por nível; bom para definir, no
  início do projeto, o que "seguro" significa.
- **OWASP Cheat Sheet Series**: guias práticos por tema (CSP, sessões, senhas, Django...).
- **CIS Benchmarks**: configuração segura de SO, Docker e nuvem.
- **CISA — Secure by Design**: princípios de segurança por padrão, a mesma filosofia deste
  projeto.

## Sugestão de pipeline mínimo para o próximo projeto

Sem exagero, o que dá mais retorno pelo esforço:

1. **Pre-commit:** gitleaks, detect-private-key, formatador e linter (com regras de segurança).
2. **CI a cada push:** testes, pip-audit (ou OSV-Scanner), CodeQL/Semgrep, Trivy na imagem,
   `manage.py check --deploy`.
3. **Após o deploy:** ZAP baseline scan e checagem de headers (`curl -I` ou Observatory).
4. **Periódico:** Qualys SSL Labs, Lynis e nmap externo, com o resultado anexado como evidência,
   como foi feito aqui com o Qualys.
