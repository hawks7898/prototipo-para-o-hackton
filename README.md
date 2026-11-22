# Buscaí

O Buscaí compara preços entre filiais de Piracicaba. O aplicativo consulta os catálogos oficiais disponíveis e lê encartes com Ollama e Tesseract no mesmo computador do Streamlit. A tabela destaca o menor preço oficial encontrado para cada produto.

## Atualizar sua instalação

Extraia o ZIP em uma pasta nova. Este pacote inclui `precos_reais.sqlite3` com as 42 coletas manuais da instalação original, preservando a data de cada preço. A tabela mostra esses valores como **Coleta manual**. O limite de idade padrão das coletas é de 30 dias.

Para manter contas, receitas e configurações, pare o Streamlit e copie `usuarios.json` e `.streamlit/secrets.toml` da instalação anterior, se existirem. Se você registrou novas coletas após enviar o ZIP original, mantenha uma cópia de segurança do seu banco e use a versão local mais recente do `precos_reais.sqlite3`. Se você personalizou `produtos.json`, `filiais_manuais.json`, `filiais_confirmadas.json` ou `logo.png`, copie também suas versões locais. Se já usa `BUSCAI_PRECOS_DB`, o app abre o banco indicado nessa configuração.

Em uma instalação nova, `python criar_adm_local.py` cria a conta administrativa com uma senha escolhida no terminal. A integração legada com PreçoMelhor vem desativada. Se você decidir habilitá-la como fonte complementar, use `BUSCAI_USAR_PRECOMELHOR=1` e configure sua chave em `.streamlit/secrets.toml` ou em `BUSCAI_PRECOMELHOR_API_KEY`. [Documentação do PreçoMelhor](https://www.precomelhor.com.br/desenvolvedores)

## Executar

Instale Python 3.11 ou 3.12. Para ler encartes, instale também Ollama e Tesseract com o idioma português. Confirme que `ollama` e `tesseract` estão no PATH. O modelo visual ocupa cerca de 3,2 GB em disco. A consulta ao catálogo do Savegnago pode ser usada só com Python e as dependências do projeto. [Ollama](https://ollama.com/download) · [Modelo Qwen2.5-VL 3B](https://ollama.com/library/qwen2.5vl:3b) · [Instalação do Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)

No Windows, abra o Ollama. Em um PowerShell na pasta do app, rode:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
tesseract --list-langs
ollama pull qwen2.5vl:3b
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Em Linux ou macOS, inicie o Ollama no computador e rode:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
tesseract --list-langs
ollama pull qwen2.5vl:3b
.venv/bin/python -m streamlit run app.py
```

`tesseract --list-langs` deve listar `por`. O app tenta usar a leitura de encartes quando as ferramentas estão disponíveis. Use `BUSCAI_ENCARTES_OLLAMA=0` para desligá-la ou `BUSCAI_OLLAMA_MODELO_ENCARTE` para trocar o modelo visual.

No app, selecione alguns produtos e a filial Delta Dois Córregos e clique em **Pesquisar**. Consulte a arte original e a validade em **Preços encontrados e fontes**. A primeira leitura pode levar alguns minutos, dependendo do computador e do número de páginas. A inferência usa o Ollama em `127.0.0.1:11434`, sem cobrar por chamada. O computador ainda precisa de internet para baixar os encartes publicados. [Visão no Ollama](https://docs.ollama.com/capabilities/vision) · [Saída estruturada do Ollama](https://docs.ollama.com/capabilities/structured-outputs)

## Como a consulta funciona

1. Para o Savegnago, o app identifica os produtos no catálogo oficial e simula a retirada por SKU e CEP. Compara os preços das ofertas confirmadas para a Loja 38. Para encartes, o Python baixa os arquivos oficiais vigentes. O Ollama indica os blocos com nome, embalagem e valor, e o Tesseract confere o recorte. [Simulação VTEX](https://developers.vtex.com/docs/guides/simulate-a-shopping-cart) · [Encartes do Delta](https://www.deltasuper.com.br/ofertas-piracicaba-dois-corregos/)
2. As regras comparam nome, variante, marca e quantidade. A tabela distingue compra online com retirada, encarte e coleta manual. O pedido mínimo online fica visível e o ranking exige que o subtotal dos itens comprados por esse canal o alcance. Um item pode aparecer como indisponível mesmo quando a loja o vende.
3. O SQLite reaproveita preços por 24 horas a partir da consulta original, respeitando a validade da publicação. Os resultados de um encarte servem a todos os produtos da mesma filial. Uma busca sem ofertas verificáveis pode ser repetida após duas horas. **Forçar atualização online** ignora o cache. **Usar somente preços salvos** consulta o SQLite e os registros manuais.
4. Com os preços verificados, o Buscaí calcula o ranking de cestas completas. A tabela permite consultar também os preços das cestas incompletas. O dia do preço informado pela fonte e o horário de acesso são campos distintos.

## Cobertura em Piracicaba

| Filial | Fonte |
| --- | --- |
| Delta Dois Córregos | Leitura do encarte oficial implementada. Só aparecem produtos anunciados e confirmados. [Encarte](https://www.deltasuper.com.br/ofertas-piracicaba-dois-corregos/) |
| Savegnago da Av. Professor Alberto Vollet Sachs | Catálogo oficial com preço confirmado para compra online e retirada na Loja 38. [Savegnago Piracicaba](https://www.savegnago.com.br/piracicaba) |
| Arena Atacado, loja 9 | Leitura do encarte oficial com conferência da área de publicação e das datas impressas. [Ofertas](https://www.arenaatacado.com.br/ofertas) |
| Supermercado Beira Rio | Coleta manual no app. O site publica encartes em imagem. [Site oficial](https://www.beirariosm.com.br/) |
| Assaí Nova América | Coleta manual no app. A consulta direta ao site retornou HTTP 403 no teste e a rede divulga o WhatsApp oficial de ofertas. [Assaí](https://www.assai.com.br/whatsapp) |

Opcionalmente, rode o SearXNG local com o formato JSON habilitado para localizar páginas oficiais do Savegnago quando o catálogo direto não encontrar uma oferta. No PowerShell, configure `$env:BUSCAI_SEARXNG_URL = "http://127.0.0.1:8080"` antes de iniciar o Streamlit. Cada página encontrada ainda passa pela confirmação de preço e disponibilidade na filial. [Instalação do SearXNG](https://docs.searxng.org/admin/installation-docker.html) · [API do SearXNG](https://docs.searxng.org/dev/search_api.html)

## Arquivos principais

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Fluxo do Streamlit e comparação de compras |
| `precos_reais.py` | Regras de produto, cache do catálogo e consulta usada pelo app |
| `fontes_savegnago.py` | Busca no catálogo e confirmação de preço para retirada |
| `fontes_busca_web.py` | Descoberta opcional de páginas oficiais com SearXNG |
| `fontes_encartes.py` | Filial, vigência e download dos encartes oficiais do Delta |
| `fontes_folhetos.py` | Seleção e leitura das páginas dos folhetos do Arena |
| `ollama_local.py` | Leitura de imagens pelo modelo local e conferência com Tesseract |
| `precos_encartes.py` | Cache do encarte no mesmo SQLite usado pelo app |
| `precos_manuais.py` | Cadastro e consulta de coletas manuais |
| `visual.py`, `assets/` | Estilos e imagens do Buscaí |
| `rotas.py`, `receitas.py` | Regras de rota e cálculos de receitas |

Rode `python -m pytest -q` para testar os parsers, a conferência de ofertas e o cache com respostas controladas. O download do encarte foi verificado no site oficial. A inferência visual completa ainda precisa ser medida com o Ollama rodando no computador onde o app será usado.
