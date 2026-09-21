# Provisionamento — Oracle Cloud Free Tier

Guia passo a passo para criar e preparar a instância que vai hospedar a aplicação. Conta pessoal,
sem qualquer ligação obrigatória com conta institucional — a criação e operação da VM é
responsabilidade individual do aluno (é inclusive parte do que a disciplina avalia).

Rótulos exatos do console da Oracle Cloud mudam de vez em quando — se algo não bater 100% com o
que está aqui, use a busca do console (ícone de lupa no topo) para achar a tela equivalente.

## Checklist

- [x] Conta Oracle Cloud criada (Always Free)
- [x] Par de chaves SSH gerado localmente
- [x] Instância criada (Ampere A1 tentado, capacidade esgotada → `VM.Standard.E2.1.Micro`) com Ubuntu 24.04.4 LTS
- [x] IP público reservado (não efêmero) — `163.176.75.32`
- [x] Security List liberando 22, 80 e 443
- [x] Primeiro acesso SSH confirmado
- [x] Hardening de SSH/UFW/Fail2Ban aplicado — ver [`ssh-hardening.md`](ssh-hardening.md)
- [x] Docker + Compose instalados
- [x] Nginx instalado
- [x] Certbot instalado (>= 5.4) — 5.8.0

---

## 1. Criar a conta

