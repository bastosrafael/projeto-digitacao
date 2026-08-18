# Projeto Digitação

Aplicação para conversar com IA e, em fases futuras, enriquecer planilhas de produtos. O backend possui health check, chat por meio do OmniRoute local, deploy saudável no Coolify, acesso local estável em `127.0.0.1:18001` e acesso público HTTPS pelo Tailscale Funnel.

## Arquitetura atual

```text
Navegador local
  -> React + Vite em :5173
  -> POST relativo /api/chat
  -> proxy de desenvolvimento do Vite
  -> http://127.0.0.1:18001

Internet
  -> https://projeto-digitacao.netlify.app/
  -> frontend estático no Netlify
  |  -> POST relativo /api/chat
  |  -> Netlify Function (proxy server-side)
  |  -> HTTPS Tailscale Funnel :8443
  |
  -> upload multipart/form-data direto
  -> HTTPS Tailscale Funnel :8443
  -> http://127.0.0.1:18001
  -> FastAPI no Coolify (porta interna 8000)
  -> OmniRoute na rede local (192.168.15.112:20128)
  -> rota/modelo configurado por OMNIROUTE_MODEL
  -> resposta da IA
```

O navegador nunca deve acessar o OmniRoute diretamente. A chave, quando necessária, existe somente como variável do backend.

O navegador usa somente `/api/chat`. Durante o desenvolvimento na HOMELAB, o Vite encaminha a requisição para o bind local estável. Em produção, uma Netlify Function encaminha a mesma rota ao Funnel sem expor a URL do backend na lógica do bundle.

Uploads não passam pela Netlify Function: o navegador envia `multipart/form-data` diretamente ao endpoint público do FastAPI no Funnel. Assim, o timeout de 25 segundos do proxy de chat não é reutilizado para arquivos grandes.

## Fases 6A/6B — infraestrutura e piloto de pesquisa real

O HOMELAB possui um SearXNG self-hosted em Docker, acessível somente em `http://127.0.0.1:8888`, com saída HTML/JSON e três engines gratuitas ativas: Bing Web, Mwmbl e Wiby. O OmniRoute 3.8.49 possui a conexão `searxng-search` apontando para esse endereço e o `POST /v1/search` foi validado com resultados e URLs reais, sem API comercial e sem usar LLM como mecanismo de busca.

A infraestrutura está integrada ao backend pelo `POST /api/uploads/{file_id}/research`. A rota exige 2 ou 3 `product_ids` distintos, usa no máximo quatro consultas preparadas pelo leitor para cada produto, chama o provider `searxng-search` sequencialmente e nunca usa LLM como mecanismo de busca. O frontend permanece inalterado.

Antes de qualquer IA, o backend normaliza URLs, remove parâmetros de rastreamento, deduplica resultados, bloqueia redes sociais e domínios de ruído conhecidos, pontua coincidências de código e sinais auxiliares e exige corroboração fora do título para fontes gerais. Essa última regra impede páginas de spam que apenas repetem a consulta no título. Evidências aceitas preservam título, URL, snippet, provider/engine, posição, data, consulta, score e motivos de relevância; marketplaces recebem prioridade secundária.

O cache privado fica, por padrão, em `/data/uploads/.search-cache`, indexado por provider e consulta Unicode normalizada, com validade de sete dias. A resposta informa chamadas reais, acertos de cache e `llm_used=false`. As variáveis `SEARCH_PROVIDER`, `SEARCH_CACHE_DIR` e `SEARCH_CACHE_TTL_SECONDS` permitem ajuste somente no backend.

Exemplo controlado:

```bash
curl -X POST http://127.0.0.1:18001/api/uploads/UUID/research \
  -H 'Content-Type: application/json' \
  -d '{"product_ids":["WW77#","CY2926","CY2927"],"max_queries_per_product":2}'
```

No piloto real de 13/08/2026, seis consultas dos três produtos produziram 40 resultados brutos. Todos foram corretamente descartados por falta de comprovação, inclusive páginas artificiais retornadas pela Qwant que refletiam a consulta no título; os produtos ficaram `NÃO_ENCONTRADO`. A repetição do piloto teve seis acertos de cache, zero chamadas ao gateway e nenhuma chamada a IA. A expansão para mais produtos e a análise posterior por IA gratuita ainda não foram iniciadas.

No segundo piloto controlado, um seletor determinístico escolheu `WY-2026-Y11`, `N260309#` e `CY2926` por riqueza e diversidade de metadados. O gerador usou até quatro consultas progressivas por produto: código exato, código + categoria normalizada por glossário fechado, código + fabricante/fornecedor e código + característica discriminante; NCM sem pontuação é apenas fallback. Das 64 ocorrências brutas retornadas, 64 URLs eram únicas e nenhuma sobreviveu: 40 eram evidências fracas sem confirmação além do título e 24 eram query echo artificial. A repetição teve 12 cache hits e zero chamadas ao gateway.

O diagnóstico direto do SearXNG mostrou Brave suspenso por excesso de requisições, DuckDuckGo em CAPTCHA, Mojeek com acesso negado e Qwant como única engine respondendo — justamente com resultados artificiais; em uma consulta a própria Qwant entrou em CAPTCHA. Assim, o segundo piloto ficou inconclusivo por indisponibilidade/qualidade do motor, e não demonstrou excesso de rigor do filtro. Commit, push e deploy permanecem bloqueados até existir ao menos uma fonte de busca saudável e o piloto ser repetido.

Na recuperação da base gratuita, Bing Web, Mwmbl e Wiby foram validadas e passaram a formar o conjunto ativo. O controle positivo `Raspberry Pi 5`, processado sem exceções pelo mesmo pipeline, reteve a página do produto em `raspberrypi.com` como evidência `STRONG`. Em contraste, os Styles dos Packing Lists continuaram corretamente como `NÃO_ENCONTRADO` quando só havia páginas desconexas. Esse contraste valida a camada determinística de busca, filtro e evidência sem IA; fetch de páginas e enriquecimento permanecem para a Fase 6B.3.

