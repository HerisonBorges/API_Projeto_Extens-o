# IAM do SANDRO CRM

Regras de identidade e acesso: quem pode entrar, quem pode administrar contas
e como cada mudança fica registrada.

## Princípios

| Regra | Como é garantida |
|---|---|
| Menor privilégio | Só o perfil **Gestor** administra usuários, relatórios e configurações. |
| Isolamento por empresa | Toda consulta filtra pela `empresa_id` do token; o Gestor de uma empresa nunca vê nem altera usuários de outra (404). |
| Sem autoelevação | Ninguém altera o próprio perfil, nem desativa ou redefine a própria conta pelo painel. Isso também garante que a empresa nunca fica sem um Gestor ativo. |
| Sem exclusão de contas | Contas são **desativadas**; o histórico e a auditoria continuam válidos. |
| Revogação imediata | Desativar, redefinir senha, reativar, mudar perfil ou trocar a própria senha incrementa `token_versao` e derruba na hora todas as sessões abertas daquela conta. |
| Rastreabilidade | Toda ação de IAM grava um evento em `auditoria_usuarios`, na mesma transação da mudança. A auditoria **nunca** guarda senhas, hashes ou tokens. |

## Senhas

- Mínimo de **10 caracteres**, máximo de **72 bytes** (limite do bcrypt).
- Recusadas: senhas comuns (lista em `iam.py`), com menos de 4 caracteres
  distintos, ou iguais ao e-mail / à parte antes do `@`.
- Sem regras de composição obrigatória (maiúscula, símbolo...), seguindo o
  NIST SP 800-63B: comprimento e lista de bloqueio protegem mais.
- Armazenadas só como hash bcrypt.

### Senha temporária

Gerada pelo sistema na **criação**, **redefinição** e **reativação** da conta:

- 14 caracteres aleatórios (`secrets`), sem caracteres ambíguos (0/O, 1/l/I).
- Mostrada **uma única vez** ao Gestor, que entrega por um canal seguro.
- Vale **72 horas**. Depois disso o login responde `SENHA_TEMPORARIA_EXPIRADA`.
- Obriga a troca no primeiro acesso: até lá, a API responde
  `403 TROCA_SENHA_OBRIGATORIA` em qualquer rota, menos `GET /auth/me` e
  `PUT /auth/senha`.
- **Reativar sempre gera senha nova**: a antiga pode ter vazado enquanto a
  conta estava parada.

## Login

- E-mail sem diferenciar maiúsculas e espaços.
- E-mail inexistente e senha errada têm **a mesma resposta** (`401 E-mail ou
  senha inválidos.`) e o mesmo custo de tempo: não dá para descobrir quem tem conta.
- **5 senhas erradas seguidas** bloqueiam a conta por **15 minutos**
  (`429 LOGIN_BLOQUEADO`), inclusive para a senha certa. A redefinição pelo
  Gestor desbloqueia na hora.
- Mensagens específicas (conta desativada, senha temporária expirada, fora do
  horário) só aparecem **depois** de a senha conferir.

## Endpoints

### Própria conta (qualquer perfil logado)

| Método | Rota | Função |
|---|---|---|
| `GET` | `/auth/me` | Dados da própria conta. Substitui o antigo `GET /auth/me/<id>`, que era público. |
| `PUT` | `/auth/senha` | Troca a própria senha: `{"senha_atual", "nova_senha"}`. Devolve um token novo; as outras sessões caem. |

### Gestão de usuários (somente Gestor, na própria empresa)

| Método | Rota | Função |
|---|---|---|
| `GET` | `/usuarios` | Lista usuários com situação (ativo, bloqueado, aguardando 1º acesso, último login). |
| `POST` | `/usuarios` | Cria: `{"nome", "email", "perfil"}`. Responde com `senha_temporaria` (única vez). |
| `PUT` | `/usuarios/<id>` | Altera nome, e-mail e/ou perfil. Mudança de perfil derruba as sessões do usuário. |
| `POST` | `/usuarios/<id>/redefinir-senha` | Nova senha temporária, desbloqueia e derruba as sessões. |
| `POST` | `/usuarios/<id>/desativar` | Desativa e derruba as sessões. |
| `POST` | `/usuarios/<id>/reativar` | Reativa com nova senha temporária. |
| `GET` | `/usuarios/auditoria?limite=50` | Últimos eventos de IAM da empresa. |

Eventos auditados: `usuario_criado`, `usuario_alterado`, `perfil_alterado`,
`senha_redefinida`, `senha_alterada`, `usuario_desativado`,
`usuario_reativado`, `login_bloqueado`.

## Limitações conhecidas

- **Não há "esqueci minha senha" por e-mail.** Exige um serviço de envio de
  e-mail, que o projeto não tem. Hoje a redefinição é feita pelo Gestor. Se a
  empresa tiver um único Gestor e ele perder a senha, a recuperação é manual
  no banco.
- **Um Gestor pode redefinir a senha de outro Gestor.** Os dois já têm o
  mesmo nível de acesso, então isso não eleva privilégio, mas permite agir em
  nome do outro. Por isso fica registrado na auditoria.
- **O bloqueio por tentativas confirma que o e-mail existe** para quem errar
  5 vezes seguidas. É a troca usual entre conter força bruta e evitar
  enumeração.
- Não há autenticação em dois fatores (MFA).

## Testes

`tests/test_iam_usuarios.py` (23 cenários BDD) cobre cada regra acima,
incluindo as tentativas de abuso: autoelevação de perfil, ação sobre outra
empresa, uso de token antigo, enumeração de contas e vazamento de senha na
auditoria.
