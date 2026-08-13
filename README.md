# Automação Zendesk + Fraction — versão final

## Atenção
Esta versão executa ações reais:

- cria tickets no Zendesk;
- fecha a aba interna do ticket depois da criação;
- depois de terminar toda a fila do Zendesk, acessa o Fraction;
- inclui e salva a observação `REMETENTE ACIONADO.`.

## login.xlsx
O arquivo deve ficar na pasta do projeto e ter duas abas:

### ZENDESK
- USER
- PASSWORD

### FRACTION
- USER
- PASSWORD

## Planilha de entrada
Colunas obrigatórias:

- `Codigo`: pesquisa no Fraction;
- `Pedido`: pesquisa e preenchimento no Zendesk;
- `Status`: somente `CUSTODIA` entra na avaliação da fila;
- `Descricao`: define se a custódia deve abrir ticket e qual motivo usar.

Somente linhas com `Status = CUSTODIA` e `Descricao` mapeada entram na fila.

## Fluxo
### Fase 1 — Zendesk
Para cada item da fila:

1. pesquisa o `Pedido`;
2. se já houver ticket, não cria outro;
3. se não houver:
   - abre novo ticket;
   - preenche assunto;
   - seleciona Jadlog;
   - seleciona Transportadoras;
   - seleciona Insucesso na entrega;
   - seleciona o motivo conforme `Descricao`;
   - preenche o número do pedido;
   - preenche o comentário com a `Descricao` corrigida;
   - cria o ticket;
   - fecha a aba interna do ticket.

### Fase 2 — Fraction
Somente para tickets recém-criados:

1. Consultas;
2. Pesquisar;
3. preenche `Codigo`;
4. Processar;
5. Incluir Observação;
6. escreve `REMETENTE ACIONADO.`;
7. Salvar;
8. repete para o próximo.

## Resultado
A planilha final é salva em `resultados/` com nome:

`tickets_zendesk_YYYY-MM-DD_HH-MM-SS.xlsx`

Ela recebe as colunas:

- `Fila_Ticket`
- `Ticket_Criado`
- `Observacao_Fraction`
- `Erro_Automacao`

`Ticket_Criado = SIM` significa que o ticket foi criado nessa execução.
`Observacao_Fraction = SIM` significa que a observação foi salva no Fraction.