1. Acesse [cloud.oracle.com/free](https://www.oracle.com/cloud/free/) → **Start for free**.
2. Preencha e-mail, verifique por e-mail, complete endereço e telefone (verificação por SMS/ligação).
3. Cartão de crédito é pedido só para **verificação de identidade** — nada é cobrado enquanto você
   permanecer no Always Free (não faz upgrade automático; é preciso confirmar manualmente).
4. **Home Region**: essa escolha é definitiva, não dá para trocar depois. A Oracle tem duas
   regiões no Brasil: **`Brazil East (Sao Paulo)`** (`sa-saopaulo-1`) e
   **`Brazil Southeast (Vinhedo)`** (`sa-vinhedo-1`) — qualquer uma das duas dá a menor latência
   possível daqui. Se nenhuma aparecer como opção na sua conta no momento do cadastro, escolha a
   região comercial mais próxima disponível.

   **Sobre disponibilidade do Ampere A1 (seção 3):** a capacidade da shape Ampere A1 do Always
   Free varia por região e ao longo do tempo — é comum (documentado pela própria Oracle) receber
   um erro de **"out of host capacity"** ao tentar criar, principalmente em regiões menores como
   as do Brasil (1 availability domain só, contra 3 em regiões maiores). Se acontecer: tentar de
   novo mais tarde (várias pessoas relatam sucesso tentando em horários diferentes), ou cair para
   a shape AMD `VM.Standard.E2.1.Micro` como plano B — funciona igual para este projeto, só com
   menos folga de recursos (1 OCPU / 1 GB em vez de até 4 OCPU / 24 GB).

## 2. Gerar o par de chaves SSH (no seu Windows)

```powershell
ssh-keygen -t ed25519 -C "central-chamados-uncisal" -f "$HOME\.ssh\uncisal_oracle"
```

Duas perguntas: caminho (aceite o padrão que você passou com `-f`) e senha da chave (opcional —
uma passphrase é mais seguro, mas exige digitá-la a cada uso; escolha o que preferir). Isso gera
`uncisal_oracle` (privada — **nunca compartilhar nem commitar**) e `uncisal_oracle.pub` (pública).

## 3. Criar a instância de computo

Menu (≡) → **Compute** → **Instances** → **Create Instance**.

- **Name**: `central-chamados-uncisal`
- **Image and shape** → **Edit**:
  - **Image**: Canonical **Ubuntu 24.04** (ou Debian 12 — os passos seguintes são iguais, é tudo
    `apt`; só o usuário padrão de login muda, ver seção 6).
  - **Shape** → **Change shape** → aba **Ampere** → `VM.Standard.A1.Flex`.

    **Por que Ampere A1, e não a shape AMD (`VM.Standard.E2.1.Micro`)?** O Always Free da Oracle
    dá até **4 OCPUs e 24 GB de RAM** no Ampere (ARM), contra **1 OCPU e 1 GB** no AMD — para
    Docker + Gunicorn + Nginx, isso é uma folga enorme sem custar nada a mais. A única pegadinha
    de usar ARM é imagem Docker incompatível com x86 — já corrigido no `Dockerfile` deste projeto
    (`ARG TARGETARCH` escolhe o binário certo do Tailwind CLI automaticamente).

  - Ajuste OCPU (ex.: 2) e memória (ex.: 12 GB) — dá para usar até o teto do Always Free (4/24);
    não precisa do máximo para este projeto, mas não custa nada usar.
- **Add SSH keys**: **Paste public keys** → cole o conteúdo de `uncisal_oracle.pub`
  (`Get-Content $HOME\.ssh\uncisal_oracle.pub` no PowerShell para ver o conteúdo).
- **Networking**: deixe no padrão (cria uma VCN nova com subnet pública, internet gateway e uma
  Security List padrão liberando 22 de qualquer origem — vamos revisar isso na seção 5).
- **Boot volume**: padrão está OK (dentro do limite gratuito de 200 GB).
- **Create**.

A instância leva 1–2 minutos para ficar `RUNNING`.

## 4. Reservar o IP público (não deixar efêmero)

Por padrão o IP é **efêmero** — muda se a instância for parada e iniciada de novo. Como o domínio
(`uncisal.lserpsistemas.com.br`) vai apontar para esse IP, ele precisa ser fixo.

Na página da instância → em **Primary VNIC**, no IP público listado → ícone de edição → trocar de
**Ephemeral** para **Reserved Public IP** (criar um novo). Anote o IP.

## 5. Revisar a Security List (firewall da nuvem, antes mesmo de chegar na VM)

Menu (≡) → **Networking** → **Virtual Cloud Networks** → a VCN criada → **Security Lists** →
a lista padrão → **Ingress Rules**.

Deve ficar assim (adicionar o que faltar com **Add Ingress Rules**):

| Source CIDR | Protocolo | Porta destino | Observação |
|---|---|---|---|
| `0.0.0.0/0` | TCP | 22 | SSH — considerar restringir ao seu IP depois (ver nota abaixo) |
| `0.0.0.0/0` | TCP | 80 | HTTP (Certbot/redirect) |
| `0.0.0.0/0` | TCP | 443 | HTTPS |

Isso é **redundante de propósito** com o UFW que vai rodar dentro da VM (ver
[`ssh-hardening.md`](ssh-hardening.md)) — duas camadas de firewall independentes, uma na borda da
nuvem, outra no host.

> **Opcional, depois que tudo estiver funcionando**: trocar `0.0.0.0/0` das portas 80/443 pelos
> [ranges de IP da Cloudflare](https://www.cloudflare.com/ips/) apenas — assim nem o tráfego HTTP
> bruto chega na Oracle Cloud sem passar pela Cloudflare antes. Não faça isso antes de confirmar
> que o site funciona, para não se trancar para fora durante o teste.
>
> Restringir a porta 22 a um único IP só vale a pena se você tiver IP fixo (raro em conexão
> residencial no Brasil) — senão, fique com o Fail2Ban + chave obrigatória como a proteção real.

## 6. Primeiro acesso SSH

```powershell
ssh -i "$HOME\.ssh\uncisal_oracle" ubuntu@SEU_IP_PUBLICO
```

(usuário padrão: `ubuntu` na imagem Ubuntu, `debian` na imagem Debian). Na primeira conexão o SSH
pergunta se confia no fingerprint do host — responda `yes`.

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

Aguarde ~1 minuto e reconecte.

## 7. Hardening (usuário dedicado, SSH, UFW, Fail2Ban)

Seguir [`ssh-hardening.md`](ssh-hardening.md) inteiro a partir daqui, antes de prosseguir — ele
cobre a criação do usuário `deploy`, desabilitar login por senha/root, UFW e Fail2Ban. Os passos
abaixo assumem que isso já foi feito (logado como `deploy`, com `sudo`).

## 8. Instalar Docker + Compose

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker deploy
```

Saia e reconecte (`exit` + `ssh` de novo) para o grupo `docker` valer. Confirmar:

```bash
docker --version
docker compose version
```

## 9. Instalar o Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable --now nginx
```

A configuração real (`server_name uncisal.lserpsistemas.com.br`, proxy para o container, headers
de segurança) está em [`docker/nginx/helpdesk.conf`](../../docker/nginx/helpdesk.conf) deste
repositório — copiar para `/etc/nginx/sites-available/` faz parte da etapa de deploy
(`docs/infra/cloudflare-setup.md`), depois que o domínio estiver apontado.

## 10. Instalar o Certbot (>= 5.4)

O `apt` do Ubuntu costuma ficar atrás da versão mais recente do Certbot. Instalar via **snap**
garante a versão exigida:

```bash
sudo apt install -y snapd
sudo snap install core; sudo snap refresh core
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
certbot --version
```

## 11. Clonar o repositório e primeiro deploy manual

Antes do CI/CD assumir isso automaticamente, vale rodar uma vez manualmente para validar:

```bash
git clone https://github.com/lscussel-uncisal/projeto-uncisal.git ~/helpdesk
cd ~/helpdesk
cp .env.example .env
nano .env   # preencher com valores reais de producao — ver docs/security/nao-commitar.md
docker compose -f docker/docker-compose.yml up -d --build
curl -s http://127.0.0.1:8000/healthz/
```

Deve responder `{"status": "ok"}`. Configuração de domínio/Cloudflare/HTTPS/CI-CD são os próximos
passos, cobertos em [`cloudflare-setup.md`](cloudflare-setup.md) e no workflow
[`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml).

## Observações (execução real — 2026-09-20)

- Região: `sa-saopaulo-1` (Brazil East).
- Shape efetivamente usada: **`VM.Standard.E2.1.Micro`** (AMD), não a Ampere A1 recomendada —
  as duas shapes Always Free ficaram momentaneamente sem capacidade ("out of host capacity") em
  AD-1 durante a criação; o AMD Micro liberou primeiro. Ver ADR-015/ADR-016 em
  `docs/architecture/decisions.md`.
- Imagem: Canonical Ubuntu **24.04.4 LTS**, `x86_64`.
- Nome da instância: `central-chamados-uncisal`.
- IP público reservado: **`163.176.75.32`**.
- A opção "Automatically assign public IPv4 address" do wizard de criação não funcionou ao criar
  a instância com subnet nova inline — a instância nasceu sem IP público e sem Internet Gateway.
  Corrigido depois, manualmente: Quick Action "Connect public subnet to internet" (cria o IG) +
  editar o IP privado da VNIC → "Reserved public IP" → "Create new Reserved IP Address".
- Shielded Instance (Secure Boot/Measured Boot/TPM): não foi possível habilitar nessa combinação
  de imagem/shape/região (toggles ficaram bloqueados) — seguiu sem, não é requisito da disciplina.
- Todo o hardening (usuário `deploy`, SSH, UFW, Fail2Ban, unattended-upgrades) e a instalação de
  Docker/Nginx/Certbot foram executados via SSH automatizado. Fail2Ban já baniu um IP na primeira
  checagem, minutos depois do IP público existir — confirma que a exposição é real desde o
  primeiro minuto.
