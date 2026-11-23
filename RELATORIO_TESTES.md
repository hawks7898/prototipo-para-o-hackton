# Relatório de testes e correções do Buscaí

Em 23 de novembro de 2026, foram corrigidos três problemas na comparação de compras e no cadastro manual de preços. A suíte passou de 38 para 42 casos após a inclusão dos testes de regressão.

## Correções verificadas

| Área | Problema reproduzido | Resultado após a correção |
| --- | --- | --- |
| Compra em várias lojas | Ao escolher o menor preço por item, o cálculo descartava uma cesta válida quando a loja online ficava abaixo do pedido mínimo. | O cálculo considera outras atribuições para cumprir o mínimo. No cenário testado, encontra a cesta válida de R$ 65. Quando o mínimo é impossível de atingir, a combinação é descartada. [rotas.py](rotas.py) |
| Aba Comparação | Com o limite em 1, a tabela mostrava 5 lojas. | A tabela respeita o limite. Expandir mostra todas as lojas selecionadas e Recolher restaura o limite, inclusive quando a pesquisa volta sem cotações. [app.py](app.py) |
| Cadastro manual de preços | Um link malformado disparava uma exceção sem tratamento no formulário. | O formulário recebe um erro de validação e pode exibir a orientação sobre o link HTTPS. [precos_manuais.py](precos_manuais.py) |

## Validação

- `python -m pytest -q` executou 42 testes com sucesso. Os novos casos cobrem a atribuição da cesta com e sem pedido mínimo, um mínimo inalcançável e um link malformado. [test_regressoes.py](tests/test_regressoes.py)
- Os testes do Streamlit cobriram abertura, login, pesquisa, as cinco abas com cesta completa, parcial ou sem cotações e os controles de expansão da Comparação.
- A validação do Streamlit usou contas e cotações simuladas. Consultas a serviços externos, envio de e-mails e leitura de encartes com Ollama ficaram fora desta execução.