### Fase 6B.3 — enriquecimento controlado

O endpoint complementar `POST /api/uploads/{file_id}/research/enrich` preserva o contrato de pesquisa existente e adiciona fetch somente para evidências `STRONG` ou `MODERATE`, limitado a três páginas por produto. Produtos `NÃO_ENCONTRADO` e resultados `WEAK`, spam, query echo ou bloqueados pelo filtro não geram requisição de página.

O fetcher aceita somente HTTP/HTTPS nas portas padrão, valida DNS/IP antes de cada requisição e depois de cada redirect e bloqueia localhost, redes privadas, link-local, metadata e demais endereços não públicos. TLS permanece validado, redirects são manuais e limitados a três, timeout é explícito e o corpo HTML descomprimido é limitado a 3 MiB. Somente `text/html` e `application/xhtml+xml` são processados; PDFs, imagens e binários não são interpretados.

A extração determinística remove scripts, estilos, navegação, menus, banners de cookies e rodapés. A API retorna somente título, meta description, H1/H2, trecho textual limitado, JSON-LD útil (`Product`, `Offer`, `Brand` e `Organization`), hash SHA-256, sinais encontrados/ausentes, fatos com origem e conflitos entre Packing List e web. HTML completo nunca é devolvido.

O cache de fetch é separado do cache de search, usa parser versionado, URL canonicalizada, arquivos privados e TTL de sete dias em `/data/uploads/.fetch-cache`. Estados explícitos incluem `OK`, `BLOCKED`, `TIMEOUT`, `TOO_LARGE`, `UNSUPPORTED_CONTENT`, `HTTP_ERROR`, `SSRF_BLOCKED` e `PARSE_ERROR`. Todo processamento permanece sequencial e declara `llm_used=false`.

### Fase 6C — análise textual de evidências com IA gratuita

O endpoint `POST /api/uploads/{file_id}/research/analyze` encadeia, para somente 1 a 3 produtos explicitamente selecionados, o search e o enriquecimento já validados e então usa a IA exclusivamente como analisador das evidências fornecidas. `/research` e `/research/enrich` permanecem compatíveis. Não há pesquisa executada pelo modelo, visão, imagens, processamento em lote ou geração de descrição DUIMP.

O contexto enviado ao OmniRoute contém somente campos normalizados da Packing List, no máximo oito resultados de search aprovados e no máximo três páginas `OK`, com excerpt limitado a 2.500 caracteres, structured data compactado, matched signals, conflitos, hashes e URLs reais. HTML completo, XLSX, binários, scripts, menus, resultados `WEAK`, spam, query echo e páginas descartadas não são enviados. A rota continua configurada por `OMNIROUTE_MODEL`, com padrão `auto/coding:free`; nenhum nome de modelo final é fixado no código.

O prompt separado e versionado `evidence-analysis-v1`, em `backend/app/prompts/evidence_analysis_v1.txt`, declara conteúdo web como dado não confiável, nunca como instrução. Ele proíbe alegações de pesquisa, fontes/atributos inventados e inferência de campos ausentes. A saída é validada por Pydantic e aceita somente `FOUND`, `REVIEW` ou `NOT_FOUND`, com confiança `HIGH`, `MEDIUM` ou `LOW` calibrada novamente pelo backend. `FOUND` exige corroboração de identidade em página enriquecida e múltiplos domínios ou resultado forte de fabricante; caso contrário é rebaixado para `REVIEW`.

Proveniência usa IDs estáveis no pacote: `PACKING-001`, `SEARCH-001...` e `WEB-001...`. Valores confirmados precisam existir no conteúdo das evidências citadas. IDs inexistentes e valores inventados, mesmo com ID válido, são rejeitados. Conflitos precisam citar a Packing List e ao menos uma página web, preservar os dois valores e forçar `REVIEW`. O backend completa deterministicamente `unknown_fields` com todo campo do schema que não foi confirmado nem entrou em conflito; assim, cor, composição, fabricante ou qualquer outro atributo ausente nunca é preenchido por probabilidade.

JSON inválido ou não fundamentado recebe no máximo um retry corretivo. Nova falha, timeout, rate limit ou indisponibilidade produz `REVIEW` controlado e `llm_error` sanitizado; nunca vira `NOT_FOUND`. Quando search não encontra evidência aprovada, a IA não é chamada e a resposta retorna `NOT_FOUND`, `llm_used=false` e cache `SKIP`. O acesso ao LLM é serializado com concorrência inicial 1.

O cache próprio `llm-analysis-v1` fica em `/data/uploads/.llm-analysis-cache`, separado dos caches de search/fetch, com arquivos modo 600 e TTL padrão de sete dias. A chave inclui produto normalizado, hash do pacote de evidências, prompt version e analysis version. Em cache hit não existe nova chamada e `llm_used=false`. Logs registram `file_id`, produto, uso do LLM, prompt, quantidade/tamanho de evidências, modelo retornado, latência, decisão, confiança e cache, sem payload completo, HTML ou secrets.

No piloto real controlado de 13/08/2026, `Raspberry Pi 5` reutilizou três search cache hits e três fetch cache hits, sem nova pesquisa/fetch. O pacote de 7.644 caracteres continha oito resultados de search e duas páginas `OK`; `auto/coding:free` selecionou efetivamente `big-pickle`. Uma chamada válida em 53.605 ms retornou `FOUND/HIGH`, confirmou code, item name, manufacturer e brand com IDs existentes, manteve os demais campos como unknown e usou `llm_used=true`. O replay de cache é coberto por teste automatizado e não chama o modelo. Nenhum produto real foi submetido ao LLM porque `WY-2026-Y13` e `N260308#` não possuem evidência aprovada; ambos continuam no caminho determinístico `NOT_FOUND`, `llm_used=false`.

