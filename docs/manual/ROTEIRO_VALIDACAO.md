# SANDRO CRM · Roteiro de validação

- **Para:** cliente e equipe que vai validar a versão nova
- **Endereço:** https://sandro-crm.netlify.app
- **Tempo estimado:** 30 a 40 minutos

## Antes de começar

- Use uma conta **criada ou redefinida pelo Gestor** em Configurações → Usuários. Não use contas de teste com senha conhecida.
- Teste no computador **e** no celular. No celular, use o navegador comum (Chrome ou Safari).
- Os dados que você cadastrar ficam guardados. Use nomes como "Cliente Teste 1" para facilitar a limpeza depois.
- Para cada item, marque **OK** ou descreva o problema na coluna "Observação": o que fez, o que esperava, o que aconteceu e, se puder, um print.

## 1. Acesso e segurança

| # | O que fazer | O que deve acontecer | OK? | Observação |
|---|---|---|---|---|
| 1.1 | Entre com o perfil errado (ex.: marcar "Atendimento" numa conta de Gestor) | Aviso: "Esta conta é do perfil Gestor. Selecione 'Gestor' para entrar." | | |
| 1.2 | Gestor: crie um usuário em Configurações → "+ Novo usuário" | Aparece a **senha temporária** uma única vez, com o botão "Copiar" | | |
| 1.3 | Entre com essa senha temporária | Tela "Defina a sua senha". Nenhuma outra tela abre antes da troca | | |
| 1.4 | Tente uma senha nova com menos de 14 caracteres | Recusada: "A nova senha precisa de pelo menos 14 caracteres." | | |
| 1.5 | Defina uma senha de 14+ caracteres (uma frase serve) | Entra no sistema: "Senha definida. Bem-vindo(a) ao SANDRO CRM." | | |
| 1.6 | Gestor: em Configurações, veja a coluna "Situação" de um usuário que ainda não entrou | Mostra "Aguardando 1º acesso" e "Senha temporária vence em … (data)" | | |
| 1.7 | Gestor: defina uma jornada para um Atendimento que termine daqui a ~10 min. Entre com ele e espere | 5 min antes: aviso amarelo com contagem regressiva. No horário: volta para o login com o motivo | | |
| 1.8 | Atendimento: confira o menu | Não aparecem "Relatórios" nem "Configurações" | | |

## 2. Planilha: modelo, erros e prévia

Em **Clientes → "Importar / Exportar"** (só Gestor):

| # | O que fazer | O que deve acontecer | OK? | Observação |
|---|---|---|---|---|
| 2.1 | Clique em "Modelo .xlsx" e abra no Excel | Abas "Clientes" e "Instruções"; listas suspensas em Status, Tipo e Frequência | | |
| 2.2 | Preencha 3 clientes. Num deles, escreva o nome começando com `=` (ex.: `=TESTE`) e envie | "Nada foi importado" com **Linha e coluna** do problema. A linha boa também não entra | | |
| 2.3 | Num cliente, coloque um CPF inválido (ex.: 123.456.789-00) | Erro na coluna "CPF/CNPJ": dígito verificador inválido | | |
| 2.4 | Corrija tudo e envie de novo | Barra de progresso, depois "Pronto para importar" e a **prévia das 5 primeiras linhas** | | |
| 2.5 | Clique em "Importar N cliente(s)" | "N cliente(s) e M recorrência(s) importados". Os clientes aparecem na lista | | |
| 2.6 | Envie a **mesma** planilha de novo | Recusada: "Já existe um cliente com este CPF/CNPJ" | | |
| 2.7 | Tente enviar um arquivo que não seja planilha (ex.: PDF ou foto) | Recusado: "Envie um arquivo .xlsx ou .csv." | | |
| 2.8 | Clique em "Exportar .xlsx" | Arquivo com os clientes da empresa no mesmo formato do modelo | | |

**Dica para a planilha 2.4:** para testar recorrência, preencha numa linha
`lembrete · mensal · 5 · Fechamento do mês` e, repetindo o **mesmo CPF/CNPJ** em outra linha,
`oportunidade · semanal · segunda · Compra semanal · 350,00`.

## 3. Recorrências

| # | O que fazer | O que deve acontecer | OK? | Observação |
|---|---|---|---|---|
| 3.1 | Abra um cliente importado no passo 2.5 | Card "Recorrências" com as regras e "Próxima: dd/mm/aaaa" | | |
| 3.2 | "+ Nova recorrência": Oportunidade, Semanal, sexta-feira, valor | O formulário mostra "Toda sexta-feira · próxima em dd/mm/aaaa" | | |
| 3.3 | Crie uma regra mensal no dia 31 | Aviso: "Nos meses mais curtos, vale o último dia do mês." | | |
| 3.4 | "Pausar" e depois "Retomar" | Mostra "Pausada"; ao retomar, volta a mostrar a próxima data | | |
| 3.5 | Funil → "+ Nova oportunidade" → marque "Repetir automaticamente" | Ao criar: "Oportunidade … criada em Prospecção. Repete …" | | |
| 3.6 | Atendimento: tente excluir uma recorrência | O botão "Excluir" não aparece (só o Gestor exclui) | | |

> Nesta fase de validação, a geração automática (o follow-up ou o card que aparece no dia)
> é disparada pela equipe técnica a pedido. Avise quando quiser ver uma regra "acontecer".

## 4. Celular

Abra o site no celular, com a conta de Gestor:

| # | O que fazer | O que deve acontecer | OK? | Observação |
|---|---|---|---|---|
| 4.1 | Percorra todas as telas | Nenhuma tela "anda para o lado"; nada cortado | | |
| 4.2 | Toque no ☰ (canto superior direito) | Menu lateral com as telas, "Alterar senha" e "Sair" | | |
| 4.3 | Clientes | Lista em cartões; tocar no cartão abre o cliente | | |
| 4.4 | Funil | Uma coluna por vez, deslizando para o lado; botões "Avançar →" e "←" | | |
| 4.5 | "+ Novo Lead": toque num campo | O formulário sobe de baixo e o campo continua visível com o teclado aberto | | |
| 4.6 | Importar planilha pelo celular | Prévia em cartões, sem rolagem lateral | | |
| 4.7 | Botões em geral | Fáceis de tocar, sem acertar o vizinho | | |

## 5. Rotina que já existia (conferência rápida)

| # | O que fazer | O que deve acontecer | OK? | Observação |
|---|---|---|---|---|
| 5.1 | "+ Novo Lead" com oportunidade | Cliente criado como Lead e card em Prospecção | | |
| 5.2 | Mover um card até "Fechado" | Entra na receita do Dashboard e de Relatórios | | |
| 5.3 | Registrar uma interação no cliente | Aparece no histórico e em "Últimas interações" do Dashboard | | |
| 5.4 | Follow-ups: "✓ Concluir" e "Reagendar" | Some da lista / muda a data | | |
| 5.5 | Relatórios → "Exportar PDF" | PDF com a marca SANDRO e os números do período | | |

## Aprovação

| | |
|---|---|
| Validado por | |
| Cargo | |
| Data | |
| Resultado | ☐ Aprovado  ☐ Aprovado com ajustes  ☐ Reprovado |
| Ajustes pedidos | |
