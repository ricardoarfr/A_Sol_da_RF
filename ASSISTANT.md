# ASSISTANT.md — Premissas do Projeto A Sol da RF

Este documento define as premissas, decisões e contexto de negócio do projeto.
Deve ser lido por qualquer pessoa (ou IA) antes de propor ou executar alterações.

---

## Quem Somos

A **RF** é uma empresa de serviços de campo. Nossos times técnicos operam externamente,
em campo, e precisam de acesso rápido a informações operacionais sem depender de
sistemas desktop ou navegadores.

---

## O Produto

Um **assistente via WhatsApp** que age como interface unificada para os sistemas internos da empresa.
O usuário (técnico, supervisor, gestor) manda uma mensagem e recebe informações operacionais em tempo real.

Não é um chatbot de FAQ. É um agente que consulta sistemas reais e toma ações reais.

---

## Usuários Principais

| Perfil | Necessidade Principal |
|--------|-----------------------|
| Técnico de campo | Ver agenda do dia, registrar ocorrência, consultar endereço |
| Supervisor | Ver status de equipe, redistribuir tarefas, verificar atrasos |
| Gestor | Visão geral de atividades, relatórios rápidos |

---

## Sistemas da Empresa

| Sistema | Papel |
|---------|-------|
| **Produttivo** | Gestão principal de atividades, técnicos e agenda de campo |
| **Voalle** | (a ser mapeado — integrar quando necessário) |
| **Telerdar** | (a ser mapeado — integrar quando necessário) |
| **Z-API** | Gateway de comunicação WhatsApp |

---

## Premissas Técnicas

1. **WhatsApp é o único canal de entrada do usuário** — não haverá app mobile ou painel web para o usuário final neste momento.

2. **O backend é stateless por padrão** — cada mensagem é processada de forma independente. Histórico de conversa, quando necessário, será gerenciado explicitamente.

3. **Cada sistema externo é um módulo isolado** — um `service` por sistema. Nunca misturar lógica de dois sistemas no mesmo arquivo.

4. **Credenciais nunca vão para o repositório** — todas as chaves, tokens e cookies ficam em variáveis de ambiente. O `.env` real nunca é commitado.

5. **O Render é nossa plataforma de hospedagem** — decisões de infraestrutura devem considerar as limitações e o modelo de custo do plano free (cold start, sleep após inatividade).

6. **A IA é um componente, não a fundação** — o sistema deve funcionar com lógicas simples primeiro. A IA entra para melhorar a interpretação de linguagem natural, não para substituir lógica de negócio.

---

## Premissas de Produto

1. **Respostas devem ser curtas e diretas** — o usuário está em campo. Sem textos longos, sem menus aninhados desnecessários.

2. **Erros devem gerar mensagens amigáveis** — nunca expor stack traces ou mensagens técnicas no WhatsApp.

3. **O sistema deve degradar com elegância** — se um sistema externo estiver fora, informar o usuário de forma clara e não derrubar os outros fluxos.

4. **Prioridade de entrega: funcionar primeiro, otimizar depois** — preferimos uma funcionalidade simples funcionando a uma arquitetura complexa incompleta.

---

## O que Não Fazer

- Não criar interfaces web ou painéis de controle enquanto o core pelo WhatsApp não estiver estável
- Não integrar sistemas novos sem antes mapear o que exatamente será consultado e como
- Não usar soluções pagas desnecessariamente enquanto houver alternativas gratuitas suficientes
- Não commitar credenciais, tokens ou cookies de sessão em nenhuma hipótese
- Não over-engenheirar: soluções simples são preferidas

---

## Decisões Tomadas

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-03 | Python + FastAPI | Ecossistema forte para APIs, async nativo, pydantic |
| 2026-03 | Z-API como gateway WhatsApp | Já contratado e número conectado |
| 2026-03 | Render como hospedagem | Plano free suficiente para início, fácil CI/CD via git |
| 2026-03 | Produttivo como sistema primário | É o sistema core de gestão de campo da RF |

---

## Contato e Responsabilidade

Projeto mantido internamente pela RF.
Dúvidas de negócio: tratar diretamente com Ricardo (responsável pelo produto).