A Fase 6C foi implantada no Coolify pelo deployment `jxrd20pmzanimoj4r3sgmh5n`, commit `d1d125d`, sem force rebuild. Em produção, health local/público e o endpoint público de análise retornaram HTTP 200. O controle positivo no código implantado retornou `FOUND/HIGH` com o modelo efetivo `big-pickle`; o replay retornou analysis cache `HIT`, `llm_calls=0` e `llm_used=false`. `WY-2026-Y13` e `N260308#` retornaram `NOT_FOUND/LOW`, `SKIP`, zero chamadas e `llm_used=false` tanto localmente quanto pelo Funnel.

### Fases 7A/7B — visão isolada e cruzamento multimodal

A auditoria da Fase 7A validou no OmniRoute 3.8.49 o modelo gratuito visual `oc/mimo-v2.5-free`. O contrato comprovado é `POST /v1/chat/completions` com content parts OpenAI-compatible: uma parte `text` e uma parte `image_url` contendo data URL interna. A imagem não precisa ser publicada. A rota textual `OMNIROUTE_MODEL=auto/coding:free` permanece inalterada e não é usada para extrair atributos visuais.

O endpoint controlado da Fase 7B é:

```http
POST /api/uploads/{file_id}/research/multimodal
```

A requisição exige seleção explícita de um ou dois produtos. Para cada produto, o backend reutiliza a associação `code -> row -> PRODUCT_IMAGE` da Fase 5B, recupera somente a primeira `PRODUCT_IMAGE`, normaliza JPEG/PNG quando necessário para no máximo 1 MiB e lado máximo de 1280 px, e envia os bytes por data URL ao modelo configurado em `OMNIROUTE_VISION_MODEL`. Não existe endpoint público de imagem, OCR, análise de wash label/hangtag, lote ou geração de descrição DUIMP.

O prompt `visual-attribute-extraction-v1` e o schema `VisualEvidence` aceitam somente categoria visual, cor principal, mangas, alças, comprimento e detalhes visíveis, cada atributo com confiança própria. Composição, percentuais, NCM, fabricante, fornecedor, SKU, material químico, gramatura e propriedades internas entram deterministicamente como desconhecidos. Texto presente na imagem é `UNTRUSTED DATA`, nunca instrução. Ambiguidades ficam em `uncertain_attributes`; campos visuais incertos não são promovidos no resultado final.

Depois da visão, o backend cruza Packing List, search aprovado, páginas enriquecidas e `VISUAL-001` usando exclusivamente o modelo textual configurado por `OMNIROUTE_MODEL`. O prompt separado `multimodal-evidence-analysis-v1` produz schema estrito com `FOUND`, `REVIEW` ou `NOT_FOUND`, `internal_visual_match`, `external_support`, `confirmed_fields`, `conflicts`, `unknown_fields` e proveniência completa. IDs inexistentes, valores sem suporte e tentativa de comprovar campo invisível com visão são rejeitados; conflitos forçam `REVIEW`. Uma imagem não promove sozinha ausência de apoio externo para `FOUND`.

Os caches também são independentes:

- `visual-analysis-v1`: `/data/uploads/.visual-analysis-cache`, chave por hash da imagem, code, modelo, prompt, tipo e preprocessing, TTL de sete dias;
- `multimodal-analysis-v1`: `/data/uploads/.multimodal-analysis-cache`, chave por produto normalizado, hash do pacote, prompt, versão e modelo textual, TTL de sete dias.

No piloto único com `WW77#`, `IMG-00001` (JPEG, 154×199, 17.100 bytes), a visão retornou vestido rosa na altura dos joelhos, detalhes de babado/estampa/cintura e marcou a interpretação das mangas como incerta; alças permaneceram `UNKNOWN`. O cruzamento retornou `REVIEW/MEDIUM`, `internal_visual_match=UNCERTAIN` e `external_support=NONE`. Packing e visual foram preservados por `PACKING-001` e `VISUAL-001`; composição, NCM e fabricante foram sustentados somente pela Packing List, nunca pela imagem. O replay teve cache hit nas duas camadas e zero chamadas LLM.

### Fase 7C — evidências de etiquetas e hangtags

O endpoint complementar `POST /api/uploads/{file_id}/research/multimodal/labels` preserva todos os contratos existentes e adiciona extração estruturada de `WASH_LABEL` e `HANGTAG` associados pela Fase 5B. Produtos sem etiqueta ou hangtag continuam processáveis; a ausência não derruba o pipeline.

O fluxo encadeia: Packing List -> PRODUCT_IMAGE -> WASH_LABEL -> HANGTAG -> search -> web -> cruzamento textual final. Cada camada de extração visual é independente e usa o modelo visual `OMNIROUTE_VISION_MODEL`. Falhas individuais geram `label_status=ERROR` e o pipeline continua com as evidências disponíveis.

Os prompts são separados e versionados:

- `wash-label-extraction-v1`: transcrição legível, composição com percentuais somente quando claramente legíveis, validação matemática da soma, preservação do idioma original, `UNKNOWN` para texto ilegível;
- `hangtag-extraction-v1`: marca, style/code, tamanho, cor declarada, barcode candidato (sem validação GTIN), composição quando explicitamente impressa.

Os schemas Pydantic são estritos (`extra="forbid"`): `WashLabelEvidence` e `HangtagEvidence` registram `raw_visible_text`, campos extraídos com confiança individual, `uncertain_text`, `composition_sum`, `composition_sum_valid` e `warnings`. Soma de composição diferente de 100 gera `composition_percentage_sum_invalid` sem correção automática.

Proveniência usa `WASH-001` e `HANGTAG-001` como evidence IDs, preservando `PACKING-001`, `SEARCH-*`, `WEB-*` e `VISUAL-001`. O cruzamento final calcula `internal_support` (STRONG/MODERATE/WEAK/NONE) baseado na consistência entre Packing, PRODUCT_IMAGE, WASH_LABEL e HANGTAG, e `external_support` independente. Decisão conservadora: `FOUND` exige suporte externo forte ou suporte interno forte com labels corroboradas. Conflitos entre Packing e Wash (ex.: composição diferente) são registrados e forçam `REVIEW`.

