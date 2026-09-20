# Provisionamento — Oracle Cloud Free Tier

> Status: pendente de preenchimento apos a criacao da instancia.
> Antes de colar comandos/capturas aqui, conferir [`docs/security/nao-commitar.md`](../security/nao-commitar.md)
> — em especial: nunca colar a chave privada da API do OCI, nem OCIDs de tenancy/usuario junto dela.

## Checklist

- [ ] Conta Oracle Cloud criada (Free Tier / Always Free)
- [ ] Instancia de computo (VM.Standard.E2.1.Micro ou Ampere A1 Always Free) criada
- [ ] Sistema operacional: Ubuntu Server ou Debian (ultima versao estavel)
- [ ] Par de chaves SSH gerado e associado a instancia
- [ ] IP publico reservado (evitar IP efemero, para nao perder o endereco em reboot)
- [ ] Security List / Network Security Group liberando apenas 22 (temporario), 80 e 443
- [ ] UFW configurado no host replicando a mesma politica de menor privilegio
- [ ] Fail2Ban instalado e configurado para a porta 22 (4 tentativas, ban de 24h)
- [ ] Autenticacao por senha desabilitada no SSH (`PasswordAuthentication no`)
- [ ] Docker + Docker Compose instalados
- [ ] Nginx instalado
- [ ] Certbot instalado (>= 5.4) e certificado emitido

## Passo a passo

_(a preencher durante o provisionamento — capturas de tela e comandos exatos usados)_

## Decisoes e observacoes

_(ex.: shape escolhido, motivo, limitacoes do Always Free encontradas)_
