# Política de Segurança

Projeto acadêmico (pós-graduação em Segurança da Informação — UNCISAL), código público desde o
início do desenvolvimento.

## Reportar uma vulnerabilidade

Se você encontrou uma vulnerabilidade neste repositório, por favor **não abra uma issue pública**.
Reporte diretamente por e-mail: leonardoscussel@gmail.com.

Inclua, se possível:
- Passos para reproduzir
- Impacto esperado
- Versão/commit onde foi observado

## O que está em escopo

- Código em `src/`
- Configuração de infraestrutura em `docker/` e `.github/workflows/`

## O que está fora de escopo

- A instância de demonstração (se/quando publicada) — é um ambiente acadêmico, sem dados reais
  de terceiros.
- Ataques que exigam acesso físico ou engenharia social.

## Gestão de risco e resposta a incidente

Ver [`docs/security/risk-matrix.md`](docs/security/risk-matrix.md) e
[`docs/security/incident-response.md`](docs/security/incident-response.md).