Caches separados:

- `wash-label-analysis-v1`: `/data/uploads/.wash-label-cache`, TTL sete dias;
- `hangtag-analysis-v1`: `/data/uploads/.hangtag-cache`, TTL sete dias;
- `labels-multimodal-analysis-v1`: `/data/uploads/.labels-multimodal-cache`, TTL sete dias.

No piloto real com `WW77#`, a WASH_LABEL (`IMG-00002`, JPEG, 200×602, 35.838 bytes) extraiu composição em duas camadas — TELA EXTERIOR 100% POLIÉSTER e TELA INTERIOR 95% POLIÉSTER 5% ELASTANO — com origem na China e instruções de lavagem completas. O HANGTAG (`IMG-00003`, JPEG, 292×666, 59.316 bytes) identificou a marca `Liu FASHION`; demais campos (style_code, size, declared_color) permaneceram `UNKNOWN` por estarem ilegíveis. O cruzamento retornou `REVIEW/MEDIUM`, `internal_support=MODERATE` e `external_support=NONE`. A composição apresenta conflito de formato (não de substância) entre Packing List (em chinês) e Wash Label (em português), registrado e preservado. O replay teve cache hit em todas as 4 camadas e zero chamadas LLM. **FASE 7C = CONCLUÍDA.**

## Repositório

- GitHub: `https://github.com/bastosrafael/projeto-digitacao.git`
- Branch principal: `main`
- Diretório do backend: `/backend`
- Diretório do frontend: `/frontend`

## Frontend React + Vite

O frontend da Fase 4 é uma interface responsiva de chat feita com React 19 e Vite 8. Ele oferece mensagens de usuário e assistente, loading, erros amigáveis, envio com Enter, quebra de linha com Shift+Enter, limpeza da conversa, scroll automático e histórico no `localStorage` do navegador.

O botão de anexo aceita planilhas `.xlsx`, mostra nome e tamanho e permite remover o arquivo antes do envio. O upload é confirmado pelo botão Enviar e segue diretamente ao FastAPI, sem passar pela Function de chat.

### Instalação

Use Node.js compatível com Vite 8. O ambiente validado utiliza Node `22.23.2` e npm `12.0.2`.

```bash
cd /opt/projeto-digitacao/frontend
npm install
```

### Proxy de desenvolvimento

Copie o arquivo de exemplo somente se precisar alterar o destino padrão:

```bash
cd /opt/projeto-digitacao/frontend
cp .env.example .env
```

Variável disponível:

```dotenv
VITE_DEV_PROXY_TARGET=http://127.0.0.1:18001
```

Essa URL não é secret. O arquivo `.env` local não é versionado. Nenhuma variável ou chave do OmniRoute deve ser adicionada ao frontend. O desenvolvimento local não precisa passar pelo Funnel público.

O serviço de API em `src/services/api.js` chama apenas `POST /api/chat`. Em desenvolvimento, `vite.config.js` encaminha `/api` para `VITE_DEV_PROXY_TARGET` e adiciona `bypass-tunnel-reminder: true`.

### Executar e validar

```bash
cd /opt/projeto-digitacao/frontend
npm run dev -- --host 0.0.0.0
```

Endereços validados na homelab:

- local: `http://127.0.0.1:5173/`;
- LAN: `http://192.168.15.112:5173/`.

Qualidade e build de produção:

```bash
npm run lint
npm run build
```

`dist/` e `node_modules/` são artefatos locais ignorados pelo Git.

### Produção do frontend

A Fase 4B foi concluída e o frontend está publicado em:

`https://projeto-digitacao.netlify.app/`

O deploy usa o repositório GitHub `bastosrafael/projeto-digitacao`, branch `main`, e a configuração versionada no `netlify.toml`.

A configuração fica no `netlify.toml` da raiz:

- base directory: `frontend`;
- build command: `npm run build`;
- publish directory: `dist`;
- functions directory efetivo: `frontend/netlify/functions`;
- rewrite de `/api/chat` para a Function `chat`;
- fallback da SPA para `/index.html`, depois da regra da API.

A Function `frontend/netlify/functions/chat.mjs` aceita somente `POST`, valida JSON e o campo `message`, limita corpo e mensagem, aplica timeout e encaminha exclusivamente para `/api/chat`. O destino vem da variável server-side de runtime:

```dotenv
BACKEND_BASE_URL=https://nflnba.tail08f125.ts.net:8443
```

Essa variável deve ser criada no Netlify com escopo de Functions/runtime. Ela não usa prefixo `VITE_` e não entra no bundle. `OMNIROUTE_API_KEY` continua exclusivamente no backend do Coolify.

Testes locais da Function:

```bash
cd /opt/projeto-digitacao/frontend
npm run test:function
```

Validação manual de produção concluída no navegador:

- `GET https://projeto-digitacao.netlify.app/`: frontend carregado corretamente;
- interface aprovada preservada, sem alteração visual;
- envio de mensagem pelo chat concluído com resposta correta;
- fluxo confirmado: navegador -> Netlify -> Netlify Function -> Tailscale Funnel -> FastAPI/Coolify -> OmniRoute -> modelo -> resposta.

### Interface aprovada

A interface da Fase 4 está congelada. O commit visual é `fc53ebb`, marcado pela tag anotada `ui-v1-approved`. Consulte `docs/UI_APROVADA.md`. Mudanças de infraestrutura não autorizam alterações em componentes visuais, CSS ou responsividade.

## Upload XLSX

O upload aceita somente `.xlsx`, valida a estrutura mínima do workbook, armazena o arquivo e retorna seus metadados. A análise de produtos e imagens é feita separadamente pelo leitor universal da Fase 5B.

Endpoints:

