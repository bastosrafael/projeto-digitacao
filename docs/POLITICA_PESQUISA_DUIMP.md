# Política de pesquisa e redação DUIMP

Versão: `duimp-v1`

Este documento consolida somente as regras reutilizáveis das memórias DUIMP fornecidas. Os exemplos históricos de NCM não são uma tabela de decisão e não devem ser aplicados automaticamente a produtos semelhantes.

## Pesquisa

A consulta deve partir apenas de evidências já presentes no produto normalizado: código/modelo, nome, NCM informada na planilha, marca, fabricante, fornecedor, composição e construção. Código e identidade do fabricante têm prioridade para reduzir homônimos.

A NCM recebida da planilha pode ser usada como termo de pesquisa, mas permanece uma alegação a validar. Ela não confirma a classificação e não deve ser usada para adaptar artificialmente a descrição.

As fontes devem ser priorizadas nesta ordem:

1. fabricante;
2. fornecedor oficial;
3. catálogo ou ficha técnica oficial;
4. distribuidor confiável;
5. loja especializada;
6. marketplace apenas como evidência secundária.

Cada resultado aproveitado deverá preservar URL real, título, origem, data de consulta, trecho factual relevante e o campo do produto que ele sustenta ou contradiz. Ausência de pesquisa real deve permanecer explícita; o modelo não pode inventar URL, fonte ou resultado.

### Foco por categoria

- Vestuário: tipo da peça, público quando comprovado, malha ou tecido plano, composição percentual e construção relevante.
- Elétricos e eletrônicos: função, funcionamento, tensão, potência, frequência, alimentação, bateria, recarga, conexão, dimensões e acessórios integrantes.
- Partes e acessórios: declarar que é parte/acessório, identificar o equipamento de destino, função, material e construção.
- Demais produtos: natureza, finalidade, material/composição e especificações que individualizam a mercadoria.

## Redação

A descrição final deverá ordenar somente fatos comprovados:

1. natureza ou tipo do produto;
2. função ou finalidade;
3. material ou composição;
4. construção e funcionamento relevantes;
5. dimensões, peso, capacidade, tensão, potência e frequência, quando pertinentes;
6. alimentação, bateria, recarga e conexão, quando pertinentes;
7. cor e tamanho quando contribuírem para individualização;
8. código/modelo, marca, fabricante e acessórios relevantes.

A redação deve ser técnica, objetiva, neutra e suficiente para individualizar a mercadoria. Não usar linguagem promocional, copiar anúncios, completar lacunas por probabilidade ou afirmar polímero/composição específica com base apenas em aparência. Para material apenas visualmente reconhecível, usar formulação genérica como “material plástico” até existir evidência técnica.

A NCM é contexto de classificação e deve ficar em campo próprio da saída; ela não é inserida automaticamente no texto descritivo.

Quando houver conflito, preservar as versões e respectivas fontes, reduzir a confiança e marcar `REVISAR`. Produto completo, parte, acessório e conjunto não são equivalentes. Se houver duas NCMs possíveis, registrar a divergência e a característica que precisa ser confirmada; nunca escolher apenas por semelhança com um caso histórico.

## Implementação

O leitor de planilhas extrai, quando existirem, finalidade, dimensões, peso, capacidade, tensão, potência, frequência, bateria, recarga, conexão e acessórios. Para cada produto, a resposta de análise inclui:

- `research_preparation`: consultas determinísticas, termos de evidência, foco técnico, campos ausentes e avisos;
- `description_preparation`: fatos verificados em ordem de redação, campos ausentes e versão desta política.

Esses blocos preparam as fases seguintes. Eles não significam que uma pesquisa web foi executada nem constituem uma descrição DUIMP final.