- `GET /api/uploads/config`: informa o limite configurado e extensões aceitas;
- `POST /api/uploads`: recebe o campo multipart `file`, retorna HTTP 201 e um `file_id` UUID;
- `GET /api/uploads/{file_id}`: consulta os metadados persistidos de um upload novo;
- `POST /api/uploads/{file_id}/analyze`: analisa um XLSX já armazenado;
- arquivo acima do limite: HTTP 413 com detalhe sanitizado;
- extensão ou estrutura XLSX inválida: HTTP 400 e remoção do arquivo parcial.

O limite fica centralizado no backend:

```dotenv
MAX_UPLOAD_SIZE_MB=200
UPLOAD_DIR=/data/uploads
CORS_ALLOWED_ORIGINS=https://projeto-digitacao.netlify.app
```

O frontend consulta `/api/uploads/config` antes da seleção. Ele mostra nome e tamanho, permite remover pelo mesmo clipe antes do envio, rejeita antecipadamente arquivos acima do limite para melhorar a experiência e envia o `File` por `FormData`, sem Base64 e sem armazenar seu conteúdo no `localStorage`. Os estados técnicos são `selected`, `uploading`, `uploaded` e `error`. A validação definitiva permanece no backend.

O backend lê o `UploadFile` em chunks de 1 MiB, conta os bytes, calcula SHA-256 no mesmo fluxo e grava primeiro em `.part`. Se ocorrer erro ou o limite for ultrapassado, remove os parciais. Depois valida extensão, ZIP e as partes mínimas `[Content_Types].xml`, `_rels/.rels` e `xl/workbook.xml`; somente então renomeia atomicamente para `<UUID>.xlsx` com modo 600.

Uploads novos também recebem `<UUID>.json`, igualmente privado e gravado de forma atômica, contendo versão do esquema, nome original sanitizado, nome armazenado, tamanho, SHA-256 e horário UTC. O nome original nunca compõe um caminho físico. Se o sidecar falhar, o XLSX recém-gravado também é removido para não deixar estado incompleto. Uploads anteriores a essa melhoria continuam analisáveis, mas não ganham metadados retroativos automaticamente. O arquivo não é enviado ao OmniRoute.

### Storage persistente obrigatório no Coolify

O storage persistente foi configurado e validado em produção na conclusão da Fase 5A, em 2026-08-08.

Configuração recomendada no Coolify:

- tipo: Persistent Storage / bind mount gerenciado pelo Coolify;
- origem no HOMELAB: `/opt/projeto-digitacao/data/uploads`;
- destino no container: `/data/uploads`;
- leitura/escrita habilitada;
- variável `UPLOAD_DIR=/data/uploads`;
- variável `MAX_UPLOAD_SIZE_MB=200`;
- variável `CORS_ALLOWED_ORIGINS=https://projeto-digitacao.netlify.app`.

O diretório de origem está no filesystem ext4 `/dev/sda1`. Na inspeção de 2026-08-08, o filesystem tinha 106 GB totais, 67 GB utilizados e 34 GB disponíveis (67% de uso). Não foi criado quota ou volume artificialmente pequeno. Uma política de retenção/limpeza deverá ser adicionada em fase futura.

O novo container foi confirmado como `running/healthy` com bind mount `rw`, Source `/opt/projeto-digitacao/data/uploads` e Destination `/data/uploads`. Um upload público real retornou HTTP 201 e produziu um arquivo UUID com modo 600 visível tanto em `/data/uploads` quanto no diretório do host. Como o arquivo reside no Source do bind, ele não depende do filesystem efêmero nem do ciclo de vida do container.

O build do Netlify define `VITE_UPLOAD_API_BASE_URL=https://nflnba.tail08f125.ts.net:8443`. Essa URL é pública, não é secret e aparece no bundle por necessidade do upload direto. A chave do OmniRoute continua exclusivamente no Coolify.

### Validações de upload

- suíte backend: 12 testes passando, incluindo arquivo exatamente no limite, HTTP 413, falso `.xlsx`, limpeza, CORS e garantia de que o upload não chama o OmniRoute;
- suíte frontend de upload: 3 testes passando, incluindo configuração, `FormData` e erro 413;
- arquivo sintético com exatamente 36.236.835 bytes, equivalente ao porte de `IM0416-26 - PACKING LIST.xlsx`: HTTP 201 e tamanho armazenado preservado;
- imagem `projeto-digitacao-backend:upload-local`: build concluído e upload validado com bind `/opt/projeto-digitacao/data/uploads:/data/uploads`;
- arquivo persistido no teste do container com modo 600; container e artefatos temporários removidos após a validação.

**FASE 5A = CONCLUÍDA.** Backend, storage persistente, endpoints local/público, upload real e frontend Netlify foram validados. A interface visual aprovada foi preservada. A leitura ou análise do conteúdo da planilha permanece fora desta fase e deve começar somente na Fase 5B.

## Leitor universal de Packing List — Fase 5B

O backend analisa um upload existente pelo identificador controlado:

```http
POST /api/uploads/{file_id}/analyze
```

`file_id` precisa ser UUID válido. O backend resolve exclusivamente `<UPLOAD_DIR>/<UUID>.xlsx`; a API não aceita caminhos e não devolve paths absolutos, bytes de imagem ou Base64. O parsing síncrono é executado em threadpool para não bloquear o event loop do FastAPI.

### Arquitetura do parser

Os módulos ficam em `backend/app/services/spreadsheets/`:

- `parser.py`: leitura OOXML determinística de workbook, worksheets, strings, células, merges e relações de drawings;
- `detector.py`: pontuação de abas e cabeçalhos, suporte a cabeçalho fora da linha 1/multilinha, aliases multilíngues e inferência de code/style pelos valores;
- `images.py`: leitura das âncoras, dimensões, referência interna, SHA-256, classificação estrutural e reutilização de mídia;
- `normalization.py`: aliases em português, inglês e chinês, normalização de cabeçalhos/códigos e separação de texto logístico;
- `schemas.py`: contratos normalizados de análise, produtos e imagens;
- `analyzer.py`: escolha da aba principal, extração, agrupamento, associação imagem↔linha↔código e métricas.
- `duimp_policy.py`: preparação determinística de termos de pesquisa e fatos ordenados para redação, sem executar busca, classificar NCM ou completar lacunas.

A detecção de code/style reconhece títulos como `Style number`, `Code`, `Código`, `SKU`, `Model`, `款号` e `货号`. Sem título conhecido, pontua colunas por proporção e diversidade de valores compatíveis com códigos, rejeitando números sequenciais, quantidades e padrões de NCM. A resposta inclui confiança de 0 a 1.

Códigos repetidos são agrupados em um produto lógico com `row_numbers`. O valor original permanece em `code_original`/`original_values`; intervalos de caixas são separados em `packing_info`. Sufixos semânticos que distinguem um item, inclusive texto chinês não logístico, são preservados. Quando não há código identificável, o parser usa `ROW-xxxxx`, `status=REVISAR` e o warning `Código não identificado`.

As imagens são contadas por âncora, não apenas por arquivo em `xl/media`, porque uma mesma mídia pode aparecer várias vezes. Cada instância registra aba, linha/coluna de âncora, dimensões, referência OOXML e SHA-256. A coluna/cabeçalho classifica `PRODUCT_IMAGE`, `LABEL_IMAGE`, `WASH_LABEL`, `HANGTAG` ou `OTHER`; a associação ao produto usa linha lógica, merges, continuidade documental e proximidade controlada.

Quando existirem colunas correspondentes, o leitor também preserva finalidade, dimensões, peso, capacidade, tensão, potência, frequência, bateria, recarga, conexão e acessórios. Cada produto recebe `research_preparation`, com consultas formadas apenas por evidências da planilha, e `description_preparation`, com fatos comprovados na ordem recomendada para redação. Esses blocos são preparação: não indicam pesquisa web executada e não constituem classificação ou descrição DUIMP final. A política completa está em `docs/POLITICA_PESQUISA_DUIMP.md`.

### Casos reais de aceitação

| Métrica | IM0416-26 | IM0342-26 com FOB |
|---|---:|---:|
| `file_id` | `fe9759e7-be2c-4808-92ae-cf395e9bd376` | `c21b5d16-d31f-4722-8c3b-213d19360be3` |
| Abas | 1 | 3 |
| Aba principal | `总合计567箱` | `Sheet1` |
| Linhas × colunas | 169 × 16 | 175 × 23 |
| Cabeçalho | linha 1 | linha 1, repetido em outras seções |
| Code/style | coluna 5, `款号 Style number` | coluna 2, `款号` |
| Confiança | 0,99 | 0,99 |
| Âncoras de imagem | 88 | 155 |
| Imagens de produto | 64 | 109 |
| Hangtags | 16 | 10 |
| Wash labels | 0 | 36 |
| Other | 8 | 0 |
| Códigos únicos | 71 | 74 |
| Códigos repetidos | 53 | 53 |
| Duração observada | ~1,3 s | ~2,2 s |

O modelo IM0416-26 é bilíngue, usa cabeçalhos como `Picture`, `Item name`, `NCM`, `Style number` e `Ingredients`, e separa hangtag/foto em colunas próprias. O modelo IM0342-26 é predominantemente chinês, contém merges, cabeçalhos repetidos e colunas estruturais para `图片`, `款号`, `品名`, `织造方式`, `成份`, `洗水唛` e `吊牌`. O mesmo código e as mesmas regras analisam ambos; não existe condição por filename.

Limitações deliberadas desta fase:

- classificação de imagem é estrutural; não há OCR nem IA visual;
- imagens em colunas desconhecidas ficam como `OTHER`;
- fórmulas usam o valor cached existente no XLSX;
- arquivos corrompidos ou sem tabela reconhecível retornam erro controlado;
- os uploads históricos da Fase 5A não possuem sidecar; uploads novos preservam nome original sanitizado, tamanho, SHA-256 e horário UTC em JSON associado ao UUID;
- não há pesquisa web, chamada ao OmniRoute, descrição comercial ou descrição DUIMP.

**FASE 5B = CONCLUÍDA.** O commit funcional `2a60c14` foi implantado no Coolify pelo deployment `qmhtkfjr44k2gdzhxg520vxt`. O novo container ficou healthy, preservou o mount RW e os dois uploads reais retornaram HTTP 200 no endpoint de análise local e público. A Fase 5A e a UI aprovada continuam preservadas. A Fase 6 não foi iniciada.

## Requisitos do backend

- Python 3.12+
- Acesso de rede ao OmniRoute em `192.168.15.112:20128`

## Executar localmente

```bash
cd /opt/projeto-digitacao/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edite .env e informe OMNIROUTE_API_KEY sem expor a chave no frontend.
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18000
```

Teste o health check:

```bash
curl http://127.0.0.1:18000/health
```

Teste o fluxo FastAPI -> OmniRoute -> modelo:

```bash
curl -X POST http://127.0.0.1:18000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Responda somente: integração funcionando"}'
```

## Testes automatizados

```bash
cd /opt/projeto-digitacao/backend
.venv/bin/pytest -q
```

## Variáveis de ambiente

- `OMNIROUTE_BASE_URL`: URL base OpenAI-compatible, incluindo `/v1`.
- `OMNIROUTE_API_KEY`: chave usada somente pelo backend; pode ficar vazia se a instância local não exigir autenticação.
- `OMNIROUTE_MODEL`: modelo ou rota configurável (padrão `auto/coding:free`).
- `OMNIROUTE_VISION_MODEL`: modelo visual separado (padrão gratuito validado `oc/mimo-v2.5-free`).
- `OMNIROUTE_TIMEOUT_SECONDS`: timeout por tentativa.
- `OMNIROUTE_MAX_RETRIES`: quantidade de novas tentativas (0 a 5).
- `SEARCH_PROVIDER`: provider explícito do Search Gateway (padrão `searxng-search`).
- `SEARCH_CACHE_DIR`: cache privado persistente (padrão `/data/uploads/.search-cache`).
- `SEARCH_CACHE_TTL_SECONDS`: validade do cache em segundos (padrão sete dias).
- `FETCH_CACHE_DIR`: cache privado de páginas aprovadas (padrão `/data/uploads/.fetch-cache`).
- `FETCH_CACHE_TTL_SECONDS`: validade do cache de fetch (padrão sete dias).
- `FETCH_TIMEOUT_SECONDS`: timeout por página (padrão 15 segundos).
- `FETCH_MAX_BYTES`: limite do HTML descomprimido por página (padrão 3 MiB).
- `LLM_ANALYSIS_CACHE_DIR`: cache privado da análise (padrão `/data/uploads/.llm-analysis-cache`).
- `LLM_ANALYSIS_CACHE_TTL_SECONDS`: validade do cache de análise (padrão sete dias).
- `LLM_ANALYSIS_TIMEOUT_SECONDS`: timeout da única tentativa de transporte por chamada (padrão 90 segundos).
- `LLM_ANALYSIS_MAX_INPUT_CHARS`: limite do JSON de evidências enviado ao modelo (padrão 18.000 caracteres).
- `VISUAL_ANALYSIS_CACHE_DIR`: cache privado da visão (padrão `/data/uploads/.visual-analysis-cache`).
- `VISUAL_ANALYSIS_CACHE_TTL_SECONDS`: validade do cache visual (padrão sete dias).
- `VISUAL_ANALYSIS_TIMEOUT_SECONDS`: timeout da chamada visual (padrão 90 segundos).
- `VISUAL_IMAGE_MAX_BYTES`: limite após normalização (padrão 1 MiB).
- `VISUAL_IMAGE_MAX_SIDE`: maior lado após normalização (padrão 1280 px, sem ampliação).
- `MULTIMODAL_ANALYSIS_CACHE_DIR`: cache privado do cruzamento (padrão `/data/uploads/.multimodal-analysis-cache`).
- `MULTIMODAL_ANALYSIS_CACHE_TTL_SECONDS`: validade do cache multimodal (padrão sete dias).
- `MULTIMODAL_ANALYSIS_TIMEOUT_SECONDS`: timeout da análise textual final (padrão 90 segundos).
- `MULTIMODAL_ANALYSIS_MAX_INPUT_CHARS`: limite do pacote final (padrão 20.000 caracteres).
- `WASH_LABEL_CACHE_DIR`: cache privado da extração de wash labels (padrão `/data/uploads/.wash-label-cache`).
- `WASH_LABEL_CACHE_TTL_SECONDS`: validade do cache de wash labels (padrão sete dias).
- `HANGTAG_CACHE_DIR`: cache privado da extração de hangtags (padrão `/data/uploads/.hangtag-cache`).
- `HANGTAG_CACHE_TTL_SECONDS`: validade do cache de hangtags (padrão sete dias).
- `LABELS_MULTIMODAL_CACHE_DIR`: cache privado do cruzamento com labels (padrão `/data/uploads/.labels-multimodal-cache`).
- `LABELS_MULTIMODAL_CACHE_TTL_SECONDS`: validade do cache de cruzamento com labels (padrão sete dias).
- `LOG_LEVEL`: nível de log.

O cliente HTTP não segue redirecionamentos, aplica timeout, retry limitado para falhas transitórias e nunca registra a chave nos logs.

Na máquina homelab, a porta 8000 do host já está ocupada pelo Coolify. Por isso, os comandos locais acima usam 18000. Isso não muda a porta interna 8000 da imagem Docker.

## Docker

Construa a imagem a partir do diretório do backend:

```bash
cd /opt/projeto-digitacao/backend
docker build -t projeto-digitacao-backend:local .
```

Para um teste local, confirme primeiro que a porta 18001 está livre e publique somente em localhost:

```bash
docker run --name projeto-digitacao-backend-test \
  -p 127.0.0.1:18001:8000 \
  -e OMNIROUTE_BASE_URL=http://192.168.15.112:20128/v1 \
  -e OMNIROUTE_API_KEY= \
  -e OMNIROUTE_MODEL=auto/coding:free \
  projeto-digitacao-backend:local
```

A aplicação continua ouvindo em `0.0.0.0:8000` dentro do container. A porta 18001 é apenas o bind local de teste; a porta 8000 do host não deve ser publicada porque já está ocupada por um serviço existente.

Depois do teste, remova somente o container temporário:

```bash
docker stop projeto-digitacao-backend-test
docker rm projeto-digitacao-backend-test
```

## Deploy no Coolify

O deploy foi realizado manualmente por um operador autorizado e está Running/Healthy. A aplicação usa a imagem gerada pelo Dockerfile do backend, escuta em `0.0.0.0:8000` dentro do container e acessa o OmniRoute pela LAN.

### Configuração atual e referência para redeploy

No dashboard do Coolify em `http://192.168.15.112:8000`:

1. entre com uma conta autorizada;
2. selecione o projeto que contém a aplicação; a label observada no deploy atual é `my-first-project`;
3. selecione a aplicação do Projeto Digitação;
4. escolha GitHub como fonte e o repositório `bastosrafael/projeto-digitacao`;
5. selecione a branch `main`;
6. escolha build por Dockerfile;
7. configure Base Directory como `/backend` e Dockerfile como `Dockerfile`;
8. configure a porta interna/exposta como `8000` e o Port Mapping restrito a `127.0.0.1:18001:8000`;
9. configure o health check HTTP com o caminho `/health`;
10. adicione as variáveis abaixo no painel, marcando a chave como secret quando aplicável;
11. salve e acione o deploy/redeploy;
12. confirme nos logs que o Uvicorn iniciou em `0.0.0.0:8000` e que o health check ficou saudável.

Resumo da configuração:

- use `backend/` como contexto de build e `backend/Dockerfile` como Dockerfile;
- configure a porta interna da aplicação como `8000`;
- publique somente o bind local `127.0.0.1:18001:8000`; nunca use `0.0.0.0:18001` nem `8000:8000`;
- deixe o proxy/reverse proxy do Coolify encaminhar o domínio para a porta interna 8000 do container;
- configure o health check HTTP com o caminho `/health`;
- não altere o comando de inicialização da imagem, salvo necessidade comprovada.

Configure as seguintes variáveis no painel do Coolify, sem colocá-las no repositório:

```dotenv
OMNIROUTE_BASE_URL=http://192.168.15.112:20128/v1
OMNIROUTE_API_KEY=<segredo-configurado-no-coolify>
OMNIROUTE_MODEL=auto/coding:free
OMNIROUTE_VISION_MODEL=oc/mimo-v2.5-free
MAX_UPLOAD_SIZE_MB=200
UPLOAD_DIR=/data/uploads
CORS_ALLOWED_ORIGINS=https://projeto-digitacao.netlify.app
```

Se o OmniRoute local continuar sem exigir autenticação, `OMNIROUTE_API_KEY` pode permanecer vazia. A chave, quando necessária, deve existir somente como variável protegida do backend.

A imagem `projeto-digitacao-backend:local` também foi construída e validada localmente. O frontend está publicado no Netlify e o fluxo de upload/análise de XLSX está implementado no backend.

### Validação do deploy

Primeiro, confirme no Coolify que `/health` está saudável e valide a rota local estável:

```bash
curl --fail --show-error http://127.0.0.1:18001/health
curl --fail --show-error -X POST http://127.0.0.1:18001/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Responda apenas: deploy funcionando"}'
```

O segundo teste comprova o fluxo Coolify -> `192.168.15.112:20128` -> OmniRoute -> modelo. Se falhar, verifique primeiro os logs da aplicação e a conectividade de saída do container, sem alterar redes globais ou o OmniRoute.

### URL pública

- Projeto Digitação: `https://nflnba.tail08f125.ts.net:8443`.
- NFLNBA: `https://nflnba.tail08f125.ts.net` na porta HTTPS padrão 443.
- O mesmo hostname oficial do node Tailscale é usado com listeners distintos; não existe hostname arbitrário fora de `*.ts.net`.
- A porta pública 8443 encaminha para `http://127.0.0.1:18001`; o backend continua inacessível diretamente pela LAN nessa porta.
- O TLS é terminado pelo Tailscale, e a configuração fica persistida no estado oficial do `tailscaled`.

Configuração aplicada com Tailscale 1.102.2:

```bash
sudo tailscale funnel --bg --yes --https=8443 http://127.0.0.1:18001
tailscale funnel status
```

O listener do Projeto Digitação pode ser removido isoladamente, sem resetar o NFLNBA:

```bash
sudo tailscale funnel --https=8443 off
```

### Estabilidade do acesso

A dependência do hostname efêmero do container Coolify foi eliminada. O Port Mapping persistido no Coolify é `127.0.0.1:18001:8000`, e o Tailscale Funnel encaminha diretamente para esse endereço. Assim, um redeploy que troque o nome do container backend não altera o destino público.

Na Fase 3D, o LocalTunnel não preservou subdomínios solicitados após reinícios. Depois da validação externa do Funnel e da confirmação de que NFLNBA continuava saudável, o container `localtunnel-projeto-digitacao` foi parado e removido. Imagens, volumes e redes foram preservados.

Configuração antiga preservada somente para rollback: imagem `node:20-alpine`, `network_mode=host`, restart `unless-stopped` e comando `lt --port 18001 --local-host 127.0.0.1 --subdomain bastosrafael-projeto-digitacao-homelab-api --print-requests`. Ela não é necessária na arquitetura atual.

Validações da Fase 3E:

- `GET https://nflnba.tail08f125.ts.net:8443/health`: HTTP 200, Uvicorn e `{"status":"ok"}`;
- `POST https://nflnba.tail08f125.ts.net:8443/api/chat`: HTTP 200 e resposta via OmniRoute;
- NFLNBA em 443: `/`, `/api/health`, `/api/games/upcoming?league=NFL` e `/nfl` permaneceram HTTP 200;
- `tailscale funnel status` manteve simultaneamente os listeners 443 e 8443.

## Fase 8B — gerador técnico DUIMP generalizado

O gerador de descrição técnica DUIMP foi generalizado para funcionar com diferentes níveis de evidência. O endpoint `POST /api/uploads/{file_id}/duimp/generate` aceita 1 produto por request.

### Gate de suficiência

Antes de chamar o LLM, o serviço avalia deterministicamente se há evidência mínima:

- Pelo menos 1 campo essencial: `category` ou `item_name` (CONFIRMED).
- Pelo menos 1 campo de suporte: `composition` ou `construction` (CONFIRMED).
- NCM sozinho NÃO é suficiente.
- Conflito em campo essencial bloqueia geração.
- Conflito em campo de suporte (composition/construction) não bloqueia — tratado via confidence MEDIUM.

Se insuficiente: `INSUFFICIENT_EVIDENCE`, `llm_used=false`, sem texto gerado.

### Packing fallback

Quando o resultado `labels_multimodal` não existe para um produto, o endpoint lê a packing list diretamente do XLSX via `analyze_workbook`, constrói um `labels_result` parcial e combina com evidências visuais/wash/hangtag em cache. O campo `packing_fallback: true` indica que essa rota foi usada.

### Normalizações

- **Composição chinesa**: parser determinístico para strings como `100涤` → 100% poliéster, `95棉5氨纶+100pu` → 2 camadas (95% algodão + 5% elastano; 100% PU). Soma > 100% retorna UNKNOWN.
- **Item name parcial**: `梭织女士套装` contém `套装` → conjunto; `梭织长裤+腰带` contém `长裤` → calça.
- **Construction**: `梭织` → tecido plano, `针织` → malha.

### Resultado

Campos adicionais na resposta: `packing_fallback` (bool), `sufficiency_reason` (string).

Piloto validado com 3 produtos: WW77# (GENERATED/MEDIUM), CY2926 (GENERATED/HIGH via packing fallback), N260309# (GENERATED/HIGH com composição de 2 camadas). 189 testes passando.
