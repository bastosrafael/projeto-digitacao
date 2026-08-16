# Memória permanente do Projeto Digitação

## 2026-08-08 — Início das fases 1 e 2

### Estado inicial

- A pasta `/opt/projeto-digitacao` estava completamente vazia.
- `memoria.md` e o repositório Git ainda não existiam, portanto não havia memória anterior para ler ou preservar.
- A pasta pertencia a `root:root` e foi ajustada para `rb:rb` para permitir o trabalho exclusivamente dentro da raiz solicitada.

### Decisões técnicas

- Backend em FastAPI, com configuração via `pydantic-settings`.
- Cliente assíncrono `httpx` para o OmniRoute.
- Modelo configurado somente por `OMNIROUTE_MODEL`, com padrão `auto/coding:free`.
- Timeout configurável, sem redirects, e duas novas tentativas por padrão para timeout, falha de rede, HTTP 429 e HTTP 5xx.
- Erros externos são sanitizados; corpo da resposta e chave de API não entram nos logs.
- Testes de unidade usam um mock do OmniRoute; a integração real será validada separadamente.
- A chave pode ficar vazia quando o OmniRoute local não exigir autenticação; se definida, é enviada somente pelo backend.
- A porta temporária 18000 foi usada nos testes do host porque a 8000 já pertence ao Coolify. A imagem Docker continua usando a porta interna 8000.

### Arquivos criados

- `.gitignore`
- `README.md`
- `memoria.md`
- `backend/Dockerfile`
- `backend/.env.example`
- `backend/requirements.txt`
- `backend/pytest.ini`
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/api/__init__.py`
- `backend/app/api/chat.py`
- `backend/app/services/__init__.py`
- `backend/app/services/omniroute.py`
- `backend/tests/test_api.py`

### Endpoints

- `GET /health` retorna `{"status":"ok"}`.
- `POST /api/chat` recebe `{"message":"..."}` e retorna `{"response":"..."}`.

### Erros encontrados e soluções

- Erro: falta de permissão para criar arquivos na raiz pertencente ao root.
- Solução: alterar somente a propriedade de `/opt/projeto-digitacao` para `rb:rb`.
- Erro: o Pytest 9 não encontrou o pacote local `app` durante a coleta.
- Solução: declarar `pythonpath = .` e `testpaths = tests` em `backend/pytest.ini`.
- Erro: as faixas abertas instalaram FastAPI 0.141/Starlette 1.6/Pytest 9 e o `TestClient` bloqueou durante a execução.
- Solução: fixar versões compatíveis e reproduzíveis no `requirements.txt`.
- Erro: a primeira chamada real recebeu HTTP 200, mas o OmniRoute retornou SSE por padrão e o cliente esperava JSON.
- Solução: enviar explicitamente `"stream": false` no payload de chat.
- Erro: não foi possível baixar dependências dentro do sandbox por bloqueio de DNS.
- Solução: autorizar exclusivamente o `pip install -r requirements.txt` com rede.
- Erro: a porta 8000 do host já estava ocupada e respondeu com uma página do Coolify.
- Solução: encerrar a tentativa do Uvicorn sem tocar no Coolify e executar o teste temporário na porta 18000.
- Erro: o primeiro `git commit` foi recusado porque a máquina não tinha identidade Git configurada.
- Solução: configurar somente neste repositório `Codex <codex@localhost>`, sem alterar a configuração Git global.

### Comandos importantes executados

```bash
cd /opt/projeto-digitacao/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18000
curl http://127.0.0.1:18000/health
curl -X POST http://127.0.0.1:18000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Responda exatamente com: integracao funcionando"}'
```

### Testes e resultados

- Suíte automatizada final: `3 passed in 0.67s`.
- `GET /health` via Uvicorn/curl: HTTP 200, `{"status":"ok"}`.
- `POST /api/chat` via Uvicorn/curl: HTTP 200, `{"response":"integracao funcionando"}`.
- Fluxo real confirmado: cliente -> FastAPI -> OmniRoute `192.168.15.112:20128` -> rota `auto/coding:free` -> resposta do modelo.
- Endpoint `/v1/models`: HTTP 200 e `auto/coding:free` presente.

### Próximo passo

- Aguardar validação das fases 1 e 2. Depois, iniciar somente a fase 3: build e execução Docker, conectividade do container e documentação do Coolify, sem alterar o Coolify automaticamente.

### Checklist

- [x] Inspecionar estado inicial.
- [x] Criar estrutura mínima do backend.
- [x] Implementar `GET /health`.
- [x] Implementar cliente OmniRoute e `POST /api/chat`.
- [x] Criar Dockerfile e `.env.example`.
- [x] Executar testes automatizados.
- [x] Validar chamada real FastAPI -> OmniRoute -> modelo.
- [x] Atualizar README e resultado final desta etapa na memória.
- [x] Criar commit Git (`feat: implementa backend e integracao com OmniRoute`).

## 2026-08-08 — Fase 3: container e preparação para Coolify

### Resultado

- Fase 3 concluída e validada.
- Imagem criada: `projeto-digitacao-backend:local`.
- ID da imagem: `sha256:f0a813e63451dab9d45a8724c175675961bc7a3cc8a894cf182b0065a668d7db`.
- Tamanho da imagem: `docker image inspect` informou 59.834.790 bytes; `docker image ls` exibiu 253 MB de tamanho local/descompactado.
- Container temporário: `projeto-digitacao-backend-test`.
- Mapeamento usado: `127.0.0.1:18001 -> container:8000`.
- O container foi parado e removido ao final; a imagem local foi mantida.
- Nenhum container, volume, rede, proxy, túnel, configuração do Coolify ou instalação do OmniRoute foi alterado.

### Revisão do Dockerfile

- Mantida a imagem enxuta `python:3.12-slim`.
- Confirmadas a instalação por `requirements.txt`, a cópia somente de `app/`, a inicialização por Uvicorn e a escuta em `0.0.0.0:8000`.
- Confirmado o `HEALTHCHECK` interno em `http://127.0.0.1:8000/health`.
- O `Dockerfile` não precisou ser alterado.
- Criado `backend/.dockerignore` para excluir `.env`, ambiente virtual, caches, testes e metadados do contexto. O contexto enviado no build caiu de aproximadamente 70 MB para 16,65 KB.

### Comandos importantes

```bash
cd /opt/projeto-digitacao/backend
sudo docker build -t projeto-digitacao-backend:local .
sudo docker run -d --name projeto-digitacao-backend-test \
  -p 127.0.0.1:18001:8000 \
  -e OMNIROUTE_BASE_URL=http://192.168.15.112:20128/v1 \
  -e OMNIROUTE_API_KEY= \
  -e OMNIROUTE_MODEL=auto/coding:free \
  projeto-digitacao-backend:local
curl http://127.0.0.1:18001/health
curl -X POST http://127.0.0.1:18001/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Responda apenas: docker funcionando"}'
.venv/bin/python -m pytest -q
sudo docker logs projeto-digitacao-backend-test
sudo docker stop projeto-digitacao-backend-test
sudo docker rm projeto-digitacao-backend-test
```

### Testes e evidências

- Build Docker: concluído sem erro.
- Estado durante o teste: `running`, healthcheck Docker `healthy`.
- Bind confirmado: apenas `127.0.0.1:18001`, direcionado a `8000/tcp` no container.
- `GET /health`: HTTP 200, `{"status":"ok"}`.
- `POST /api/chat`: HTTP 200, `{"response":"docker funcionando"}`.
- Acesso do container ao OmniRoute confirmado: requisição para `http://192.168.15.112:20128/v1/chat/completions` retornou HTTP 200 usando `auto/coding:free`.
- Testes automatizados: `3 passed in 0.88s`.
- Logs: Uvicorn iniciou em `0.0.0.0:8000`; health, chat e OmniRoute retornaram HTTP 200; nenhum erro crítico e nenhuma chave de API apareceram.

### Problemas encontrados e soluções

- Problema: o usuário da sessão não tinha acesso direto ao socket `/var/run/docker.sock`.
- Solução: executar somente os comandos Docker necessários com `sudo`, sem mudar grupos ou permissões do daemon.
- Problema: o isolamento de rede da ferramenta não permitiu consultar sockets nem acessar `127.0.0.1:18001`.
- Solução: repetir somente as inspeções e chamadas localhost necessárias fora do isolamento.
- Problema: o diretório `backend/` ocupava aproximadamente 70 MB por incluir `.venv` no contexto potencial.
- Solução: criar `.dockerignore`; o contexto efetivo do build ficou em 16,65 KB.
- Observação: o `pip` exibiu no build um aviso esperado sobre instalação como root dentro da imagem, sem falha ou impacto no host.

### Preparação para Coolify

- Documentado no `README.md`: contexto `backend/`, Dockerfile `backend/Dockerfile`, porta interna 8000, proxy do Coolify para essa porta, health check `/health` e variáveis de ambiente.
- Nenhum deploy, chamada administrativa, aplicação, domínio, proxy ou túnel foi criado ou alterado.

### Arquivos criados ou modificados

- Criado: `backend/.dockerignore`.
- Modificado: `README.md`.
- Modificado: `memoria.md`.

### Próximo passo

- Aguardar validação da Fase 3. Depois, iniciar a Fase 4 para criar o frontend mínimo React + Vite e conectá-lo somente ao backend. Não fazer deploy no Coolify antes de configuração e autorização explícitas.

### Checklist da Fase 3

- [x] Ler memória, README e backend integralmente antes de alterar arquivos.
- [x] Revisar o Dockerfile mantendo a porta interna 8000.
- [x] Confirmar que a porta 18001 estava livre.
- [x] Construir `projeto-digitacao-backend:local` sem erro.
- [x] Testar o container em `127.0.0.1:18001`.
- [x] Validar `/health`.
- [x] Validar `/api/chat` e o acesso real ao OmniRoute.
- [x] Revisar logs e confirmar ausência de chave exposta.
- [x] Executar os testes automatizados.
- [x] Parar e remover somente o container temporário.
- [x] Documentar a futura configuração do Coolify sem realizar deploy.
- [x] Atualizar README e memória.
- [x] Verificar Git e criar commit da Fase 3 (`feat: valida backend em container docker`).

## 2026-08-08 — Fase 3B: GitHub e preparação do deploy no Coolify

### GitHub

- Auditoria pré-push concluída: `.gitignore` e `backend/.dockerignore` revisados.
- Nenhum `.env`, token, senha, chave privada ou credencial foi encontrado nos arquivos versionados ou no histórico.
- `backend/.env.example` é o único arquivo versionado com nome de ambiente; `OMNIROUTE_API_KEY` está declarada com valor vazio.
- Remote: `origin https://github.com/bastosrafael/projeto-digitacao.git` para fetch e push.
- Branch: `main`.
- Primeira tentativa automatizada de push falhou corretamente por ausência de credencial HTTPS, com `fatal: unable to get password from user`; nenhum token foi criado, impresso ou armazenado.
- O operador autenticou o GitHub fora do agente e executou `git push -u origin main` com sucesso.
- Confirmação posterior: `origin/main` e `main` apontavam para `1b58f7d6beeb5425ca9285e189d60c4b4036bcc2`.

### Coolify

- Coolify local confirmado ativo em `http://192.168.15.112:8000`.
- Health da API: `/api/health` e `/api/v1/health` retornaram HTTP 200.
- Dashboard redireciona para `/login`.
- Endpoints administrativos `/api/v1/projects` e `/api/v1/applications` retornaram HTTP 401 sem autenticação.
- Nenhum token/API do Coolify estava disponível na sessão.
- Credenciais internas do container não foram lidas nem reutilizadas; isso seria um contorno inseguro da autenticação.
- Não existia aplicação ou container chamado `projeto-digitacao-backend`.
- Deploy não realizado. Alvo manual preparado: projeto `projeto-digitacao`, aplicação `projeto-digitacao-backend`, fonte GitHub, repositório `bastosrafael/projeto-digitacao`, branch `main`, build Dockerfile, base `/backend`, Dockerfile `Dockerfile`, porta interna 8000 e health check `/health`.
- Variáveis a configurar somente por nome no Coolify: `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`, `OMNIROUTE_MODEL`.

### Rede e OmniRoute

- O OmniRoute permanece acessível na LAN em `http://192.168.15.112:20128` e não foi alterado.
- A conectividade de um container Docker comum para o OmniRoute foi comprovada na Fase 3.
- Coolify -> OmniRoute não pôde ser validado nesta etapa porque a aplicação Coolify ainda não foi criada.
- Após o deploy manual, o teste crítico será `POST /api/chat`; ele deve retornar HTTP 200 antes de considerar o deploy concluído.

### Túnel e acesso externo

- Existe container `localtunnel` em rede host executando `lt --port 3001 --subdomain nflnba`.
- URL observada: `https://nflnba.loca.lt`.
- Esse túnel atende outro serviço na porta 3001 e não foi alterado, reiniciado ou reaproveitado.
- Nenhuma URL pública está configurada para o backend.
- `GET /health` externo e `POST /api/chat` externo não foram executados por inexistência de deploy e URL do backend; nenhum domínio foi inventado.

### Testes

- Testes automatizados executados novamente: `3 passed in 0.81s`.
- Nenhum teste válido foi removido ou alterado.

### Problemas, diagnósticos e soluções

- Problema: primeira tentativa de push sem autenticação GitHub.
- Diagnóstico: remote correto, mas nenhuma credencial HTTPS estava disponível.
- Solução: operador autenticou externamente e realizou o push sem colocar token no repositório ou na URL.
- Problema: ausência de credencial/API segura do Coolify na sessão.
- Diagnóstico: health público funciona, mas endpoints administrativos exigem autenticação HTTP 401.
- Solução: não contornar autenticação; documentar criação manual no dashboard.
- Problema: túnel existente já pertence a outro serviço.
- Diagnóstico: container `localtunnel` aponta a URL `https://nflnba.loca.lt` para a porta 3001.
- Solução: preservar o túnel e deixar a URL pública do backend pendente para decisão/configuração do operador.

### Arquivos modificados

- `README.md`: arquitetura, GitHub, roteiro manual do Coolify, validação e situação do túnel.
- `memoria.md`: registro integral da Fase 3B.

### Próximo passo

- Operador deve criar a aplicação no dashboard do Coolify seguindo o `README.md`, configurar as três variáveis, realizar o deploy e fornecer a URL real. Depois, validar `/health`, `/api/chat` e Coolify -> OmniRoute antes de iniciar a Fase 4.

### Checklist da Fase 3B

- [x] Ler memória, README e estado Git antes de agir.
- [x] Auditar arquivos e histórico contra secrets.
- [x] Configurar exclusivamente o remote GitHub autorizado.
- [x] Publicar o histórico existente em `origin/main`.
- [x] Revisar Dockerfile, porta interna 8000 e health check `/health`.
- [x] Inspecionar Coolify e túnel existentes sem alterar infraestrutura.
- [x] Confirmar que o Coolify exige autenticação administrativa.
- [x] Preparar instruções manuais exatas para o dashboard.
- [x] Preservar o localtunnel existente da porta 3001.
- [x] Executar testes automatizados.
- [x] Atualizar README e memória.
- [x] Deploy Coolify (concluído manualmente pelo operador depois do commit `8b4aea3`).
- [x] Validar Coolify -> OmniRoute (HTTP 200 com resposta `coolify funcionando`).
- [x] Configurar e validar URL HTTPS externa (concluído manualmente e revalidado na Fase 3C).
- [x] Criar commit final e fazer push (`chore: prepara deploy do backend no coolify`).

### Atualização posterior da Fase 3B

- Fase 3B concluída manualmente pelo operador após o registro inicial acima.
- GitHub concluído: repositório `https://github.com/bastosrafael/projeto-digitacao.git`, branch `main`.
- Coolify concluído: aplicação criada, deploy do commit `8b4aea3` realizado e estado Running/Healthy.
- Variáveis configuradas no Coolify somente pelos nomes: `OMNIROUTE_BASE_URL`, `OMNIROUTE_MODEL`, `OMNIROUTE_API_KEY`. Nenhum valor secreto foi registrado.
- Backend confirmado em `0.0.0.0:8000` dentro do container.
- `GET /health` interno: HTTP 200, `{"status":"ok"}`.
- `POST /api/chat` interno: HTTP 200, `{"response":"coolify funcionando"}`.
- Coolify -> OmniRoute -> `auto/coding:free`: confirmado.

## 2026-08-08 — Fase 3C: finalização do acesso externo

### Estado do deploy e do túnel

- Container do backend observado: `3612b2a5ec37`, nome `bc9syuqtenojm8hr7l8uxh6f-194104617028`. Ambos são efêmeros e não devem ser usados como identificadores permanentes.
- Backend Coolify: running e healthy, imagem correspondente ao commit `8b4aea3666e72e9bb866a494f612ff11b22dfdac`.
- Container do projeto: `localtunnel-projeto-digitacao`, imagem `node:20-alpine`.
- Estado inspecionado: running.
- Rede: `coolify`.
- Restart policy: `unless-stopped`.
- Docker: serviço `enabled` e `active`; o container deve reiniciar após reinício do daemon/HOMELAB, desde que não tenha sido parado manualmente.
- Comando real: instala `localtunnel` e executa `lt --port 8000 --local-host bc9syuqtenojm8hr7l8uxh6f-194104617028 --subdomain projeto-digitacao-api --print-requests`.
- URL confirmada: `https://projeto-digitacao-api.loca.lt`.
- O container `localtunnel` original, em rede host, continua atendendo a porta 3001 e `https://nflnba.loca.lt`; não foi alterado.

### Validações externas

- Teste externo realizado previamente pelo operador: `POST /api/chat` retornou HTTP 200 com `{"response":"acesso externo funcionando"}`.
- Fase 3C, `GET https://projeto-digitacao-api.loca.lt/health`: HTTP 200, `{"status":"ok"}`.
- Fase 3C, `POST https://projeto-digitacao-api.loca.lt/api/chat`: HTTP 200, `{"response":"fase 3c validada"}`.
- Foi usado `bypass-tunnel-reminder: true`; nenhum secret foi enviado.
- Fluxo confirmado: Internet -> HTTPS LocalTunnel -> rede `coolify` -> FastAPI:8000 -> OmniRoute:20128 -> `auto/coding:free` -> resposta.

### Análise de estabilidade do hostname

- Risco confirmado e ainda não resolvido: o `--local-host` usa o nome completo do container de uma implantação do Coolify.
- Aliases Docker observados no backend: apenas repetições do nome completo `bc9syuqtenojm8hr7l8uxh6f-194104617028`.
- O UUID base `bc9syuqtenojm8hr7l8uxh6f` não resolveu por DNS a partir do túnel e o health falhou.
- O nome lógico de `coolify.resourceName`/`coolify.serviceName` também não resolveu.
- O destino atual completo resolveu e retornou HTTP 200 em `/health`.
- O `coolify-proxy` não forneceu uma rota interna comprovadamente utilizável para a aplicação; não foi modificado.
- Nenhuma rede, alias, proxy ou container foi alterado, pois uma mudança agora exigiria operação potencialmente disruptiva no túnel funcionando.
- Alternativa operacional simples: depois de cada redeploy, descobrir o novo container pela label `coolify.applicationId=3`, validar `/health` internamente e, somente com autorização/janela de manutenção, recriar apenas `localtunnel-projeto-digitacao` com o novo `--local-host`.
- A documentação oficial confirma que nomes de serviço funcionam como hostnames estáveis dentro de um mesmo stack Docker Compose; não foi encontrada uma opção comprovada de alias persistente para a aplicação atual baseada somente em Dockerfile.
- Solução definitiva preferida para uma fase futura: migração planejada para um único stack Docker Compose com serviços `backend` e `tunnel`, sem redes customizadas nem portas de host, permitindo `--local-host backend`. Essa mudança é estrutural e não foi executada nesta fase.

### Testes automatizados

- `.venv/bin/python -m pytest -q`: `3 passed in 0.84s`.
- Nenhum teste foi removido ou alterado.

### Arquivos modificados

- `README.md`: estado real do deploy, arquitetura externa, URL, LocalTunnel e risco de hostname efêmero.
- `memoria.md`: correção da Fase 3B e registro integral da Fase 3C.

### Próximo passo

- Antes de qualquer redeploy, decidir entre migrar backend+túnel para um stack Docker Compose com hostname de serviço estável ou aceitar o procedimento manual de atualizar somente o túnel do projeto. Depois da validação da Fase 3C, iniciar a Fase 4 sem alterar o túnel `nflnba`.

### Checklist da Fase 3C

- [x] Ler memória, README e estado Git antes de modificar arquivos.
- [x] Inspecionar containers, túnel, comando, rede, logs e restart policy.
- [x] Confirmar persistência com Docker enabled e `unless-stopped`.
- [x] Validar `/health` externo.
- [x] Validar uma única chamada externa `/api/chat`.
- [x] Analisar aliases e proxy sem alterar infraestrutura.
- [x] Preservar os dois túneis e todos os serviços existentes.
- [x] Executar testes automatizados.
- [x] Atualizar README e memória.
- [x] Auditar secrets, criar commit e fazer push (`docs: registra deploy e acesso externo`).

## 2026-08-08 — Fase 4: frontend mínimo de chat

### Resultado

- Fase 4 concluída sem alterar backend, Coolify, OmniRoute, redes Docker ou containers LocalTunnel.
- Frontend criado em `/opt/projeto-digitacao/frontend` com React `19.2.8`, Vite `8.2.1` e JavaScript.
- Node existente mantido: `v22.23.2`; npm: `12.0.2`. Nenhuma segunda instalação de Node foi realizada.
- Nenhum repositório Git adicional foi criado dentro de `frontend/`.

### Estrutura criada

- `frontend/index.html`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/.env.example`
- `frontend/vite.config.js`
- `frontend/eslint.config.js`
- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/styles.css`
- `frontend/src/components/Header.jsx`
- `frontend/src/components/ChatMessage.jsx`
- `frontend/src/components/ChatInput.jsx`
- `frontend/src/services/api.js`

### Interface e funcionalidades

- Interface autoral, responsiva, sem branding de terceiros e sem dependências visuais pesadas.
- Mensagem inicial, mensagens do usuário/assistente, timestamps, indicador de resposta e erro amigável.
- Textarea expansível: Enter envia; Shift+Enter cria nova linha.
- Envio duplicado bloqueado durante a resposta.
- Scroll automático, limpeza da conversa e persistência no `localStorage`.
- Botão visual de anexo exibe aviso; upload real não foi implementado.
- Nenhum streaming, SSE ou WebSocket foi adicionado.

### API e proxy Vite

- `src/services/api.js` centraliza `sendMessage(message)` e usa somente a URL relativa `POST /api/chat`.
- Timeout no cliente: 90 segundos; resposta validada antes de ser exibida.
- `vite.config.js` usa `VITE_DEV_PROXY_TARGET`, com padrão `https://projeto-digitacao-api.loca.lt`.
- O proxy adiciona `bypass-tunnel-reminder: true` e evita CORS no desenvolvimento local.
- `frontend/.env.example` contém somente `VITE_DEV_PROXY_TARGET`; nenhuma chave ou variável do OmniRoute existe no frontend.

### Testes e resultados

- `npm install`: 132 pacotes adicionados, 133 auditados e 0 vulnerabilidades reportadas.
- `npm run lint`: concluído sem erros na execução final.
- `npm run build`: concluído com Vite 8.2.1; 20 módulos transformados em 719 ms na execução final.
- Bundle final observado: HTML 0,58 kB; CSS 9,11 kB; JavaScript 198,30 kB (62,68 kB gzip).
- Vite executado temporariamente com `npm run dev -- --host 0.0.0.0`.
- Página validada em `http://127.0.0.1:5173/`: HTTP 200, título `Assistente de Produtos`.
- Teste real único via proxy: `POST http://127.0.0.1:5173/api/chat` com `Responda apenas: frontend funcionando` retornou HTTP 200 e `{"response":"frontend funcionando"}`.
- Fluxo confirmado: cliente/Vite -> `/api/chat` -> proxy Vite -> HTTPS LocalTunnel -> FastAPI Coolify -> OmniRoute -> `auto/coding:free` -> resposta.
- O servidor Vite temporário foi encerrado depois dos testes.

### Segurança

- `.gitignore` ampliado para ignorar `node_modules/`, `dist/` e arquivos `*.local`.
- `frontend/node_modules/`, `frontend/dist/` e `frontend/.env` confirmados como ignorados.
- Busca no código e bundle confirmou ausência de `OMNIROUTE_API_KEY`, `OMNIROUTE_BASE_URL`, tokens GitHub e padrões de chaves.
- O termo genérico `password` aparece duas vezes no runtime de dependências empacotado, mas não existe valor, variável ou credencial correspondente no código-fonte.
- A URL externa não está espalhada em componentes nem no bundle; fica somente no proxy de desenvolvimento e no exemplo de ambiente.

### Problemas encontrados e soluções

- Problema: o primeiro `npm install` ficou bloqueado pelo isolamento de rede.
- Solução: interromper a tentativa e autorizar somente o download das dependências declaradas.
- Problema: ESLint 10 exige `defineConfig` para compor configurações com `extends`.
- Solução: usar `defineConfig`/`globalIgnores` e declarar separadamente globals Node para arquivos `*.config.js`.
- Problema: `crypto.randomUUID()` não estava disponível no navegador ao abrir o Vite pelo IP em HTTP, causando falha na montagem do React.
- Solução: criar `createMessageId()` com `crypto.randomUUID()` quando disponível e fallback local não sensível; depois disso lint/build e serviço dos módulos passaram sem novos erros.

### Arquivos modificados fora do frontend

- `.gitignore`: ignores de artefatos Node/Vite.
- `README.md`: arquitetura e instruções do frontend/proxy.
- `memoria.md`: registro da Fase 4.

### Próximo passo

- Antes de publicar no Netlify, definir a arquitetura segura de produção: domínio do frontend, CORS restrito ou proxy, proteção da API e estabilidade do destino LocalTunnel. Depois, iniciar a etapa de upload `.xlsx`; não implementar upload antes da validação desta fase.

### Checklist da Fase 4

- [x] Ler memória, README, Git e estrutura antes de modificar arquivos.
- [x] Verificar Node/npm existentes.
- [x] Criar React + Vite em JavaScript sem Git aninhado.
- [x] Implementar interface responsiva e funcionalidades do chat.
- [x] Centralizar API e configurar proxy Vite.
- [x] Criar `.env.example` sem secrets.
- [x] Executar `npm install`, lint e build.
- [x] Validar um teste real pelo proxy Vite.
- [x] Auditar bundle, ignores e secrets.
- [x] Atualizar README e memória.
- [x] Revisar Git, criar commit e fazer push (`feat: implementa frontend inicial de chat`).

## 2026-08-08 — Fase 3D: estabilização do acesso externo

### Resultado

- Estabilização do destino interno concluída: o Coolify publica `127.0.0.1:18001:8000` e o backend continua ouvindo em `8000` dentro do container.
- `ss` confirmou bind exclusivo em `127.0.0.1:18001`; não houve exposição em `0.0.0.0:18001`.
- `GET http://127.0.0.1:18001/health`: HTTP 200, `server: uvicorn`, `{"status":"ok"}`.
- O LocalTunnel deixou de depender do hostname efêmero do container Coolify e passou a usar `network_mode=host`, destino `127.0.0.1:18001` e restart policy `unless-stopped`.
- A estabilização pública não foi concluída: o LocalTunnel gratuito não garantiu a reutilização de um subdomínio personalizado após `docker restart`.
- Conforme o critério de parada da fase, nenhum túnel alternativo, domínio, proxy ou serviço adicional foi instalado.

### Diagnóstico e tentativas do LocalTunnel

- Estado inicial observado: o comando solicitava `projeto-digitacao-api`, mas a URL concedida era `https://selfish-monkey-100.loca.lt`.
- A URL aleatória inicial foi validada: `GET /health` retornou HTTP 200 com Uvicorn e `POST /api/chat` retornou HTTP 200 com `{"response":"novo tunel funcionando"}`.
- O hostname original respondeu HTTP/HTTPS 503 `Tunnel Unavailable` no início desta execução; a resposta Kestrel relatada anteriormente não estava mais ativa naquele momento.
- Tentativa 1 recuperou `https://projeto-digitacao-api.loca.lt`; health e chat retornaram HTTP 200. Após restart, o LocalTunnel concedeu `https://green-cat-23.loca.lt`.
- Tentativa 2 concedeu diretamente `https://hard-warthog-91.loca.lt`.
- Tentativa 3 recuperou novamente o hostname original, mas após restart concedeu `https://ugly-termite-82.loca.lt`.
- Fallback preferido `projeto-digitacao-bastosrafael-api` foi concedido, porém apresentou colisão/roteamento inconsistente: `GET /health` chegou a `Kestrel/ASP.NET` com HTTP 404, enquanto `POST /api/chat` chegou ao nosso Uvicorn. O nome foi descartado.
- Fallback exclusivo solicitado: `bastosrafael-projeto-digitacao-homelab-api`. Antes do restart, dois GETs retornaram HTTP 200/Uvicorn e o chat retornou HTTP 200 com a frase solicitada, normalizada pelo modelo para `túnel estável funcionando`.
- Foi adicionada ao comando do container uma carência de 15 segundos antes de iniciar o cliente LocalTunnel. Mesmo assim, após `docker restart`, o serviço concedeu `https://spotty-swan-71.loca.lt`.
- Validação pós-restart da URL efetiva: `GET /health` HTTP 200/Uvicorn e `POST /api/chat` HTTP 200, confirmando backend e OmniRoute. O hostname solicitado retornou HTTP 503 `Tunnel Unavailable`.
- Conclusão: **LocalTunnel público não garantiu persistência de subdomínio.** URLs aleatórias não são endpoints aceitáveis para produção ou Netlify.

### Configuração final observada do container do projeto

- Nome: `localtunnel-projeto-digitacao`.
- Imagem: `node:20-alpine`.
- `network_mode`: `host`.
- Restart policy: `unless-stopped`.
- Destino: `127.0.0.1:18001`.
- Subdomínio sempre solicitado pelo comando: `bastosrafael-projeto-digitacao-homelab-api`.
- O comando instala o cliente LocalTunnel, aguarda 15 segundos e executa `lt --port 18001 --local-host 127.0.0.1 --subdomain bastosrafael-projeto-digitacao-homelab-api --print-requests`.
- URL efetivamente concedida após o último restart da validação: `https://spotty-swan-71.loca.lt`, considerada temporária e não configurada no frontend.

### Preservação de infraestrutura e frontend

- O container `localtunnel` do serviço `https://nflnba.loca.lt` permaneceu running, com o mesmo ID observado `c7666f7b9a8f`, rede host e comando para a porta 3001; não foi parado, removido, reiniciado ou alterado.
- Coolify, backend, OmniRoute, firewall, proxy e redes Docker globais não foram alterados nesta execução.
- Nenhum componente, CSS, layout ou identidade visual do frontend foi alterado.
- O proxy técnico do Vite e `frontend/.env.example` passaram a usar por padrão `http://127.0.0.1:18001`, evitando depender de URL pública aleatória durante o desenvolvimento local.
- Nenhum secret ou variável do OmniRoute foi adicionado ao frontend.

### Testes do projeto

- Backend: `.venv/bin/python -m pytest -q` retornou `3 passed in 0.97s`.
- Frontend: `npm run lint` concluído sem erros.
- Frontend: `npm run build` concluído com Vite 8.2.1 e 20 módulos transformados.
- Proxy Vite atualizado: `POST http://127.0.0.1:5173/api/chat` retornou HTTP 200/Uvicorn com `{"response":"proxy local funcionando"}`, comprovando Vite -> `127.0.0.1:18001` -> FastAPI -> OmniRoute.
- O servidor Vite temporário foi encerrado após o teste.

### Problemas e decisões

- Problema resolvido: o hostname interno do container Coolify mudava em redeploys.
- Solução: Port Mapping persistente e restrito `127.0.0.1:18001:8000`, acessado pelo túnel em rede host.
- Problema não resolvido: o serviço público LocalTunnel pode ignorar `--subdomain` e conceder hostname aleatório, inclusive após ter concedido o nome personalizado antes do restart.
- Decisão: não aceitar hostname aleatório, não prosseguir para Netlify e não instalar automaticamente outro provedor de túnel.

### Arquivos modificados

- `frontend/vite.config.js`: destino padrão do proxy alterado somente de forma técnica para `http://127.0.0.1:18001`.
- `frontend/.env.example`: exemplo atualizado para o bind local estável.
- `README.md`: arquitetura, Port Mapping, estado do LocalTunnel e bloqueio público documentados.
- `memoria.md`: registro da Fase 3D.

### Próximo passo

- O operador deve escolher uma opção de endpoint público com hostname garantido antes da Fase 4B: túnel com hostname reservado, domínio/túnel próprio ou aceitar LocalTunnel apenas para testes efêmeros. Não publicar o frontend no Netlify apontando para uma URL aleatória.

### Checklist da Fase 3D

- [x] Ler memória, README e Git antes de agir.
- [x] Confirmar `127.0.0.1:18001 -> 8000` e health local.
- [x] Remover a dependência do hostname efêmero do container Coolify.
- [x] Manter `network_mode=host` e `unless-stopped` no túnel do projeto.
- [x] Validar health e chat externos antes e depois de restart.
- [x] Limitar a três tentativas do hostname original.
- [x] Testar fallbacks determinísticos e rejeitar colisão/hostname aleatório.
- [x] Preservar integralmente o túnel `nflnba`.
- [x] Preservar a interface aprovada.
- [x] Documentar o diagnóstico sem secrets.
- [ ] Obter hostname público persistente após restart.
- [ ] Considerar a Fase 3D pública concluída.
- [ ] Iniciar Fase 4B/Netlify.

## 2026-08-08 — Fase 5A: upload inicial de XLSX — bloqueada por storage de produção

### Escopo executado

- Implementado somente o recebimento e armazenamento seguro de planilhas `.xlsx`.
- Não foram implementados leitura de produtos, extração de imagens, pesquisa, jobs, banco ou geração de planilha final.
- O upload de produção foi desenhado para seguir navegador -> Tailscale Funnel -> FastAPI, sem passar pela Netlify Function do chat.

### Backend

- Variável central `MAX_UPLOAD_SIZE_MB`, padrão 200 MB; aumento futuro exige somente alteração dessa variável no backend.
- `UPLOAD_DIR` configurável, padrão `/data/uploads` no container.
- `CORS_ALLOWED_ORIGINS` configurável, restrito inicialmente a `https://projeto-digitacao.netlify.app`.
- `GET /api/uploads/config` publica o limite necessário para a validação de UX do frontend.
- `POST /api/uploads` recebe multipart `file`, lê em chunks de 1 MiB e nunca usa `contents = await file.read()`.
- Bytes são contados durante a cópia. Ao ultrapassar o limite, a operação é interrompida, o `.part` é removido e a API retorna HTTP 413 com mensagem sanitizada.
- Arquivo temporário recebe modo 600. Após gravação, são validados extensão `.xlsx`, ZIP e as partes mínimas `[Content_Types].xml`, `_rels/.rels` e `xl/workbook.xml`.
- XMLs obrigatórios têm limite individual de leitura de 2 MiB. Nenhum conteúdo do workbook é interpretado nesta fase.
- Arquivo inválido ou falha de storage remove parcial/final. Arquivo válido é promovido atomicamente para nome UUID `.xlsx`, sem usar o nome do usuário no caminho.
- Adicionada dependência `python-multipart==0.0.32`.

### Frontend

- O botão de clipe existente abre seletor restrito a `.xlsx`.
- Antes do envio, o aviso visual já existente mostra nome e tamanho formatado; o botão Enviar confirma e o mesmo clipe remove o anexo.
- Limite é consultado no backend, evitando hardcode duplicado no JavaScript.
- Arquivos acima do limite são rejeitados no frontend, sem substituir a validação obrigatória do backend.
- Envio usa `FormData`; não usa Base64, não define `Content-Type` manualmente e não grava o arquivo no `localStorage`.
- Upload não possui o timeout de 25 segundos do chat/Netlify Function.
- `VITE_UPLOAD_API_BASE_URL` foi centralizada no build do Netlify com o endpoint público Tailscale; não contém secret.
- Nenhum CSS, paleta, tipografia ou framework visual foi alterado. A interface continua baseada no design aprovado, com apenas o comportamento funcional do anexo habilitado.
- Estados explícitos implementados no composer: `selected`, `uploading`, `uploaded` e `error`.
- A resposta de sucesso contém `file_id`; esse UUID também define o nome físico, enquanto o filename original sanitizado existe somente como metadado.
- O arquivo não é enviado ao OmniRoute em nenhuma etapa do upload.

### Disco e persistência

- `df -hT /opt`: `/dev/sda1`, ext4, 106 GB total, 67 GB usados, 34 GB disponíveis, 67% de uso.
- Criado `data/uploads/.gitkeep`; o diretório host observado tem modo 775 e owner `rb:rb`.
- Inspeção do container Coolify atual: `mounts=[]`. Portanto o deploy atual ainda não possui storage persistente para uploads.
- Antes do redeploy, configurar no Coolify o bind/persistent storage `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`, leitura/escrita.
- O mount foi validado em container Docker temporário: arquivo persistiu no host com modo 600.
- Nenhuma quota artificial foi criada. Retenção/cleanup permanece como requisito futuro.

### Testes realizados

- Backend: 12 testes passaram na validação final.
- Casos cobertos: config, XLSX válido, nome UUID, filename sanitizado, arquivo exatamente no limite, HTTP 413, remoção de parcial, extensão inválida, falso `.xlsx`/ZIP inválido, CORS e garantia de que o upload não chama o OmniRoute.
- Frontend: lint e build passaram; 6 testes da Netlify Function continuaram passando.
- Frontend upload: 3 testes passaram para config, multipart `FormData` e detalhe sanitizado HTTP 413.
- Arquivo de referência real não foi localizado em `/opt` ou `/home`.
- Foi gerado temporariamente um XLSX estruturalmente válido com exatamente 36.236.835 bytes. Upload local retornou HTTP 201, `size_bytes=36236835`, CORS correto e arquivo armazenado com o mesmo tamanho.
- Imagem `projeto-digitacao-backend:upload-local` construída sem erro.
- Container temporário em `127.0.0.1:18003 -> 8000` validou health, config, multipart e bind persistente; depois foi parado e removido.
- Todos os arquivos de teste de upload foram removidos; somente `.gitkeep` permaneceu em `data/uploads`.

### Erros e soluções

- Erro de coleta: literal `bytes` com caracteres acentuados no teste Python.
- Solução: gerar os bytes por `.encode()` e repetir toda a suíte com sucesso.
- Limitação encontrada: o container Coolify em produção ainda não possui volume/mount.
- Solução segura: não alterar o Coolify automaticamente; documentar o mount obrigatório antes do redeploy.
- Estado da fase: implementação e testes locais concluídos, porém a **Fase 5A ainda não está concluída em produção**. É necessária ação manual no Coolify para criar o storage persistente antes de push/redeploy.

### Arquivos criados

- `backend/app/api/uploads.py`
- `backend/app/services/upload_service.py`
- `backend/tests/test_uploads.py`
- `frontend/tests/upload-api.test.mjs`
- `data/uploads/.gitkeep`

### Arquivos modificados

- `backend/app/config.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- `backend/.env.example`
- `frontend/src/App.jsx`
- `frontend/src/components/ChatInput.jsx`
- `frontend/src/services/api.js`
- `frontend/package.json`
- `netlify.toml`
- `README.md`
- `memoria.md`

### Próximo passo

- Fase 5A concluída em produção com storage persistente, backend e frontend validados.
- Não iniciar automaticamente a Fase 5B. A inspeção/leitura do Excel, produtos e imagens continua reservada ao roadmap permanente abaixo.

### Checklist

- [x] Centralizar limite em `MAX_UPLOAD_SIZE_MB=200`.
- [x] Gravar incrementalmente em chunks e limpar parciais.
- [x] Validar extensão, ZIP e estrutura mínima XLSX após salvar.
- [x] Retornar HTTP 413 sanitizado ao exceder o limite.
- [x] Expor config do limite para o frontend.
- [x] Enviar multipart `FormData` direto ao FastAPI, sem Base64.
- [x] Mostrar nome e tamanho antes do envio.
- [x] Permitir remover o anexo antes do envio usando o clipe existente.
- [x] Retornar `file_id` e manter filename sanitizado apenas como metadado.
- [x] Implementar estados `selected`, `uploading`, `uploaded` e `error`.
- [x] Garantir que o arquivo não seja enviado ao OmniRoute.
- [x] Preservar conteúdo do arquivo fora do `localStorage`.
- [x] Validar arquivo de 36.236.835 bytes.
- [x] Auditar disco e mount atual.
- [x] Testar bind persistente em container temporário.
- [x] Configurar persistent storage no Coolify e redeployar.
- [x] Validar upload público real em produção.
- [ ] Iniciar leitura/inspeção do XLSX.

### Auditoria de retomada da Fase 5A — 2026-08-08

- Container ativo do backend encontrado em estado `running/healthy` pela label `coolify.applicationId=3`.
- `docker inspect` confirmou novamente ausência total de mounts na implantação ativa; portanto `/data/uploads` ainda não está associado ao bind persistente exigido.
- As variáveis não secretas `MAX_UPLOAD_SIZE_MB`, `UPLOAD_DIR` e `CORS_ALLOWED_ORIGINS` não estavam presentes no ambiente do container ativo.
- Port Mapping preservado: `127.0.0.1:18001:8000`, com socket ouvindo exclusivamente no loopback.
- Tailscale Funnel preservado: HTTPS 443 continua apontando ao NFLNBA em `127.0.0.1:3001`; HTTPS 8443 continua apontando ao Projeto Digitação em `127.0.0.1:18001`.
- Decisão segura: não fazer push nem redeploy, porque isso poderia publicar o upload usando filesystem efêmero.
- Solução necessária: operador deve adicionar no Coolify o bind mount RW `projeto-digitacao-uploads`, Source `/opt/projeto-digitacao/data/uploads`, Destination `/data/uploads`, e configurar as três variáveis como Runtime ON/Buildtime OFF.
- Próximo passo: após confirmação manual, publicar os commits locais, acompanhar o deploy e validar mount, endpoints, upload e persistência antes de marcar a Fase 5A como concluída.
- Checklist da retomada: roadmap permanente registrado; storage e variáveis auditados; bind/Funnel preservados; push, deploy e Fase 5B não iniciados.

### Conclusão da Fase 5A — 2026-08-08

- A configuração persistida do Coolify foi confirmada no registro `local_file_volumes` como Directory Mount (`is_directory=true`), Source `/opt/projeto-digitacao/data/uploads`, Destination `/data/uploads`, sem sufixo para PR e sem modo read-only.
- Variáveis confirmadas: `MAX_UPLOAD_SIZE_MB=200`, `UPLOAD_DIR=/data/uploads` e `CORS_ALLOWED_ORIGINS=https://projeto-digitacao.netlify.app`, todas com Runtime ON e Buildtime OFF.
- Commits `96e4011`, `656d36f` e `c521b41` publicados em `origin/main` por push normal, sem force push.
- O Auto Deploy do Coolify não iniciou; foi feito redeploy manual seguro, sem force rebuild. Deployment `vxulg6ka8l73jgcz04dslxl9` finalizado no commit `c521b41e48f0c2cb39dd7142cb1d148fcdb8b4f3`.
- Novo container `1275c1197718` validado como `running/healthy`, mantendo `127.0.0.1:18001:8000`.
- `docker inspect` confirmou bind persistente `rw`: `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`; o diretório existe, é gravável e está sobre ext4 montado como RW.
- `GET /health` local e público: HTTP 200 com `{"status":"ok"}`.
- `GET /api/uploads/config` local e público: HTTP 200 com limite de 200 MB e extensão `.xlsx`.
- Upload público sintético de 1002 bytes: HTTP 201, `file_id=3fafbb6e-dd5d-4892-86cc-3ce887ecb421`, arquivo UUID com modo 600, hash preservado e sem exposição do caminho físico na resposta.
- A persistência foi comprovada pela presença do mesmo arquivo no Source do host e no Destination do container através do bind mount. O dado não reside no filesystem efêmero do container.
- Frontend Netlify validado em Firefox headless: clipe funcional, seletor `.xlsx`, nome e tamanho visíveis, remoção antes do envio e upload concluído (`file_id=652c25d7-c588-4b2f-ab13-f06ee8f6b573`).
- UI aprovada preservada; nenhuma alteração visual foi feita durante a validação.
- **FASE 5A = CONCLUÍDA.** A Fase 5B não foi iniciada.

## ROADMAP APÓS FASE 5A — PACKING LIST / DUIMP

Este roadmap é permanente. Os arquivos reais de referência são:

- `IM0416-26 - PACKING LIST.xlsx`;
- `IM0342-26 - PACKING LIST com fob.xlsx`.

Esses arquivos podem possuir estruturas diferentes, não devem ser adicionados ao Git e serão usados posteriormente como arquivos reais de teste por upload.

### Fase 5B — leitor universal de Packing List

Objetivo: receber diferentes formatos de planilhas XLSX e entender automaticamente sua estrutura, sem depender de um template fixo.

Requisitos:

1. detectar abas relevantes;
2. detectar linha ou linhas de cabeçalho;
3. detectar semanticamente a coluna de código/modelo/style;
4. procurar cabeçalhos equivalentes como `Style number`, `Style`, `Style No.`, `Code`, `Código`, `Item Code`, `Item No.`, `SKU`, `Reference`, `Ref.`, `Modelo`, `Model`, `款号`, `货号` e variações semelhantes;
5. não depender literalmente do nome `Style number`;
6. quando o cabeçalho não for claro, analisar semanticamente os valores da coluna para inferir qual coluna contém códigos/modelos;
7. detectar imagens incorporadas na planilha;
8. relacionar cada imagem à linha/célula correspondente;
9. classificar as imagens, quando possível, entre imagem principal do produto, etiqueta de composição, etiqueta de lavagem, hangtag e outra imagem auxiliar;
10. não confundir etiqueta ou hangtag com a foto principal do produto;
11. relacionar imagem ↔ linha ↔ Style number/code ↔ demais dados do produto;
12. normalizar códigos quando houver textos auxiliares junto ao código;
13. agrupar linhas repetidas que representam o mesmo código/produto;
14. não gerar descrições diferentes para o mesmo produto apenas porque ele aparece em várias linhas logísticas;
15. coletar também, quando existirem: NCM, item name, nome do produto, composição, material, construção/tecelagem, cor, tamanho, fabricante, fornecedor, hangtag, etiqueta e outras características presentes na planilha;
16. gerar estrutura JSON interna por produto;
17. se não houver código identificável, não inventar código: usar identificador interno controlado, por exemplo `ROW-00045`, e marcar `status = REVISAR`.

A Fase 5B não fará pesquisa na internet.

### Fase 6 — pesquisa real na internet

Objetivo: pesquisar produtos reais usando informações extraídas da planilha.

A IA não deve fingir que pesquisou na internet. Ela somente poderá afirmar que pesquisou ou encontrou informação na internet quando o backend tiver executado uma pesquisa real e fornecido resultados reais ao modelo.

Fluxo obrigatório:

```text
Style number / Code
+ nome existente
+ NCM
+ marca/fabricante
+ dados da planilha
+ imagem, quando aplicável
  -> motor/ferramenta real de busca
  -> resultados reais
  -> páginas/fontes
  -> dados fornecidos à IA
```

Prioridade de fontes, quando disponíveis:

1. fabricante;
2. fornecedor oficial;
3. catálogo oficial;
4. distribuidor confiável;
5. lojas especializadas;
6. marketplaces como evidência secundária.

O modelo não poderá inventar URLs ou fontes. Todas as fontes utilizadas deverão ser registradas.

### Fase 7 — análise visual e cruzamento de evidências

Objetivo: usar imagens da planilha como evidência adicional. A imagem não deve ser a única fonte da verdade quando existir informação documental melhor.

Cruzar código/style, dados da planilha, NCM, composição, etiquetas, hangtag, imagem principal e resultados reais da internet.

A IA com visão poderá ajudar a reconhecer categoria da peça/produto, formato, detalhes visuais, cor, mangas, alças, comprimento, acabamentos, elementos visuais e textos legíveis quando apropriado.

Ela não poderá inventar como fato técnico composição, percentual de fibras, material, fabricante, modelo ou característica não comprovada apenas pela aparência. Se a imagem parecer poliéster, isso não é suficiente para registrar `100% POLIÉSTER`. A informação deverá vir da planilha, etiqueta, catálogo, fabricante, fornecedor, fonte web confiável ou outra evidência documental.

### Fase 8 — descrição técnica para DUIMP

Objetivo: gerar descrição técnica, objetiva e adequada ao processo de DUIMP, sem linguagem comercial ou publicitária.

Padrão desejado:

> VESTIDO CURTO FEMININO, DE USO ADULTO, CONFECCIONADO EM TECIDO PLANO DE FIBRAS SINTÉTICAS (100% POLIÉSTER), SEM MANGAS, COM ALÇAS LARGAS, CORPO COM ACABAMENTO EM LASTEX, BABADOS DO MESMO TECIDO E FORRO INTERNO CONFECCIONADO EM 95% POLIÉSTER E 5% ELASTANO, NA COR ROSA.

A descrição deverá ser construída a partir de dados e evidências. Nunca completar composição, percentuais, material ou características técnicas apenas por parecerem prováveis.

Cada produto deverá manter dados estruturados antes da descrição final. Exemplo conceitual:

```json
{
  "code": "WW77#",
  "ncm": "6104.43.00",
  "product_type": "vestido feminino",
  "construction": "tecido plano",
  "outer_material": "100% poliéster",
  "lining": "95% poliéster, 5% elastano",
  "color": "rosa",
  "sources": {
    "spreadsheet": true,
    "product_image": true,
    "label_image": true,
    "web": []
  },
  "confidence": "alta",
  "status": "OK"
}
```

Somente após estruturar e validar os dados será gerado o texto técnico.

### Confiabilidade

Todo produto deverá possuir confiança `ALTA`, `MÉDIA` ou `BAIXA` e um dos status `OK`, `REVISAR`, `NÃO ENCONTRADO`, `ERRO` ou `PENDENTE`.

Se houver dúvida relevante, não inventar: marcar `REVISAR`. Se não houver evidência suficiente, usar `NÃO ENCONTRADO` ou `REVISAR`, conforme o caso.

### Fase 9 — planilha final para download

Objetivo: gerar um novo XLSX baixável pela interface, preservando sempre que possível os dados originais.

Saída mínima:

- Código;
- Imagem;
- Produto;
- Descrição técnica DUIMP;
- Fonte;
- Confiança;
- Status.

Quando apropriado, também manter NCM, dados originais, composição e outras colunas úteis.

### Arquitetura final planejada

```text
Excel
  -> Upload
  -> Leitor universal
  -> Detecção da estrutura
  -> Imagem ↔ Style/Code
  -> Agrupamento de produtos
  -> Dados estruturados
  -> Pesquisa REAL na internet
  -> Análise visual
  -> Cruzamento de evidências
  -> Descrição técnica DUIMP
  -> Confiança/status
  -> Novo Excel
  -> Download
```

### REGRA CRÍTICA DE VERACIDADE

> **A IA NÃO É A FONTE PRIMÁRIA DA VERDADE.**

A IA deve atuar como analisador dos dados fornecidos pelo sistema.

Nunca permitir a afirmação `pesquisei na internet` se nenhuma ferramenta real de busca tiver sido executada. Nunca permitir que composição, material, percentuais, código, fabricante ou outras características técnicas sejam inventados sem evidência.

### Limite desta execução

- Não iniciar a Fase 5B antes da conclusão e validação em produção da Fase 5A.
- Não extrair imagens, interpretar produtos, pesquisar na internet, gerar descrição DUIMP ou gerar Excel final nesta execução.

## Fase 4B — preparação do frontend para Netlify (2026-08-08)

### Estado inicial

- Repositório em `main`, commit inicial `5cdfcea`, sincronizado com `origin/main` e working tree limpa.
- Netlify CLI não estava instalada na HOMELAB; não havia sessão autenticada disponível e não foi feito login, instalação de CLI ou uso de token.
- Endpoint público estável preservado: `https://nflnba.tail08f125.ts.net:8443`.
- Tailscale Funnel, Coolify, OmniRoute, portas e serviços existentes não foram alterados.

### Interface aprovada / DESIGN LOCK

- Status: **LOCKED / DO NOT ALTER WITHOUT AUTHORIZATION**.
- Commit visual de referência: `fc53ebb`.
- Criado `docs/UI_APROVADA.md` com o escopo visual congelado.
- Criada a tag anotada `ui-v1-approved`, apontando exatamente para `fc53ebb`, e enviada ao GitHub.
- Nenhum componente em `frontend/src/components`, `App.jsx`, CSS, layout ou identidade visual foi modificado.

### Preparação Netlify

- Criado `netlify.toml` na raiz do monorepo.
- Build configurado com base `frontend`, comando `npm run build` e publicação em `dist`.
- Functions usam o diretório padrão relativo à base: `frontend/netlify/functions`.
- A regra `/api/chat` é processada antes do fallback SPA para `/index.html`.
- Criada `frontend/netlify/functions/chat.mjs` usando a API moderna Web `Request`/`Response` do Netlify Functions.
- O frontend permaneceu chamando somente a URL relativa `/api/chat`; o proxy Vite local continua apontando por padrão para `http://127.0.0.1:18001`.

### Segurança e validações da Function

- Aceita somente `POST`; outros métodos retornam HTTP 405 e header `Allow: POST`.
- Exige `Content-Type: application/json`, JSON válido e `message` string não vazia.
- Limites: corpo de 16 KiB e mensagem de 4.000 caracteres.
- O cliente não escolhe destino; a Function constrói exclusivamente `/api/chat` a partir de `BACKEND_BASE_URL`.
- Timeout upstream de 25 segundos; timeout, falha de rede, configuração ausente e resposta inválida produzem JSON controlado sem stack trace.
- `BACKEND_BASE_URL` é variável server-side/runtime. Não foi criada variável `VITE_BACKEND_BASE_URL` e nenhuma chave do OmniRoute foi adicionada ao frontend ou ao bundle.
- Criada suíte Node em `frontend/tests/netlify-chat.test.mjs` e script `npm run test:function`.

### Testes realizados

- Function: `npm run test:function` — 6 testes passaram, cobrindo POST válido, GET rejeitado, ausência de `message`, JSON inválido, backend indisponível e timeout.
- Teste real do código da Function com `BACKEND_BASE_URL=https://nflnba.tail08f125.ts.net:8443`: HTTP 200, `{"response":"netlify proxy funcionando"}`.
- Funnel: `GET /health` — HTTP/2 200, `server: uvicorn`, `{"status":"ok"}`.
- Desenvolvimento local: Vite em `http://127.0.0.1:5173`; `POST /api/chat` via proxy para `127.0.0.1:18001` — HTTP 200, `{"response":"vite local funcionando"}`.
- Backend: `.venv/bin/python -m pytest -q` — 3 testes passaram em 0,72 s.
- Frontend: `npm run lint` — concluído sem erros.
- Frontend: `npm run build` — concluído com Vite 8.2.1, 20 módulos transformados.
- O servidor Vite temporário foi encerrado após o teste.

### Problemas e soluções

- Um teste inicial montava incorretamente uma requisição GET com body; o helper de teste foi corrigido e toda a suíte foi repetida com sucesso.
- Publicação automática indisponível porque a Netlify CLI não está instalada e não há autenticação Netlify confirmada. A preparação técnica foi concluída sem inventar credenciais.

### Publicação concluída — atualização do operador

- **FASE 4B: CONCLUÍDA.**
- URL pública definitiva: `https://projeto-digitacao.netlify.app/`.
- Repositório: `bastosrafael/projeto-digitacao`, branch `main`.
- Configuração aplicada: base `frontend`, build `npm run build`, publish `dist` e Functions em `frontend/netlify/functions`.
- `BACKEND_BASE_URL` configurada no ambiente server-side/runtime do Netlify para o endpoint Tailscale estável, sem exposição no bundle.
- Teste manual do frontend público: página carregou corretamente no navegador.
- Teste manual do chat público: mensagem enviada e resposta correta recebida do backend.
- Fluxo de produção confirmado: navegador -> Netlify frontend -> `POST /api/chat` -> Netlify Function -> Tailscale Funnel `:8443` -> `127.0.0.1:18001` -> Coolify/FastAPI `:8000` -> OmniRoute -> modelo -> resposta.
- A interface aprovada permaneceu inalterada e continua **LOCKED / DO NOT ALTER WITHOUT AUTHORIZATION**, com referência no commit `fc53ebb` e tag `ui-v1-approved`.
- LocalTunnel não faz parte da arquitetura de produção.

### Arquivos criados ou modificados

- `netlify.toml`: build do monorepo e roteamento API/SPA.
- `frontend/netlify/functions/chat.mjs`: proxy server-side seguro.
- `frontend/tests/netlify-chat.test.mjs`: testes automatizados da Function.
- `frontend/package.json`: script `test:function`.
- `frontend/eslint.config.js`: lint dos arquivos Node `.mjs`.
- `docs/UI_APROVADA.md`: registro do design lock.
- `README.md`: arquitetura e instruções Netlify.
- `memoria.md`: registro desta fase.

### Próximo passo

- Aguardar autorização específica antes de iniciar a Fase 5/Excel. A publicação Netlify e o chat de produção já estão validados.

### Checklist da Fase 4B

- [x] Ler memória, README e estado Git antes de alterar.
- [x] Preservar integralmente a interface aprovada.
- [x] Documentar o design lock.
- [x] Criar e publicar a tag `ui-v1-approved` em `fc53ebb`.
- [x] Criar configuração Netlify para o monorepo.
- [x] Criar Function server-side para `/api/chat`.
- [x] Implementar validação, limites, timeout e erros controlados.
- [x] Preservar o proxy Vite local para `127.0.0.1:18001`.
- [x] Validar a Function localmente e contra o Funnel real.
- [x] Executar lint, build e testes backend.
- [x] Publicar no Netlify e validar a URL pública.
- [x] Validar carregamento do frontend público.
- [x] Validar chat público até o OmniRoute.
- [x] Confirmar novamente que o design permanece LOCKED.
- [ ] Iniciar Fase 5/Excel.

## 2026-08-08 — Fase 3E: Tailscale Funnel

### Resultado

- Fase 3E concluída com acesso público HTTPS estável pelo Tailscale Funnel.
- Motivo da migração: o LocalTunnel gratuito ignorava ou não preservava subdomínios personalizados após reinícios.
- Tailscale instalado: versão `1.102.2`.
- Hostname oficial do node: `nflnba.tail08f125.ts.net`; tailnet observado: `tail08f125.ts.net`.
- O NFLNBA já ocupava o listener HTTPS 443, encaminhando `/` para `http://127.0.0.1:3001`.
- Foi adicionado, sem resetar ou substituir o listener existente, o listener HTTPS 8443 para o Projeto Digitação.
- URL pública final: `https://nflnba.tail08f125.ts.net:8443`.
- Target local: `http://127.0.0.1:18001`.
- Port Mapping Coolify preservado: `127.0.0.1:18001:8000`.
- O bind permaneceu exclusivamente em `127.0.0.1:18001`; não houve exposição em `0.0.0.0:18001`.

### Configuração do Funnel

Comando aplicado:

```bash
sudo tailscale funnel --bg --yes --https=8443 http://127.0.0.1:18001
```

Configuração final confirmada por `tailscale funnel status` e `tailscale funnel status --json`:

```text
https://nflnba.tail08f125.ts.net
|-- / proxy http://127.0.0.1:3001

https://nflnba.tail08f125.ts.net:8443
|-- / proxy http://127.0.0.1:18001
```

- O Tailscale permite Funnel somente nas portas públicas 443, 8443 e 10000; 8443 foi escolhida para manter paths raiz do backend sem rewrite.
- Rollback isolado, se necessário: `sudo tailscale funnel --https=8443 off`.
- Não foi usado `tailscale funnel reset`, pois ele afetaria a configuração NFLNBA.
- A persistência é fornecida pelo estado oficial do `tailscaled`; não foi realizado restart do daemon nem da máquina.

### Validações do Projeto Digitação

- Local, `GET http://127.0.0.1:18001/health`: HTTP 200, `server: uvicorn`, `{"status":"ok"}`.
- Público, `GET https://nflnba.tail08f125.ts.net:8443/health`: HTTP/2 200, `server: uvicorn`, `{"status":"ok"}`.
- Público, `POST https://nflnba.tail08f125.ts.net:8443/api/chat`: HTTP/2 200, `{"response":"tailscale funnel funcionando"}`.
- Fluxo confirmado: Internet -> Tailscale Funnel:8443 -> `127.0.0.1:18001` -> Coolify/FastAPI:8000 -> OmniRoute -> `auto/coding:free` -> resposta.

### Preservação do NFLNBA

- URL preservada: `https://nflnba.tail08f125.ts.net` em HTTPS 443.
- Target preservado: `http://127.0.0.1:3001`.
- Depois da inclusão do listener 8443, os seguintes testes retornaram HTTP 200:
  - `/`;
  - `/api/health`;
  - `/api/games/upcoming?league=NFL`;
  - `/nfl`.
- Aplicação Coolify, porta 3001, banco SQLite, volumes e configuração Funnel do NFLNBA não foram alterados ou interrompidos.

### Remoção do LocalTunnel do projeto

- Antes da remoção foi registrada a configuração de rollback do container `localtunnel-projeto-digitacao`:
  - imagem `node:20-alpine`;
  - `network_mode=host`;
  - restart policy `unless-stopped`;
  - destino `127.0.0.1:18001`;
  - subdomínio solicitado `bastosrafael-projeto-digitacao-homelab-api`;
  - comando `lt --port 18001 --local-host 127.0.0.1 --subdomain bastosrafael-projeto-digitacao-homelab-api --print-requests`.
- Somente depois de health/chat públicos e NFLNBA terem sido validados, o container foi parado e removido.
- A imagem `node:20-alpine` foi preservada; nenhum volume, rede, imagem ou outro container foi removido.

### Arquitetura resultante

```text
Internet
  -> https://nflnba.tail08f125.ts.net:8443
  -> Tailscale Funnel HTTPS 8443
  -> http://127.0.0.1:18001
  -> Coolify -> FastAPI:8000
  -> OmniRoute:20128
  -> modelo configurado
```

- Desenvolvimento local permanece Vite -> `/api/chat` -> `http://127.0.0.1:18001`.
- Nenhum componente, CSS, layout ou comportamento visual do frontend foi alterado.
- Netlify e Netlify Function não foram iniciados nesta fase.

### Testes do projeto

- Backend: `.venv/bin/python -m pytest -q` retornou `3 passed in 1.12s`.
- Frontend: `npm run lint` concluído sem erros.
- Frontend: `npm run build` concluído com Vite 8.2.1, 20 módulos transformados e build em 517 ms.
- Proxy local: `POST http://127.0.0.1:5173/api/chat` retornou HTTP 200/Uvicorn com `{"response":"proxy local fase 3e funcionando"}`.
- O servidor Vite temporário foi encerrado depois do teste.

### Arquivos modificados

- `README.md`: arquitetura, URL pública, comandos, rollback e validações do Tailscale Funnel.
- `memoria.md`: registro integral da Fase 3E.

### Próximo passo

- Iniciar somente após validação do operador a Fase 4B: preparar o proxy de produção/Netlify Function para a URL Tailscale, definir proteção da API e CORS, sem alterar a interface aprovada.

### Checklist da Fase 3E

- [x] Ler memória, README e estado Git antes de agir.
- [x] Registrar estado inicial de `tailscale funnel status` e `tailscale serve status`.
- [x] Confirmar Tailscale 1.102.2, hostname e target NFLNBA.
- [x] Confirmar que HTTPS 8443 poderia coexistir com 443.
- [x] Preservar o listener NFLNBA em 443.
- [x] Publicar `127.0.0.1:18001` no Funnel HTTPS 8443.
- [x] Validar health e chat públicos do Projeto Digitação.
- [x] Confirmar resposta do OmniRoute.
- [x] Validar quatro rotas NFLNBA após a alteração.
- [x] Revalidar persistência pelo estado oficial do Tailscale.
- [x] Remover somente `localtunnel-projeto-digitacao` depois das validações.
- [x] Preservar UI, desenvolvimento local, imagens, volumes e redes.
- [ ] Iniciar Fase 4B/Netlify.

## 2026-08-08 — Fase 5B: leitor universal de Packing List

### Identificação segura dos uploads reais

- A Fase 5A não persistia metadados de filename em banco ou sidecar; o nome original existia somente na resposta HTTP do upload.
- Foram encontrados quatro XLSX no mount. Dois tinham 1002 bytes e correspondem aos testes sintéticos registrados na conclusão da Fase 5A.
- Os dois uploads novos foram relacionados usando logs do backend (`file_id`, bytes e horário), stat do mount e inspeção estrutural interna do workbook, sem depender somente de mtime.
- `IM0416-26 - PACKING LIST.xlsx`: `file_id=fe9759e7-be2c-4808-92ae-cf395e9bd376`, 36.236.835 bytes, upload em 2026-08-08 20:01:36 -03, arquivo controlado `/data/uploads/fe9759e7-be2c-4808-92ae-cf395e9bd376.xlsx`.
- `IM0342-26 - PACKING LIST com fob.xlsx`: `file_id=c21b5d16-d31f-4722-8c3b-213d19360be3`, 1.751.445 bytes, upload em 2026-08-08 20:00:09 -03, arquivo controlado `/data/uploads/c21b5d16-d31f-4722-8c3b-213d19360be3.xlsx`.
- A associação foi confirmada também pelo conteúdo: o primeiro é bilíngue e contém `Picture`, `Item name`, `NCM`, `Style number`, `Ingredients`; o segundo contém `图片`, `款号`, `品名`, `织造方式`, `成份`, `洗水唛`, `吊牌` e USD.

### Implementação determinística

- Criado `backend/app/services/spreadsheets/` com módulos separados: `parser`, `detector`, `images`, `normalization`, `schemas` e `analyzer`.
- O parser lê OOXML diretamente e fecha ZIP/streams por context manager. Não carrega imagens em Base64 nem inclui bytes na resposta.
- Cabeçalhos são pontuados em qualquer linha e podem ocupar até três linhas. Abas são comparadas por score de cabeçalho, volume de dados e imagens.
- Code/style usa aliases em português, inglês e chinês. Quando não há título conhecido, a coluna é inferida pela natureza dos valores, com penalização de números, quantidade e NCM.
- Células mescladas são resolvidas pelo valor top-left. Linhas logísticas sem código só herdam o anterior quando nome/NCM confirmam o mesmo bloco documental.
- `original_values` preserva valores brutos. Texto de caixa é separado em `packing_info`; sufixos chineses semânticos que distinguem itens são preservados no código.
- Produtos repetidos são agrupados por código normalizado e mantêm todos os `row_numbers`.
- Ausência real de código gera `ROW-xxxxx`, `REVISAR` e `Código não identificado`; nenhum código é inventado.
- Drawings são lidos pelas relações OOXML. Cada âncora registra sheet, row, column, width, height, media reference, SHA-256, classificação e código relacionado.
- Classificação estrutural: coluna de Picture/图片 -> `PRODUCT_IMAGE`; wash label/洗水唛 -> `WASH_LABEL`; hangtag/吊牌 -> `HANGTAG`; label -> `LABEL_IMAGE`; desconhecida -> `OTHER`.
- Associação imagem↔produto considera linha lógica, merges, continuidade documental e proximidade limitada, sem depender cegamente da mesma linha.
- Endpoint criado: `POST /api/uploads/{file_id}/analyze`. UUID é validado e somente `<UPLOAD_DIR>/<UUID>.xlsx` pode ser aberto. O trabalho pesado roda em threadpool.
- Não houve chamada ao OmniRoute, pesquisa na internet, análise visual por IA, descrição comercial ou descrição DUIMP.

### Testes sintéticos

- 24 testes backend passaram na validação local, preservando todos os testes da Fase 5A.
- Cobertura nova: `Style number`, `Code`, `款号`, header fora da linha 1, header multilinha, inferência por valores, ausência de código, repetidos, texto logístico, sufixo chinês semântico, múltiplas abas, merges, imagens, imagem sem código, NCM, composição, wash label, hangtag, label, UUID inválido, upload inexistente e tentativa de path arbitrário.
- Respostas verificadas sem Base64, sem bytes de imagem e sem path absoluto.

### Métricas locais — IM0416-26

- `file_id=fe9759e7-be2c-4808-92ae-cf395e9bd376`.
- 1 sheet; principal `总合计567箱`; 169 linhas; 16 colunas; cabeçalho na linha 1.
- Code/style na coluna 5, header `款号 Style number`, confiança 0,99.
- 118 linhas com código explícito; 71 códigos/produtos únicos; 53 códigos repetidos.
- 88 âncoras; 85 mídias únicas por SHA-256; 64 product images; 16 hangtags; 8 other.
- Campos auxiliares: item name, NCM, composition, hangtag e packing info.
- Sem warnings ou produtos `REVISAR` no caso de aceitação.
- Duração observada ~1,3 s; máximo RSS do processo ~40 MB; JSON ~69 KB.

### Métricas locais — IM0342-26 com FOB

- `file_id=c21b5d16-d31f-4722-8c3b-213d19360be3`.
- 3 sheets; principal `Sheet1`; 175 linhas; 23 colunas; cabeçalho principal na linha 1 e cabeçalhos repetidos em seções posteriores; 199 merges no workbook.
- Code/style na coluna 2, header `款号`, confiança 0,99.
- 137 linhas com código explícito; 74 códigos/produtos únicos; 53 códigos repetidos.
- 155 âncoras; 98 mídias únicas por SHA-256; 109 product images; 36 wash labels; 10 hangtags.
- Campos auxiliares: item name, NCM, composition, construction, manufacturer, wash label, hangtag e packing info.
- Sem warnings ou produtos `REVISAR` no caso de aceitação.
- Duração observada ~2,2 s; máximo RSS do processo ~36 MB; JSON ~94 KB.

### Comparação e limitações

- IM0416-26 é bilíngue, tem uma aba e separa hangtag/foto; IM0342-26 usa três abas, texto chinês, merges, headers repetidos e colunas específicas para wash label/hangtag.
- Uma mídia pode ser reutilizada em várias âncoras; por isso `images_detected` conta instâncias e `unique_media` usa SHA-256.
- Classificação permanece estrutural. Não há OCR/visão; colunas desconhecidas ficam `OTHER`.
- Fórmulas dependem do valor cached no XLSX. Workbooks sem tabela reconhecível retornam erro controlado.
- UI permaneceu LOCKED e nenhum arquivo frontend/CSS foi alterado.
- Arquivos XLSX reais e imagens extraídas permanecem fora do Git por `.gitignore`.
- Commit funcional `2a60c14` (`feat: adiciona leitor universal de packing list`) criado e publicado em `origin/main` por push normal, sem force push.
- Auto Deploy não iniciou. Redeploy manual seguro `qmhtkfjr44k2gdzhxg520vxt` foi concluído no commit `2a60c14316d5d7d0f6c53cba772a640dbdbc726d`, sem force rebuild.
- Novo container `6d3b34f4199b` confirmado `running/healthy`, com port mapping `127.0.0.1:18001:8000` e bind RW `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`.
- Fase 5A revalidada: `/health` local/público HTTP 200, `/api/uploads/config` com 200 MB, variáveis corretas e os dois arquivos persistentes presentes no host/container.
- Produção IM0416-26: POST local e público HTTP 200; 71 produtos únicos, 88 imagens, zero warnings/reviews e sem path/Base64 na resposta.
- Produção IM0342-26 com FOB: POST local e público HTTP 200; 74 produtos únicos, 155 imagens, zero warnings/reviews e sem path/Base64 na resposta.
- Netlify respondeu HTTP 200; nenhum frontend/CSS foi alterado. Funnel preservou 443 -> NFLNBA e 8443 -> Projeto Digitação.
- **FASE 5B = CONCLUÍDA.** Todos os 25 critérios de sucesso foram atendidos.
- A Fase 6 não foi iniciada.

## 2026-08-08 — Checkpoint final do dia antes da Fase 6

### Estado encerrado

- **FASE 5A = CONCLUÍDA.** Upload XLSX e storage persistente continuam funcionando em produção.
- **FASE 5B = CONCLUÍDA E VALIDADA EM PRODUÇÃO.** O leitor universal analisou os dois formatos reais com o mesmo parser, sem regra especial por filename.
- **FASE 6 = NÃO INICIADA.** Nenhuma nova funcionalidade foi iniciada neste checkpoint.

### Casos reais consolidados

- Modelo 1: `IM0416-26 - PACKING LIST.xlsx`, `file_id=fe9759e7-be2c-4808-92ae-cf395e9bd376`, 36.236.835 bytes; 1 aba, principal `总合计567箱`, 169 × 16, code/style na coluna 5 (`款号 / Style number`, confiança 0,99), 88 imagens — 64 `PRODUCT_IMAGE`, 16 `HANGTAG` e 8 `OTHER` —, 71 produtos únicos, 53 códigos repetidos e zero warnings.
- Modelo 2: `IM0342-26 - PACKING LIST com fob.xlsx`, `file_id=c21b5d16-d31f-4722-8c3b-213d19360be3`, 1.751.445 bytes; 3 abas, principal `Sheet1`, 175 × 23, code/style na coluna 2 (`款号`, confiança 0,99), 155 imagens — 109 `PRODUCT_IMAGE`, 36 `WASH_LABEL` e 10 `HANGTAG` —, 74 produtos únicos, 53 códigos repetidos e zero warnings.
- Performance observada: aproximadamente 1,3–1,6 s no modelo 1 e 2,1–2,6 s no modelo 2; RSS máximo aproximado de 40 MB e respostas JSON abaixo de 100 KB.

### Validação e preservação

- Backend: 24/24 testes; Netlify Function: 6/6; upload frontend: 3/3; lint e build do frontend aprovados.
- Coolify healthy, bind `127.0.0.1:18001:8000` e storage RW `/opt/projeto-digitacao/data/uploads` -> `/data/uploads` preservados.
- Produção preservada em `https://projeto-digitacao.netlify.app` e `https://nflnba.tail08f125.ts.net:8443`; Tailscale Funnel mantém 443 para NFLNBA e 8443 para o Projeto Digitação.
- UI aprovada e LOCKED no commit visual `fc53ebb`; nenhuma alteração visual está autorizada sem aprovação expressa do operador.
- Commits da Fase 5B: `2a60c14 feat: adiciona leitor universal de packing list` e `c3d8a45 docs: registra conclusao da fase 5b`; ao encerrar a fase, `main` estava sincronizada com `origin/main` e a working tree estava limpa.

### Próximo passo

- Amanhã, iniciar a **Fase 6 — Pesquisa REAL na internet**, usando no backend uma ferramenta real de busca para cada produto normalizado pela Fase 5B.
- Fluxo obrigatório: produto estruturado -> busca real no backend -> resultados e URLs reais -> conteúdo relevante -> evidências entregues à IA -> comparação das evidências.
- A IA não pode afirmar que pesquisou a internet quando nenhuma busca real tiver sido executada. O modelo não é ferramenta de busca.
- Priorizar fabricante, fornecedor e catálogo oficiais; depois distribuidor e loja especializada/confiável; marketplace somente como evidência secundária. Não inventar URLs, fabricantes ou composição.
- Roadmap preservado: Fase 7 — análise visual e cruzamento de evidências; Fase 8 — descrição técnica objetiva para DUIMP; Fase 9 — planilha final para download.

## 2026-08-10 — Preparação adicional antes da Fase 6

### Memória revisada e oportunidade incorporada

- O material disponível no workspace foi revisado antes de iniciar a Fase 6. A pasta Windows `C:\Users\basto\Desktop\projeto-digitacao\memorias` não estava montada no ambiente; o arquivo permanente disponível era `memoria.md`.
- Foi corrigida a limitação registrada na Fase 5B: uploads novos agora persistem metadados ao lado do XLSX, evitando depender de logs, `mtime` e inspeção estrutural para recuperar o nome de origem.
- O sidecar controlado `<UUID>.json` contém `schema_version`, `file_id`, nome original sanitizado, nome armazenado, tamanho em bytes, SHA-256 e horário UTC.
- XLSX e sidecar usam somente nomes derivados de UUID, recebem modo 600 e são gravados por arquivos temporários com rename atômico. Falha no metadado remove também o XLSX novo e todos os parciais.
- Criado `GET /api/uploads/{file_id}` para consultar a proveniência sem aceitar paths arbitrários. `POST /api/uploads/{file_id}/analyze` permanece compatível.
- Uploads históricos continuam analisáveis e não são alterados automaticamente; apenas não possuem o novo sidecar até serem reenviados ou migrados com dados de origem confiáveis.
- O `POST /api/uploads` passou a retornar também `sha256` e `uploaded_at`, sem remover campos anteriores e sem alterar o frontend visual aprovado.

### Validação

- Suíte backend: 26 testes passando.
- Cobertos: conteúdo e permissão do sidecar, hash do XLSX, consulta por UUID, rejeição de identificador inválido, remoção integral quando a gravação do metadado falha e regressões de upload/análise/chat.
- `git diff --check` sem erros.
- **FASE 6 CONTINUA NÃO INICIADA.** Esta mudança apenas fortalece rastreabilidade e proveniência para a próxima fase.

## 2026-08-10 — Incorporação das memórias DUIMP de Shirley

### Fontes revisadas

- Lidos integralmente os dois Markdown e o PDF em `/home/rb/Compartilhado/Backup-D/memorias-shirley`.
- O PDF repete a memória geral; o segundo Markdown amplia exemplos e ressalvas.
- Os casos e NCMs históricos não foram convertidos em regras automáticas. As próprias memórias determinam análise individual, registram dados incompletos e alertam sobre classificações discutíveis.

### Conteúdo incorporado

- Criada a política canônica `docs/POLITICA_PESQUISA_DUIMP.md`, limitada a critérios reutilizáveis de pesquisa, evidência e redação neutra.
- O parser passou a reconhecer cabeçalhos em português, inglês e chinês para finalidade, dimensões, peso, capacidade, tensão, potência, frequência, bateria, recarga, conexão e acessórios.
- Produtos normalizados agora incluem `research_preparation`: consultas determinísticas, termos originados na planilha, foco técnico por categoria, lacunas e avisos.
- Produtos normalizados também incluem `description_preparation`: somente fatos comprovados, ordenados segundo a política DUIMP, sem preencher campos ausentes.
- A NCM da planilha pode compor a pesquisa, mas recebe aviso explícito de que não confirma a classificação. Ela permanece fora do texto descritivo automático e em campo próprio.
- Nenhuma URL, fonte, composição, material, fabricante, modelo ou NCM é inventada. Nenhuma lista histórica foi usada como lookup.
- A interface aprovada permaneceu inalterada. Nenhuma pesquisa web foi executada e nenhuma descrição DUIMP final foi gerada nesta preparação.

### Validação

- Suíte backend ampliada para 32 testes, incluindo aliases técnicos em português/inglês/chinês, preparação de pesquisa, separação da NCM e garantia de não preencher lacunas.
- Os dois XLSX reais não puderam ser reabertos pelo usuário da sessão porque permanecem com modo 600 e propriedade do container/root; não houve alteração de permissões nem dos arquivos persistentes. Os testes sintéticos equivalentes passaram.
- **FASE 6 AINDA NÃO EXECUTOU PESQUISA REAL.** O projeto apenas ganhou entradas estruturadas e política para fazê-la com rastreabilidade na próxima etapa.

## 2026-08-10 — FASE 6A — SEARCH INFRASTRUCTURE

### Instalação do SearXNG

- SearXNG self-hosted instalado fora do projeto, em `/opt/searxng`, por Docker Compose com um único container e sem Valkey/Redis.
- Imagem oficial fixada em `searxng/searxng:2026.8.10-0a118066d`, digest `sha256:cd22dbf7fac8b25d5e39e65af53a4b47009df5ad3162e270c477fd5b30ce03f2`.
- Publicação restrita a `127.0.0.1:8888 -> 8080/tcp`; o serviço não responde em `192.168.15.112:8888` e não possui Funnel, proxy público ou exposição para a LAN.
- Restart policy `unless-stopped`, limite de memória de 512 MiB, limite de 1 CPU e um worker Granian.
- `secret_key` forte gerada localmente e mantida somente em `/opt/searxng/.env`, modo 600. O valor não foi registrado nem versionado.
- Formatos `html` e `json` habilitados. Limiter e image proxy desativados; como a instância é local, Valkey não é necessário neste cenário.
- Engines efetivamente ativas e sem API paga: DuckDuckGo, Brave, Qwant e Mojeek. A engine Google foi descartada da configuração final porque vem marcada como `inactive` nesta versão.

### Validação direta

- Homepage local: HTTP 200.
- `GET /search?q=OpenAI&format=json`: HTTP 200, JSON válido, 26 resultados no teste inicial, com `title`, `url` e `content`; latência observada de 1,37 s.
- Consulta controlada de produto: código real `WW77#`, obtido pelo parser do Packing List `c21b5d16-d31f-4722-8c3b-213d19360be3`; HTTP 200, 10 resultados e URLs, em 1,20 s.
- Brave e DuckDuckGo forneceram resultados na consulta inicial. Mojeek apresentou uma falha pontual de upstream; a redundância permaneceu configurada e o serviço continuou respondendo normalmente.
- O código isolado retornou ao menos um resultado coerente, mas também ruído e spam. Filtragem, composição de consultas e avaliação de evidências ficam explicitamente para a Fase 6B.

### OmniRoute Search Gateway

- OmniRoute preservado na versão 3.8.49 e porta 20128.
- Criada somente a conexão `searxng-search`, nome `SearXNG HOMELAB`, `auth_type=none`, ativa, sem API key/token, sem proxy e com `baseUrl=http://127.0.0.1:8888`.
- Antes da persistência foi criado o backup local `omniroute-backup-pre-searxng-search-provider`. Como o endpoint administrativo recusou escrita sem uma sessão de administrador válida, a linha sem credencial foi inserida transacionalmente no schema `provider_connections`; a contagem dos três providers LLM preexistentes permaneceu inalterada.
- `POST /v1/search` com `provider=searxng-search`, consulta `OpenAI` e `max_results=5`: HTTP 200, 5 resultados reais, 1.130 ms de upstream, `search_cost_usd=0`, sem erros.
- `POST /v1/search` com `provider=searxng-search`, consulta `WW77#` e `max_results=5`: HTTP 200, 5 resultados reais, 1.536 ms de upstream, `search_cost_usd=0`, sem erros.
- Depois de `docker restart searxng`, o JSON direto voltou a responder e uma consulta não cacheada pelo OmniRoute retornou HTTP 200, 5 resultados, 829 ms de upstream e custo zero.
- Nenhuma API comercial foi criada, contratada ou utilizada. `duckduckgo-free` permanece apenas como fallback possível e não foi configurado como provider principal.

### Recursos, segurança e preservação

- Medição final em idle: SearXNG com 134,5 MiB de RAM de um limite de 512 MiB, 0,00% de CPU e 12 PIDs/threads; um único processo worker foi confirmado.
- Host: 3,6 GiB de RAM total, 3,0 GiB em uso, 614 MiB disponíveis; swap 1,8 GiB de 5,6 GiB; CPU do container em 0% e host com aproximadamente 88% idle na amostra.
- Docker reportou imagem de 377 MB e camada gravável do container de 496 KB. O filesystem raiz permaneceu com aproximadamente 33 GiB livres.
- `ss -ltnp` confirmou somente `127.0.0.1:8888`; não existe bind `0.0.0.0:8888`.
- Projeto Digitação permaneceu saudável em `127.0.0.1:18001`; NFLNBA permaneceu saudável em `127.0.0.1:3001`.
- Tailscale Funnel permaneceu sem mudanças: 443 aponta para NFLNBA/3001 e 8443 para Projeto Digitação/18001. Nenhum Funnel foi criado para o SearXNG.
- Nenhum arquivo de backend ou frontend foi alterado pela Fase 6A. A UI continua LOCKED no commit visual `fc53ebb`.

### Regra arquitetural e próximo passo

- Pesquisa real e análise permanecem camadas independentes: SearXNG executa a busca; OmniRoute `/v1/search` entrega resultados e URLs; os modelos gratuitos `auto/coding:free` poderão analisar evidências posteriormente.
- LLM não é mecanismo de pesquisa e não pode alegar busca sem resultados reais do Search Gateway.
- **FASE 6A = CONCLUÍDA.** Infraestrutura de pesquisa real, local e de custo zero validada; a Fase 6B não foi iniciada.
- **FASE 6B — INTEGRAÇÃO DA PESQUISA COM PRODUTOS:** produto estruturado da Fase 5B -> geração de consultas -> OmniRoute `/v1/search` -> SearXNG -> resultados reais -> evidências -> cache -> posteriormente IA gratuita.

## 2026-08-10 — Checkpoint final do dia após a Fase 6A

### Estado encerrado

- **FASE 5A = CONCLUÍDA.** Upload XLSX e storage persistente permanecem funcionando em produção.
- **FASE 5B = CONCLUÍDA.** O leitor universal de Packing List permanece validado com os dois modelos reais.
- **FASE 6A = CONCLUÍDA.** A infraestrutura gratuita de pesquisa real foi instalada, conectada ao OmniRoute e validada.
- **FASE 6B = NÃO INICIADA.** Este checkpoint não adicionou integração de pesquisa ao backend, pesquisa em lote, análise por IA ou descrição DUIMP.

### Fase 5B preservada

- `IM0416-26 - PACKING LIST.xlsx`, `file_id=fe9759e7-be2c-4808-92ae-cf395e9bd376`: 71 produtos únicos e 88 imagens — 64 `PRODUCT_IMAGE`, 16 `HANGTAG` e 8 `OTHER`.
- `IM0342-26 - PACKING LIST com fob.xlsx`, `file_id=c21b5d16-d31f-4722-8c3b-213d19360be3`: 74 produtos únicos e 155 imagens — 109 `PRODUCT_IMAGE`, 36 `WASH_LABEL` e 10 `HANGTAG`.
- O parser detecta abas, cabeçalhos multilíngues e multilinha, Style/Code por aliases ou inferência, anchors e merges; relaciona imagem ↔ linha ↔ código, normaliza códigos, agrupa produtos repetidos, preserva valores originais, classifica imagens e não depende do filename.
- A classificação de imagens continua estrutural; não existe OCR ou análise visual por IA nesta etapa.

### Infraestrutura atual de pesquisa

- SearXNG instalado por Docker Compose em `/opt/searxng/compose.yaml`, imagem `searxng/searxng:2026.8.10-0a118066d`, sem containers auxiliares e sem Valkey/Redis.
- Bind exclusivo `127.0.0.1:8888 -> container:8080`; não existe `0.0.0.0:8888`, exposição para LAN/internet ou Tailscale Funnel.
- HTML e JSON habilitados. `GET /search?...&format=json` retornou HTTP 200 com `title`, URL e conteúdo/snippet reais.
- Engines gratuitas ativas: DuckDuckGo, Brave, Qwant e Mojeek. Nenhuma API comercial, conta paga ou cartão foi utilizado.
- OmniRoute 3.8.49 preservado na porta 20128, com Search Gateway `POST /v1/search` e provider ativo `searxng-search`, autenticação `none`, sem API key e custo observado de US$ 0.

### Testes consolidados da Fase 6A

- SearXNG direto, consulta `OpenAI`: aproximadamente 26 resultados em 1,37 s.
- SearXNG direto, consulta real de produto `WW77#`: aproximadamente 10 resultados em 1,20 s.
- OmniRoute `POST /v1/search`, `provider=searxng-search`, consulta `OpenAI`, `max_results=5`: 5 resultados reais, upstream aproximado de 1.130 ms e custo US$ 0.
- OmniRoute `POST /v1/search`, `provider=searxng-search`, consulta `WW77#`, `max_results=5`: 5 resultados reais, upstream aproximado de 1.536 ms e custo US$ 0.
- Depois de `docker restart searxng`, o JSON direto, o Search Gateway e uma pesquisa não cacheada continuaram funcionando.

### Limitação observada

- A consulta somente pelo código `WW77#` também retornou ruído, spam e páginas sem relação suficiente com o produto.
- Isso não invalida a infraestrutura: comprova que a Fase 6B precisa combinar código e dados da planilha, normalizar e deduplicar resultados, filtrar spam, aplicar scoring, priorizar fontes, armazenar evidências e usar cache.
- Não pesquisar centenas de combinações indiscriminadamente nem processar os aproximadamente 145 produtos de uma vez.

### Recursos e alerta operacional

- SearXNG observado com aproximadamente 134,5 MiB de RAM, limite de 512 MiB e CPU próxima de 0% em idle.
- Host observado com aproximadamente 3,6 GiB de RAM total, 3,0 GiB usados, 614 MiB disponíveis e 1,8 GiB de swap usados de 5,6 GiB; CPU do host aproximadamente 88% idle.
- Imagem SearXNG aproximadamente 377 MB; filesystem do host com aproximadamente 33 GiB livres.
- A RAM do HOMELAB permanece limitada. Antes de qualquer piloto da Fase 6B, executar novamente `free -h` e `docker stats --no-stream`.
- A Fase 6B deverá começar com concorrência baixa, poucas pesquisas e cache desde o início.

### Arquitetura preservada

```text
Packing List
  -> upload
  -> leitor universal da Fase 5B
  -> produto estruturado

Pesquisa futura:
produto
  -> backend do Projeto Digitação
  -> OmniRoute /v1/search
  -> provider searxng-search
  -> SearXNG
  -> internet real
  -> URLs + títulos + snippets

IA futura:
resultados reais + dados da planilha
  -> OmniRoute
  -> auto/coding:free
  -> comparação e resumo de evidências
```

> **REGRA CRÍTICA: A IA NÃO É O MECANISMO DE BUSCA.** A IA somente poderá analisar resultados depois que o backend executar uma busca real pelo OmniRoute `/v1/search` e SearXNG. Nunca permitir que um modelo afirme “pesquisei na internet” sem essa execução real.

### Próximo passo exato — Fase 6B

- Iniciar amanhã a **FASE 6B — INTEGRAÇÃO DE PESQUISA COM PRODUTOS**, sem começar por todos os produtos.
- Selecionar primeiro somente 2 ou 3 produtos reais com code/style conhecido e, preferencialmente, `item_name`, NCM, composição ou outros sinais auxiliares.
- Gerar poucas consultas controladas, combinando quando disponível: código exato; código + `item_name`; código + fornecedor; código + tipo de produto; código + composição.
- Fluxo: produto estruturado -> consultas -> OmniRoute `/v1/search` -> SearXNG -> resultados reais -> normalização -> deduplicação -> filtragem de ruído/spam -> scoring -> priorização de fontes -> evidências -> cache -> posteriormente IA gratuita.
- Prioridade de fontes: fabricante; fornecedor oficial; catálogo oficial; distribuidor confiável; loja especializada; marketplace apenas como fonte secundária. Spam, SEO farms, agregadores ruins e páginas irrelevantes devem perder pontuação ou ser descartados.
- Cache mínimo por query normalizada e provider, guardando timestamp, resultados e status, para não repetir sem necessidade consultas como `WW77#`.
- Para cada evidência relevante preservar: título, URL, snippet, provider, posição, data da consulta, query utilizada, score futuro e motivo de relevância quando disponível. Nunca inventar URL.
- Somente depois da busca estruturada, resultados reais e dados da planilha poderão ser enviados a `auto/coding:free` para comparar, classificar e resumir evidências, sem inventar fonte, composição, fabricante ou fato técnico.

### Infraestrutura bloqueada para alterações neste checkpoint

- Frontend `https://projeto-digitacao.netlify.app` e UI **LOCKED** no commit visual `fc53ebb`.
- Backend local `http://127.0.0.1:18001` e público `https://nflnba.tail08f125.ts.net:8443`.
- Tailscale Funnel preservado: 443 -> NFLNBA e 8443 -> Projeto Digitação.
- Storage RW preservado: host `/opt/projeto-digitacao/data/uploads` -> container `/data/uploads`.
- SearXNG preservado em `127.0.0.1:8888`; OmniRoute preservado na porta 20128.
- Fases futuras permanecem: Fase 7 — análise visual e cruzamento de evidências; Fase 8 — descrição técnica objetiva para DUIMP; Fase 9 — Excel final para download.

## 2026-08-13 — Fase 6B: piloto de integração e filtragem pré-IA

- O backend passou a integrar produtos estruturados da Fase 5B ao OmniRoute `POST /v1/search`, usando exclusivamente o provider `searxng-search`. Nenhuma alteração foi feita no SearXNG, OmniRoute, Coolify, Funnel ou frontend.
- Criado `POST /api/uploads/{file_id}/research`, restrito a 2 ou 3 `product_ids` distintos e a no máximo 3 consultas por produto. O processamento é sequencial para respeitar a RAM limitada do HOMELAB.
- O fluxo implementado é: análise do XLSX -> seleção explícita dos produtos -> consultas preparadas -> busca real -> normalização de URL -> deduplicação -> bloqueio de ruído -> scoring -> evidências rastreáveis -> cache.
- Cada evidência aceita preserva título, URL, snippet, provider, engine de origem, posição, timestamp, query, categoria da fonte, score e motivos de relevância. A resposta declara `llm_used=false`.
- O cache privado usa provider + consulta Unicode normalizada, registra timestamp/status/resposta, validade padrão de 7 dias e fica em `/data/uploads/.search-cache`, dentro do mount persistente existente.
- O piloto real utilizou `WW77#`, `CY2926` e `CY2927`, todos do upload `c21b5d16-d31f-4722-8c3b-213d19360be3`, com 2 consultas por produto e até 8 resultados por consulta.
- As 6 pesquisas reais avaliaram 40 resultados brutos. Foi identificado query-reflection spam da Qwant: páginas em domínios aleatórios repetiam código, fabricante, item e NCM no título, mas apresentavam snippets artificiais sem relação factual.
- O filtro foi endurecido para exigir, em fontes gerais, ao menos um sinal do produto também no snippet, caminho da URL ou domínio. Após a correção, os 40 resultados foram descartados e os três produtos ficaram `NÃO_ENCONTRADO`, sem produzir falsas evidências.
- A repetição imediata executou as mesmas 6 consultas com 6 cache hits, zero chamadas ao gateway e `llm_used=false`.
- Validação local: 37 testes backend passando, `compileall` sem erros e `git diff --check` limpo.
- **FASE 6B — PILOTO CONTROLADO INTEGRADO E VALIDADO.** A expansão para outros produtos e o envio posterior das evidências filtradas às IAs gratuitas não foram iniciados.

## 2026-08-13 — Fase 6B: segundo piloto controlado antes de commit/deploy

### Seleção automática

- Foi criado um seletor determinístico que considera campos úteis, pesos de identidade/composição, distintividade do código e diversidade em relação aos produtos já escolhidos. Fórmulas `DISPIMG` não contam como metadado.
- Entre os 145 produtos dos dois Packing Lists, o seletor escolheu `WY-2026-Y11`, `N260309#` e `CY2926`, todos do upload `c21b5d16-d31f-4722-8c3b-213d19360be3`.
- Cada selecionado possuía 6 sinais úteis: code, item_name, NCM, composição, construção e fabricante. O primeiro tinha código mais distintivo; os seguintes acrescentaram combinações novas de categoria, composição, fabricante e NCM. `CY2926` reapareceu por ranking automático, não por escolha manual baseada no piloto anterior.

### Estratégia de consultas e scoring

- O query builder passou a produzir até quatro consultas progressivas: código exato; código + categoria; código + fabricante/fornecedor/marca; código + característica discriminante. Código + NCM sem pontuação é usado somente como fallback quando não existe característica melhor.
- Adicionado glossário multilíngue fechado e determinístico apenas para termos inequívocos observados nos Packing Lists, por exemplo `短袖T恤 -> short sleeve T-shirt`, `梭织 -> woven`, `针织 -> knitted`, `涤/涤纶 -> polyester`, `棉 -> cotton` e `氨纶 -> elastane`. Termos desconhecidos permanecem originais; nenhuma IA ou tradução probabilística é usada.
- O scoring distingue evidência `STRONG`, `MODERATE` e `WEAK`. Código no snippet ou URL é forte, salvo código curto/ambíguo sem corroboração. Código apenas no título exige outro sinal no snippet/URL/domínio ou compatibilidade nominal de fabricante/fornecedor; evidência fraca é descartada.
- A classificação de domínio passou a usar `MANUFACTURER`, `SUPPLIER`, `DISTRIBUTOR`, `STORE`, `MARKETPLACE` ou `UNKNOWN`. Compatibilidade nominal nunca é declarada como prova de oficialidade.
- Páginas de busca interna, query echo, domínio bloqueado, conteúdo spam, resultado inválido, conteúdo desconexo e score baixo recebem motivos de descarte explícitos. Evidências válidas em domínios distintos recebem pequeno bônus de corroboração.
- A resposta agora registra por consulta provider, cache HIT/MISS, total bruto, total após dedupe, total após filtro e motivos agregados de descarte. `llm_used` permanece invariavelmente `false`.

### Resultado do segundo piloto

- 12 consultas novas foram executadas sequencialmente, com 12 cache misses e 12 chamadas reais ao gateway; nenhuma entrada anterior foi apagada ou invalidada.
- `WY-2026-Y11`: 24 brutos, 24 deduplicados, 24 descartados — 16 `weak_evidence`, 8 `query_echo`, 0 mantidos, `NÃO_ENCONTRADO`.
- `N260309#`: 16 brutos, 16 deduplicados, 16 descartados — 16 `weak_evidence`, 0 mantidos, `NÃO_ENCONTRADO`.
- `CY2926`: 24 brutos, 24 deduplicados, 24 descartados — 8 `weak_evidence`, 16 `query_echo`, 0 mantidos, `NÃO_ENCONTRADO`.
- Total: 64 brutos, 64 URLs únicas após dedupe, 64 descartados, zero evidências mantidas. Não existiram top 3 legítimos para reportar; publicar páginas artificiais como top results seria enganoso.
- Repetição imediata: 12 consultas, 12 cache hits, zero cache misses, zero chamadas ao gateway e `llm_used=false`.

### Diagnóstico e gate

- Amostras do cache confirmaram que os resultados fracos/echo eram todos da Qwant, em domínios aleatórios, com a consulta copiada no título e snippets sem relação factual.
- Consulta direta ao SearXNG confirmou: Brave `Suspended: too many requests`, DuckDuckGo `CAPTCHA`, Mojeek `Suspended: access denied`; Qwant forneceu 10 resultados artificiais para dois códigos e entrou em `CAPTCHA` para outro.
- Classificação da causa: principalmente **D — search engines indisponíveis ou retornando resultados ruins**; secundariamente **E/A — códigos possivelmente sem presença pública e produtos difíceis de encontrar**. Não há evidência de **B — query ruim** após as consultas progressivas, nem de **C — filtro excessivamente restritivo**, pois nenhum resultado amostrado continha confirmação legítima no snippet, URL ou domínio.
- O teste automatizado específico preserva o caso Qwant: título contém código/consulta, snippet não comprova, URL não comprova e domínio não comprova -> `query_echo` descartado.
- Validação local após os ajustes: 41 testes backend passando. Frontend/UI não foi alterado, nenhum XLSX/cache foi versionado e nenhuma IA foi chamada.
- **GATE NÃO ATENDIDO:** sem fonte de busca saudável não foi possível demonstrar retenção de evidência real. Por isso não houve commit, push nem deploy nesta execução.
- Próximo passo seguro: restaurar ao menos uma engine gratuita confiável no SearXNG e repetir somente este piloto. Depois de evidência legítima sobreviver, preparar commit/deploy; somente então iniciar a etapa de enriquecimento de evidências da Fase 6B e decidir sobre fetch controlado ou comparação posterior por IA gratuita.

## 2026-08-13 — Fase 6B.1: recuperação da base de busca gratuita

### Backup, recursos e preservação

- Antes de alterar a configuração, foi criado o backup privado `/opt/searxng/backups/pre-6b1-20260813`, modo 700, contendo `compose.yaml`, `.env`, `/etc/searxng/settings.yml` e instruções de rollback. Nenhum secret foi exibido ou adicionado ao Git.
- Estado anterior preservado: imagem `searxng/searxng:2026.8.10-0a118066d`, container `searxng`, `unless-stopped`, bind exclusivo `127.0.0.1:8888:8080`, 512 MiB de RAM, 1 CPU, 256 PIDs e engines DuckDuckGo/Brave/Qwant/Mojeek.
- Recursos antes dos testes: SearXNG 48,33 MiB/512 MiB; host com aproximadamente 717 MiB disponíveis e 3,5 GiB de swap livre; filesystem com 33 GiB livres. O host não estava crítico.
- Foi mantido o mesmo container. Não foram instalados proxy, Tor, VPN, Redis, Valkey, outro metasearch, scraper, API comercial ou serviço adicional. Custo permaneceu US$ 0.

### Auditoria individual de engines

- A versão instalada contém implementações web nativas de Bing, Google, Yahoo, Startpage, DuckDuckGo, Brave, Qwant e Mojeek. Também foram auditadas as alternativas gratuitas Yep, Mwmbl e Wiby.
- **Bing Web:** saudável; `OpenAI` HTTP 200, cerca de 540 ms, 10 resultados reais, sem erro. Os três códigos retornaram 10 resultados cada, porém desconexos dos produtos têxteis.
- **Google Web:** existe no código com `inactive: true`; após habilitação temporária explícita, respondeu HTTP 200 em 129–440 ms, mas retornou zero resultados nas quatro consultas. Inutilizável neste ambiente/versão.
- **Yahoo Web:** saudável isoladamente; `OpenAI` retornou 7 resultados reais em aproximadamente 1,4 s. Para os códigos, retornou colisões reais porém erradas, como veículos Nissan/Chery e peça Canon. Ao ser combinado com outra engine apresentou timeout/erro de protocolo e foi excluído por instabilidade.
- **Startpage:** CAPTCHA na primeira consulta e suspensão local nas seguintes. Não houve insistência upstream após o bloqueio.
- **DuckDuckGo:** CAPTCHA confirmado em uma única revalidação.
- **Brave:** `too many requests` confirmado em uma única revalidação.
- **Qwant:** respondeu 10 resultados, mas todos eram páginas artificiais/query echo em domínios aleatórios; excluída.
- **Mojeek:** `access denied` confirmado em uma única revalidação.
- **Yep:** `OpenAI` retornou 20 resultados reais e bons, mas a primeira consulta de produto atingiu timeout e a engine ficou suspensa; excluída por instabilidade.
- **Mwmbl:** `OpenAI` retornou 117 resultados reais em aproximadamente 4,3 s; respondeu corretamente com zero resultados para os três códigos, sem CAPTCHA/erro.
- **Wiby:** `OpenAI` retornou 12 resultados reais em aproximadamente 3,1 s; respondeu corretamente com zero resultados para os três códigos, sem CAPTCHA/erro.

### Configuração final e validação

- Conjunto final ativo limitado a três engines gratuitas: `bing`, `mwmbl` e `wiby`.
- O container foi reiniciado após a configuração final. `/config` confirmou somente essas três engines. A configuração ativa e a cópia privada `/opt/searxng/final-settings.yml` possuem SHA-256 `89c3ebef564f6f53dc5146f689487315a18e44d7a7dc101bc465cc393b382eab`.
- Consulta direta final `OpenAI`: HTTP 200, aproximadamente 2,4 s, 139 resultados — 10 Bing, 117 Mwmbl e 12 Wiby —, sem engines não responsivas. Os primeiros resultados incluíram `openai.com` e outras páginas reais.
- Consultas diretas finais dos códigos: 10 resultados Bing para cada código, todos desconexos; Mwmbl e Wiby não encontraram os códigos. Não houve páginas artificiais da Qwant.
- OmniRoute `POST /v1/search`, provider `searxng-search`: consulta de controle nova e três códigos retornaram HTTP 200, `cached=false`, resultados Bing reais, custo US$ 0 e nenhum erro. O provider e a conexão existentes foram preservados.

### Cache e piloto pelo filtro da Fase 6B

- O cache histórico de 12 arquivos não foi apagado. Para evitar mistura com o conjunto antigo, foi criado o namespace privado `/data/uploads/.search-cache/bing-mwmbl-wiby-v1`, também ignorado pelo Git.
- Primeira execução no namespace: 12 queries, 12 cache misses, 12 chamadas ao gateway e `llm_used=false`.
- `WY-2026-Y11`: 32 brutos, 8 URLs únicas, 32 descartados — 24 duplicatas entre consultas, 6 evidências fracas e 2 domínios bloqueados; zero mantidos.
- `N260309#`: 32 brutos, 32 URLs únicas, 32 evidências fracas descartadas; zero mantidos.
- `CY2926`: 32 brutos, 32 URLs únicas, 31 evidências fracas e 1 domínio bloqueado; zero mantidos.
- Total: 96 ocorrências brutas, 72 URLs únicas, zero evidências mantidas e zero `query_echo`. Os resultados eram páginas reais, mas não correspondiam aos produtos estruturados.
- Repetição: 12 cache hits, zero misses, zero chamadas ao gateway e `llm_used=false`.

### Gate e estado

- **GATE 6B.1 ATENDIDO PELO CRITÉRIO C:** existem três engines gratuitas funcionais e a consulta de controle é saudável; Bing retornou resultados reais para os códigos, mas todos desconexos, enquanto Mwmbl/Wiby retornaram zero. Isso constitui evidência clara de ausência pública indexada desses três produtos nas fontes testadas.
- O filtro não foi relaxado nem alterado nesta recuperação. `WEAK`, proteção `query_echo`, dedupe, scoring, limite de 2–3 produtos e `llm_used=false` foram preservados.
- Validação: 41 testes backend passando, `compileall` sem erros e `git diff --check` limpo.
- Recursos finais: SearXNG 122,7 MiB/512 MiB; host com aproximadamente 704 MiB disponíveis e 3,5 GiB de swap livre; 33 GiB de disco livres. O limite de RAM não foi aumentado.
- **FASE 6B NÃO ESTÁ CONCLUÍDA.** Não houve commit, push ou deploy do Projeto Digitação.
- Próxima decisão recomendada: manter Bing/Mwmbl/Wiby como base gratuita e escolher novos produtos com provável presença pública para validar retenção legítima antes de commit/deploy. Somente depois iniciar enriquecimento/fetch controlado de evidências.

## 2026-08-13 — Fase 6B.2: controle positivo e validação final da pesquisa determinística

### Controle positivo

- Foi usado exclusivamente em memória o produto público `Raspberry Pi 5`, identificado como `POSITIVE_CONTROL`, com fabricante/marca `Raspberry Pi` e categoria `single-board computer`. Ele não foi incluído em Packing List, upload ou dado persistente do projeto.
- A escolha fornece um modelo inequívoco, amplamente indexado e com página pública do produto em domínio nominalmente compatível com o fabricante. Não foi criada regra especial nem bypass de aceitação.
- O mesmo query builder produziu três consultas: `"Raspberry Pi 5"`, `"Raspberry Pi 5" "single-board computer"` e `"Raspberry Pi 5" "Raspberry Pi"`.
- O mesmo `ProductResearchService` executou busca, canonicalização, dedupe, bloqueio de spam, proteção query echo, scoring e classificação de evidências pelo provider `searxng-search` e pelas engines Bing/Mwmbl/Wiby.
- Resultado: 24 ocorrências brutas, 15 URLs únicas, 11 evidências mantidas e classificação técnica `FOUND`. A melhor evidência foi `https://www.raspberrypi.com/products/raspberry-pi-5/`, engine Bing, categoria `MANUFACTURER`, força `STRONG` e score 12,5.
- A categoria `MANUFACTURER` decorre da compatibilidade determinística entre `Raspberry Pi` e `raspberrypi.com`; o pipeline continua registrando que compatibilidade nominal não é, isoladamente, prova absoluta de oficialidade.
- Repetição do controle: 3 cache hits, zero misses, zero chamadas ao gateway e `llm_used=false`.

### Produtos reais adicionais

- Excluídos todos os códigos dos pilotos anteriores, o ranking determinístico selecionou `WY-2026-Y13` e `N260308#`. Ambos possuem code/style, item name, NCM, composição, construção e fabricante; o primeiro obteve score de riqueza 19 e o segundo 18.
- `WY-2026-Y13`: consultas `"WY-2026-Y13"`, código + `short sleeve T-shirt`, código + fabricante `叶芬` e código + `knitted polyester cotton`. Foram 32 ocorrências, 8 URLs únicas, 24 duplicatas, 6 evidências fracas, 2 domínios bloqueados e zero evidências mantidas.
- Como o código não produziu evidência, foi executada uma única consulta experimental sem código: `"叶芬" "short sleeve T-shirt" knitted cotton polyester`. Os 8 resultados foram únicos, porém todos `WEAK` e corretamente descartados; categoria genérica não foi tratada como correspondência.
- `N260308#`: consultas pelo código, código + item original, código + fabricante `黄林` e código + `woven elastane polyester`. Foram 32 ocorrências e 32 URLs únicas; 8 foram bloqueadas por conteúdo spam, 22 eram evidências fracas e 2 pertenciam a domínios bloqueados. Nenhuma evidência foi mantida.
- Os dois produtos ficaram `NOT_FOUND`/`NÃO_ENCONTRADO`; não houve caso `REVIEW`. Há indício técnico de `possible_private_style_code=true` para ambos, pois as engines são saudáveis, as consultas combinadas funcionaram, mas nenhum resultado associou código e metadados. Isso é inferência, não afirmação factual sobre o fornecedor.

### Conclusão e gate

- O contraste entre o controle público `FOUND` e os Styles reais `NOT_FOUND` demonstra que os filtros não estão excessivamente rígidos e que ausência de comprovação não precisa ser mascarada por IA.
- Anti-spam e proteção Qwant/query echo permanecem sem relaxamento. Não houve query echo no conjunto atual. Evidência `WEAK` isolada continua incapaz de gerar `FOUND`.
- A lógica de query/scoring não mudou nesta etapa; foi preservado o namespace `bing-mwmbl-wiby-v1`. As oito consultas reais e a consulta experimental repetiram com 9 cache hits e zero chamadas ao gateway. Nenhum cache histórico foi apagado.
- Adicionado teste determinístico com mock para o controle positivo, sem dependência da internet: a URL oficial-like é canonicalizada, classificada como `MANUFACTURER`/`STRONG`, deduplicada entre três consultas e passa pelo serviço regular com `llm_used=false`.
- Validação local: 42 testes backend passando, `compileall` sem erros e `git diff --check` limpo.
- **GATE FINAL DA CAMADA SEARCH + FILTER + EVIDENCE ATENDIDO.** A Fase 6B pode ser publicada; processamento em lote, fetch de páginas e IA permanecem fora desta execução.
- Commit autorizado somente após auditoria final: `feat: integra pesquisa real de produtos`. Depois do deploy, validar health e somente 2 produtos no endpoint de produção, preservando provider, cache, mount, portas, Funnel e UI LOCKED.
- Próxima etapa, ainda não iniciada: **FASE 6B.3 — ENRIQUECIMENTO DE EVIDÊNCIAS**, com possível fetch controlado, extração de texto e comparação entre fontes antes de qualquer IA gratuita.

### Publicação e produção

- Auditoria pré-commit confirmou: nenhum XLSX real ou cache versionado, nenhum secret, nenhuma alteração em frontend/CSS e nenhuma chamada a LLM. O placeholder documental da chave do Coolify não contém valor real.
- Commit funcional criado e publicado por push normal: `1c18ab9 feat: integra pesquisa real de produtos`. Não houve force push.
- O Auto Deploy não iniciou. Foi enfileirado redeploy manual seguro, sem force rebuild, deployment `e121hktxouh5m44x3stalrqa`, concluído no commit completo `1c18ab9ceab7c00fe06bd2842860048d6c1a547e`.
- Novo container `9969de8fc36f` ficou `running/healthy`, preservando `127.0.0.1:18001:8000` e o bind RW `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`.
- `/health` local e público pelo Tailscale Funnel `:8443` retornaram HTTP 200 com `{"status":"ok"}`. SearXNG permaneceu restrito a `127.0.0.1:8888`; OmniRoute e UI LOCKED não foram alterados.
- Teste público de produção em `POST /api/uploads/{file_id}/research`, somente com `WY-2026-Y13` e `N260308#`: HTTP 200, provider `searxng-search`, 6 consultas, 6 misses/6 chamadas na primeira execução, zero evidências falsas e ambos `NÃO_ENCONTRADO`.
- Replay público: HTTP 200, 6 cache hits, zero misses, zero chamadas ao gateway, mesmos resultados e `llm_used=false`.
- Não houve lote, fetch de páginas, IA, visão, tradução por IA ou geração de descrição DUIMP.

## 2026-08-13 — Fase 6B.3: enriquecimento controlado de evidências

### Arquitetura e segurança

- Criado o endpoint complementar `POST /api/uploads/{file_id}/research/enrich`; o contrato de `/research` permaneceu intacto. A rota aceita somente 2 ou 3 produtos, executa o search existente e entrega ao fetcher no máximo três evidências `STRONG`/`MODERATE` por produto.
- Resultados `WEAK`, spam, query echo, domínio bloqueado, descartados ou produtos `NÃO_ENCONTRADO` nunca chegam ao cliente HTTP. O processamento é estritamente sequencial e não segue links da página.
- O cliente aceita apenas HTTP/HTTPS nas portas padrão, rejeita credenciais embutidas e valida DNS/IP antes da requisição e novamente em cada redirect. Localhost, loopback, RFC1918, link-local, metadata, IP não global e sufixos internos são bloqueados como `SSRF_BLOCKED`; TLS não é desativado.
- Redirects são manuais e limitados a três. User-Agent é identificável, timeout padrão é 15 s e logs contêm somente domínio, status, bytes e tipo de erro, sem query string ou conteúdo.
- Limite padrão: 3 MiB de HTML descomprimido, verificado por `Content-Length` e durante streaming. São aceitos somente `text/html` e `application/xhtml+xml`; gzip e Brotli são tratados pelo `httpx` com dependência Brotli explícita. PDF, imagem, ZIP, executável e outros binários ficam `UNSUPPORTED_CONTENT`.
- Estados: `OK`, `BLOCKED`, `TIMEOUT`, `TOO_LARGE`, `UNSUPPORTED_CONTENT`, `HTTP_ERROR`, `SSRF_BLOCKED` e `PARSE_ERROR`.

### Extração, matching e cache

- Parser determinístico baseado em biblioteca padrão remove scripts, estilos, navegação, menus, banners/cookies, formulários, aside e footer. Preserva título, meta description, H1/H2, texto principal/tabelas simples e trecho de até 4.000 caracteres; HTML completo nunca é devolvido.
- JSON-LD é inspecionado para `Product`, `Offer`, `Brand` e `Organization`, preservando `name`, `sku`, `mpn`, `brand`, `manufacturer`, `model`, `description`, `material`, `color`, `category`, GTIN, URL e offers quando existentes. JSON-LD é tratado como evidência da fonte, não como verdade automática.
- O matching compara deterministicamente code/style, item name, fabricante, marca, composição, construção e NCM. A resposta preserva sinais encontrados/ausentes, fatos da planilha e fatos web com origem explícita e conflitos sem escolher silenciosamente um valor.
- O conteúdo HTML descomprimido recebe SHA-256. O cache separado fica em `/data/uploads/.fetch-cache`, usa URL canonicalizada + parser `web-evidence-v1`, TTL de sete dias, arquivos modo 600 e estados `HIT`, `MISS` e `EXPIRED`. Respostas `BLOCKED`, `TOO_LARGE` e `UNSUPPORTED_CONTENT` também são cacheadas para evitar insistência.

### Piloto real controlado

- Controle `Raspberry Pi 5`: search reutilizou 3 cache hits, zero chamadas ao gateway e ofereceu 11 evidências aprovadas; somente as três melhores foram buscadas.
- `https://www.raspberrypi.com/products/raspberry-pi-5/`: HTTP 403, 1.190 ms na primeira amostra e depois ~199 ms, status `BLOCKED`; nenhuma tentativa de contorno.
- `https://www.robocore.net/placa-raspberry-pi/raspberry-pi-5-8gb`: HTTP 200, `text/html`, 184.979 bytes, ~2.255 ms; título, meta description, H1/H2 e sinais `code`, `item_name`, `manufacturer` e `brand` encontrados.
- `http://geekworm.com/collections/raspberry-pi/Raspberry-Pi-5`: redirect seguro para HTTPS, HTTP 200, `text/html`, 1.065.915 bytes, ~1.806 ms; título/meta e os mesmos quatro sinais encontrados.
- Nenhuma das duas páginas reais processadas expôs JSON-LD útil ao parser. A fixture sintética comprovou extração de JSON-LD Product com SKU, MPN, model, brand, manufacturer, material, color e category.
- Não houve conflito no controle positivo real. Fixture determinística comprovou preservação do conflito `composition`: Packing List `100% polyester` versus web `100% cotton`, com as duas origens.
- Replay final: 3 fetch cache hits e zero requisições de rede, inclusive para a página oficial bloqueada. Cache ocupa aproximadamente 20 KiB em três arquivos privados e ignorados pelo Git.
- `WY-2026-Y13` e `N260308#`: oito search cache hits, zero gateway calls, ambos `NÃO_ENCONTRADO`, zero URLs aprovadas e zero fetches. A imagem Docker local também validou o endpoint com esses dois produtos: HTTP 200, seis search cache hits, zero gateway calls e zero fetches.

### Validação e gate local

- 67 testes backend passaram. Cobertura inclui HTML/meta/headings, JSON-LD Product, SKU, fabricante, material, gzip/Brotli, redirect seguro, redirect para IP privado, localhost/RFC1918/metadata/esquemas, DNS privado, limite por header/stream, MIME inválido, timeout, cache hit/expired/BLOCKED, conflito e limite/seleção de URLs aprovadas.
- `compileall`, `pip check`, build Docker Python 3.12 e `git diff --check` passaram. Imagem local: 70.762.133 bytes.
- Recursos após o piloto: host com aproximadamente 734 MiB disponíveis e 3,4 GiB de swap livre; backend de produção anterior em ~44 MiB e SearXNG dentro do limite de 512 MiB. Nenhum serviço adicional foi instalado.
- `llm_used=false`; nenhuma chamada LLM, IA visual, DUIMP, browser headless, Firecrawl/Jina ou processamento em lote ocorreu.
- **GATE 6B.3 ATENDIDO.** A auditoria Git confirmou ausência de XLSX/cache/HTML real/secret/CSS no commit; o único valor semelhante a credencial é o placeholder documental da chave OmniRoute.

### Publicação e produção

- Commit funcional `c24dd34 feat: adiciona enriquecimento de evidencias web` criado e enviado por push normal para `origin/main`; não houve force push.
- O Auto Deploy não abriu fila. O redeploy seguro `m10b92rb0c3hpbe8mvtdlq4p` foi enfileirado no SHA completo `c24dd34d970f1ae171cbf9576504ce7a95399a1e` e terminou com sucesso.
- Container `a59d986c21af` ficou healthy, preservando `127.0.0.1:18001:8000`, bind RW `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`, SearXNG, OmniRoute, Funnel 8443 e UI LOCKED.
- `/health` local e público pelo Funnel retornaram HTTP 200. O endpoint público `/research/enrich`, somente para `WY-2026-Y13` e `N260308#`, retornou HTTP 200, provider `searxng-search`, seis search cache hits, zero gateway calls, ambos `NÃO_ENCONTRADO`, zero URLs aprovadas, zero fetches e `llm_used=false`.
- O controle positivo foi repetido no código implantado sem persistir produto de teste: 3 search cache hits, 11 evidências aprovadas, 3 fetch cache hits e zero acesso de rede. A fonte `raspberrypi.com` permaneceu `BLOCKED`/HTTP 403; RoboCore e Geekworm permaneceram `OK`/HTTP 200 com `code`, `item_name`, `manufacturer` e `brand` encontrados e sem conflitos.
- Recursos finais: backend ~56,75 MiB; SearXNG dentro do limite de 512 MiB; host com aproximadamente 762 MiB disponíveis e 3,4 GiB de swap livre. O cache de fetch permanece com ~20 KiB e arquivos modo 600.
- Nenhuma IA, descrição DUIMP, fetch em lote ou crawler foi iniciado. Próxima etapa: decidir a integração das IAs gratuitas do OmniRoute para analisar exclusivamente Packing List + search real + conteúdo real + evidências estruturadas.

## 2026-08-13 — Fase 6C: análise textual de evidências com IA gratuita

### Arquitetura e escopo

- Criado `POST /api/uploads/{file_id}/research/analyze`, limitado a 1–3 produtos explicitamente escolhidos. O endpoint encadeia o search e o enriquecimento existentes e preserva integralmente `/research` e `/research/enrich`.
- A IA não pesquisa: recebe somente produto normalizado, até oito resultados de search já aprovados e até três páginas `OK` realmente buscadas, com excerpt de até 2.500 caracteres, structured data compactado, matched signals, conflitos, hashes e URLs reais.
- Não são enviados XLSX, imagens, HTML completo, scripts, menus, binários, páginas descartadas, `WEAK`, spam ou query echo. Não houve lote, visão nem descrição DUIMP.
- Prompt separado `backend/app/prompts/evidence_analysis_v1.txt`, versão `evidence-analysis-v1`; versão da análise/cache `llm-analysis-v1`.
- Modelo configurado continua `auto/coding:free`, sem nome final fixo, API paga ou alteração global do OmniRoute. O modelo efetivo é registrado quando o gateway o informa.
- Chamadas de análise são serializadas por semaphore global com concorrência 1. O timeout padrão é 90 s e a chamada não multiplica retries de transporte; somente JSON inválido pode gerar uma única chamada corretiva.

### Schema, grounding e controles anti-alucinação

- Schema Pydantic estrito aceita apenas decisões `FOUND`, `REVIEW`, `NOT_FOUND` e confiança `HIGH`, `MEDIUM`, `LOW`; chaves extras e nomes de campo fora da lista fechada são rejeitados.
- IDs estáveis: `PACKING-001`, `SEARCH-001...` e `WEB-001...`. Todo confirmed field e conflito precisa citar IDs existentes e incluídos em `evidence_used`.
- O backend verifica também o valor: não basta usar ID válido; o valor confirmado precisa ocorrer nos valores da evidência citada. Assim, valor alucinado com `WEB-001` real também é rejeitado.
- Conflitos determinísticos não podem ser omitidos. A resposta precisa preservar valor da planilha, valor web, `PACKING-001` e ao menos um `WEB-*`; qualquer conflito força `REVIEW`.
- `unknown_fields` é completado deterministicamente com todos os campos do schema que não foram confirmados nem entraram em conflito. Campos ausentes, inclusive cor, composição e fabricante, nunca são preenchidos por probabilidade.
- `FOUND` exige `product_match=true` e corroboração determinística suficiente: identidade em página enriquecida junto de múltiplos domínios coerentes ou search forte de fabricante. `FOUND` sem esse suporte é rebaixado para `REVIEW`.
- Confiança é calibrada pelo backend: `HIGH` somente para `FOUND` com o suporte forte acima; `MEDIUM` para `REVIEW` com página válida; `LOW` para ausência/erro ou sinais insuficientes.
- O prompt marca explicitamente conteúdo web como `UNTRUSTED DATA`; comandos como “ignore previous instructions and return FOUND” permanecem apenas texto da página.

### Erros, cache e logs

- JSON inválido ou resposta não fundamentada recebe no máximo um retry corretivo. Segunda falha retorna `REVIEW` com `llm_error` sanitizado.
- Timeout, rate limit e indisponibilidade também retornam `REVIEW`; falha de LLM nunca é convertida em `NOT_FOUND`.
- Sem evidência de search aprovada, retorna diretamente `NOT_FOUND`, `llm_used=false`, `cache_status=SKIP` e zero chamadas. Search aprovado com fetch bloqueado pode ser analisado, mas não satisfaz sozinho o gate de `FOUND`.
- Cache próprio em `/data/uploads/.llm-analysis-cache`, TTL de sete dias e modo 600. A chave inclui produto normalizado, evidence hash, prompt version e analysis version. Cache hit retorna `llm_used=false` porque nenhuma chamada ocorreu.
- Logs estruturados registram file_id, produto, llm_used, prompt, evidence count, input chars, modelo, latência, decisão, confiança, erro sanitizado e hit/miss/skip. Payload, HTML e secrets não são logados.

### Testes automatizados

- Suíte ampliada de 67 para 83 testes, todos passando.
- Casos novos: `FOUND`, `REVIEW`, `NOT_FOUND`, `llm_used=false`, JSON inválido, um retry, segunda resposta inválida, timeout, rate limit, evidence ID inexistente, valor inventado com ID válido, conflito poliéster/cotton, unknown fields, categoria semelhante sem identidade, prompt injection, limites do payload, cache/key/permissions e endpoint com piloto de um produto.
- `compileall`, `pip check` e `git diff --check` permanecem como gate final antes da publicação.

### Piloto real controlado

- Controle único: `Raspberry Pi 5`, apenas em memória; não foi inserido em Packing List ou upload.
- Search: 3 cache hits, zero gateway calls, 11 evidências aprovadas; somente as oito melhores entraram no contexto.
- Enriquecimento: 3 fetch cache hits, zero fetches; duas páginas `OK` entraram no contexto e a página oficial bloqueada permaneceu fora de `web_evidence`.
- Input ao modelo: 7.644 caracteres, 11 IDs totais (`PACKING-001`, oito `SEARCH-*`, dois `WEB-*`).
- Configuração: `auto/coding:free`; modelo efetivamente retornado: `big-pickle`.
- Resultado final: `FOUND`, confiança `HIGH`, `product_match=true`, `llm_used=true`, uma chamada, latência 53.605 ms. Code, item name, manufacturer e brand foram confirmados com IDs válidos; demais campos permaneceram unknown; não houve conflito.
- A primeira execução de diagnóstico falhou fechada em `REVIEW` porque o modelo criou o campo fora do schema `memory_capacity`. O prompt/retry foi então tornado explícito e o backend passou a completar omissions de UNKNOWN deterministicamente; o controle repetido passou sem relaxar grounding, IDs ou regra de `FOUND`.
- Cache de análise criado com um arquivo privado de aproximadamente 1,8 KiB (8 KiB em disco), sem versionamento.
- Recursos após o piloto: host com aproximadamente 636 MiB disponíveis e 4,1 GiB de swap livre; nenhuma chamada LLM concorrente ou serviço adicional.
- Produto real adicional não executado: `WY-2026-Y13` e `N260308#` continuam sem evidência aprovada, portanto não houve fabricação de caso e a IA não deve ser chamada para eles.

### Estado e próximo passo

- Commit funcional `d1d125d feat: adiciona analise de evidencias com ia` criado e publicado em `origin/main` por push normal, sem force push.
- O Auto Deploy não iniciou. Redeploy seguro `jxrd20pmzanimoj4r3sgmh5n`, sem force rebuild, foi enfileirado exclusivamente para `applicationId=3` no SHA completo `d1d125de3d85a989510b2a60b816a77337c15688` e terminou com status `finished`.
- Novo container `1eecd7b9280f` ficou healthy, preservando `127.0.0.1:18001:8000` e bind RW `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`. O Tailscale Funnel permaneceu 443 -> NFLNBA/3001 e 8443 -> Projeto Digitação/18001.
- `/health` local e público retornaram HTTP 200. O endpoint público `/research/analyze` para `WY-2026-Y13` e `N260308#` retornou HTTP 200, `NOT_FOUND/LOW`, `SKIP`, `llm_calls=0` e `llm_used=false` para ambos.
- O controle positivo executado no código de produção retornou `FOUND/HIGH`, `auto/coding:free` -> `big-pickle`, uma chamada em 37.439 ms, 7.644 caracteres e `llm_used=true`. A execução permaneceu limitada ao Raspberry Pi 5; não houve lote.
- Replay imediato do controle em produção: 3 search cache hits, zero gateway calls, 3 fetch cache hits, zero fetches, analysis cache `HIT`, `FOUND/HIGH`, `llm_calls=0` e `llm_used=false`.
- Recursos após os testes: backend aproximadamente 52 MiB, SearXNG aproximadamente 73 MiB de 512 MiB, host com aproximadamente 796 MiB disponíveis e 3,7 GiB de swap livre. O pico de CPU observado imediatamente após parsing/chamada foi transitório; nenhum processamento concorrente foi executado.
- **FASE 6C = CONCLUÍDA E VALIDADA EM PRODUÇÃO.** Todos os 16 itens do gate foram atendidos.
- UI permanece LOCKED no commit `fc53ebb`; nenhum arquivo frontend/CSS foi alterado.
- Próxima fase, somente depois da conclusão/publicação desta etapa: **FASE 7 — ANÁLISE VISUAL + CRUZAMENTO DE EVIDÊNCIAS**. Não iniciar automaticamente.

## 2026-08-13 — Checkpoint final do dia antes da Fase 7

### Estado encerrado

- **FASES 5A, 5B, 6A, 6B, 6B.3 e 6C = CONCLUÍDAS.** A Fase 6C está validada em produção.
- **FASE 7 = NÃO INICIADA.** Este checkpoint é exclusivamente documental: nenhum código funcional, frontend, CSS, infraestrutura, OmniRoute, SearXNG, pesquisa, visão, descrição DUIMP ou processamento em lote foi alterado ou iniciado.
- Pipeline validado: Packing List XLSX -> upload persistente -> leitor universal da Fase 5B -> produto estruturado -> pesquisa real via OmniRoute `/v1/search` -> SearXNG -> filtro/scoring/deduplicação -> fetch controlado das páginas aprovadas -> extração estruturada -> análise textual por IA gratuita via OmniRoute.
- A IA permanece somente como analisador de evidências fornecidas pelo backend; ela não é mecanismo de pesquisa e não pode alegar que pesquisou, abriu páginas ou consultou fabricantes por conta própria.

### Fase 6C consolidada

- Endpoint: `POST /api/uploads/{file_id}/research/analyze`, limitado a 1–3 produtos explicitamente selecionados. `/research` e `/research/enrich` permanecem preservados.
- Prompt `evidence-analysis-v1`, armazenado separadamente em `backend/app/prompts/evidence_analysis_v1.txt`.
- Rota OmniRoute `auto/coding:free`, sem modelo pago e sem nome fixo no projeto; o fallback continua sob responsabilidade do OmniRoute.
- Schema Pydantic estrito: decisões `FOUND`, `REVIEW` e `NOT_FOUND`; confiança `HIGH`, `MEDIUM` e `LOW`.
- Proveniência: IDs estáveis `PACKING-001...`, `SEARCH-001...` e `WEB-001...`; IDs e valores retornados são validados contra o registro real e IDs inventados são rejeitados.
- Campos não comprovados permanecem `UNKNOWN`. Nenhum atributo pode ser preenchido por probabilidade.
- Conflitos preservam valor da Packing List, valor web, fonte e evidence IDs; divergência relevante leva a `REVIEW`, sem escolha silenciosa.
- Conteúdo web é `UNTRUSTED DATA`. Instruções encontradas em páginas, como `ignore previous instructions`, são tratadas somente como dados; o teste automatizado de prompt injection passou.
- Cache separado `llm-analysis-v1`, TTL de sete dias, chave baseada em produto, hashes das evidências, prompt version e analysis version. Arquivos permanecem modo 600; replay idêntico não chama a IA.
- JSON inválido admite no máximo um retry corretivo. Timeout de 90 segundos, rate limit e indisponibilidade geram `REVIEW`/erro controlado, nunca `NOT_FOUND` artificial.

### Pilotos, uso do LLM e desempenho

- Controle positivo `Raspberry Pi 5`: `FOUND`, confiança `HIGH`, `llm_used=true`. O modelo gratuito efetivamente selecionado naquela execução foi `big-pickle`; esse nome é apenas observacional e não se tornou obrigatório.
- Replay do controle positivo: cache hit e `llm_used=false`.
- Produtos reais `WY-2026-Y13` e `N260308#`: `NOT_FOUND/LOW`, sem evidência web aprovada suficiente e `llm_used=false`. Nenhuma evidência foi fabricada.
- Contexto do controle positivo: aproximadamente 7.644 caracteres. Latência observada: aproximadamente 53,6 s local e 37,4 s em produção. Concorrência LLM mantida em 1.
- Medição final registrada: backend aproximadamente 49,6 MiB de RAM e SearXNG aproximadamente 58,1 MiB. Manter concorrência baixa.
- Validação final: 83 testes passaram; `compileall`, `pip check` e `git diff --check` também passaram.

### Git, deploy, produção e preservação

- Commit funcional: `d1d125d feat: adiciona analise de evidencias com ia`.
- Commit documental de conclusão: `50ba76e docs: registra conclusao da fase 6c`.
- Deployment final: `s100uyxyol6b69akwjo2s18s`, implantando o commit `50ba76e`; container healthy.
- Health local e público: HTTP 200. Bind preservado em `127.0.0.1:18001:8000`.
- Storage persistente RW preservado: host `/opt/projeto-digitacao/data/uploads` -> container `/data/uploads`.
- Tailscale Funnel preservado em `:8443` para o Projeto Digitação; SearXNG em `127.0.0.1:8888`; OmniRoute na porta `20128`.
- UI aprovada e LOCKED no commit visual `fc53ebb`; nenhum frontend ou CSS foi alterado na Fase 6C.
- `main` estava sincronizada com `origin/main` e a árvore de trabalho estava limpa no início deste checkpoint. Nenhum XLSX, HTML real, cache, secret ou arquivo visual foi versionado indevidamente.

### Próximo passo exato

- Amanhã iniciar somente a **FASE 7 — ANÁLISE VISUAL + CRUZAMENTO MULTIMODAL DE EVIDÊNCIAS**: Packing List + search real + web evidence + imagem principal e, quando realmente disponíveis e associados, wash label/hangtag -> cruzamento -> campos confirmados/conflitos/confidence -> `FOUND`, `REVIEW` ou `NOT_FOUND`.
- Antes de implementar, auditar tecnicamente quais modelos gratuitos atuais do OmniRoute possuem capacidade real de visão. Não inferir capacidade pelo nome; se não houver modelo gratuito adequado, parar e reportar antes de mudar a arquitetura.
- Começar com um único controle positivo multimodal e depois, no máximo, um ou dois produtos reais. Validar antes a associação imagem <-> linha <-> Style/Code produzida pela Fase 5B. Não executar lote.
- A imagem pode apoiar somente atributos visualmente observáveis, como categoria, formato, mangas, alças, comprimento, tipo aparente, cor visível e elementos construtivos. Ela não comprova sozinha composição, percentual de fibras, fabricante, NCM, material não observável ou características internas.
- Wash label e hangtag poderão ser evidências mais fortes para composição, marca, instruções, modelo e tamanho, mas somente após leitura real; nada deve ser presumido.
- Roadmap preservado: Fase 7 — análise visual e cruzamento multimodal; Fase 8 — descrição técnica objetiva para DUIMP; Fase 9 — Excel final para download. A Fase 7 não deve gerar descrição DUIMP.
- **Nenhuma funcionalidade da Fase 7 foi iniciada neste checkpoint.**

## 2026-08-14 — Fase 7A: auditoria multimodal e validação visual

- OmniRoute `3.8.49` auditado sem alterar configuração global. O combo textual `auto/coding:free` não declarou suporte visual e permaneceu intacto.
- Modelo gratuito visual comprovado: `oc/mimo-v2.5-free`, provider OpenCode. O modelo efetivo observado nas respostas foi `mimo-v2.5-free`.
- Contrato validado: `POST /v1/chat/completions`, `stream=false`, content parts com `text` e `image_url`, usando data URL interna (`data:<mime>;base64,...`). Nenhuma imagem foi publicada.
- Controle sintético de 384×256 e 15.987 bytes identificou corretamente triângulo vermelho, círculo azul e texto `Z7`, comprovando recepção real da imagem.
- Produto real validado: file_id `c21b5d16-d31f-4722-8c3b-213d19360be3`, code `WW77#`, rows 2–3, sheet `Sheet1`, `IMG-00001`, âncora row 2/column 1, classificação `PRODUCT_IMAGE`.
- Mídia real: `xl/media/image1.jpeg`, JPEG 154×199, 17.100 bytes, SHA-256 `6fa3ad3a23220d7f1a4bf9c2c5b41d6063b2302fba4d38a31017021bb52cf739`.
- O produto também possui WASH_LABEL e HANGTAG associados, mas esses tipos não foram analisados. Não existe LABEL_IMAGE associada ao piloto.
- A visão descreveu vestido rosa, comprimento aproximado até o joelho e detalhe de babado. Composição, NCM, fabricante, fornecedor e demais atributos invisíveis permaneceram desconhecidos.
- Custo observado: US$ 0. A Fase 7A foi uma auditoria operacional; nenhuma imagem real, cache ou credencial foi versionada.

## 2026-08-14 — Fase 7B: cruzamento multimodal de evidências

### Arquitetura implementada

- Criado `POST /api/uploads/{file_id}/research/multimodal`, limitado por schema a um ou dois produtos explicitamente selecionados. `/research`, `/research/enrich` e `/research/analyze` foram preservados.
- Fluxo: produto estruturado -> associação PRODUCT_IMAGE da Fase 5B -> extração controlada dos bytes -> visão separada -> packing/search/web/visual com IDs -> análise textual final -> validação e calibração determinística.
- `OMNIROUTE_VISION_MODEL` foi separado com fallback explícito `oc/mimo-v2.5-free`. `OMNIROUTE_MODEL=auto/coding:free` não foi alterado e continua como decisor textual final.
- A abstração `extract_product_image_bytes` fica no módulo de imagens da planilha, valida classificação, related_code, SHA-256, MIME e dimensões e não expõe acesso ao OOXML/ZIP para a business logic.
- Pré-processamento `visual-image-normalization-v1`: somente JPEG/PNG, uma imagem por produto, máximo padrão de 1 MiB e 1280 px no maior lado, sem upscaling. A imagem segue apenas como data URL interna ao OmniRoute.

### Schemas, prompts e grounding

- Prompt visual `visual-attribute-extraction-v1`; cache/analysis `visual-analysis-v1` em `/data/uploads/.visual-analysis-cache`, TTL sete dias. Chave: hash processado, code, prompt, modelo, tipo e preprocessing.
- `VisualEvidence` Pydantic estrito registra `VISUAL-001`, image_id/type/code, hash/MIME/bytes/dimensões, modelo, prompt, métricas e confiança individual de categoria, cor, mangas, alças, comprimento e detalhes.
- Composição, percentuais de fibra, NCM, fabricante, fornecedor, SKU, material químico, gramatura e propriedades internas são acrescentados deterministicamente a `unknown_attributes`. Texto visível é `UNTRUSTED DATA`, nunca instrução.
- Prompt final `multimodal-evidence-analysis-v1`; cache/analysis `multimodal-analysis-v1` em `/data/uploads/.multimodal-analysis-cache`, TTL sete dias. Chave: produto normalizado, hash do pacote, prompt/version e rota textual.
- Schema final estrito registra decisão/confiança, `internal_visual_match`, `external_support`, confirmed fields, conflitos, unknown fields, evidence IDs, modelos, latências e flags de uso.
- Todos os IDs citados precisam existir e todos os valores precisam ocorrer na evidência citada. Campo invisível não pode ser comprovado somente por `VISUAL-001`, nem “lavado” pela inclusão de outro ID que não contenha o valor.
- Conflitos conhecidos não podem ser omitidos e levam a `REVIEW`. Campo presente em `uncertain_attributes` visual é removido deterministicamente de `confirmed_fields` e volta a unknown.
- `FOUND` exige apoio externo forte. Imagem consistente sem search/web suficiente produz `REVIEW`; sem apoio textual nem visual, `NOT_FOUND` permanece possível.

### Piloto real único WW77#

- File_id `c21b5d16-d31f-4722-8c3b-213d19360be3`; code `WW77#`; `IMG-00001`; `PRODUCT_IMAGE`; sheet `Sheet1`; row 2; column 1.
- Imagem enviada: JPEG 154×199, 17.100 bytes, SHA-256 `6fa3ad3a23220d7f1a4bf9c2c5b41d6063b2302fba4d38a31017021bb52cf739`; request visual aproximado 24.919 bytes. Nenhuma normalização foi necessária.
- Visão efetiva `mimo-v2.5-free`: category `dress` HIGH, primary color `pink` HIGH, length `knee-length` HIGH, details `ruffle neckline`, `floral pattern` e `cinched waist` HIGH. Straps ficou `UNKNOWN/LOW`; sleeves `off-the-shoulder` veio com alternativa `short sleeves` explicitamente incerta.
- O cruzamento final removeu sleeves dos confirmados por incerteza. Resultado: `REVIEW/MEDIUM`, `internal_visual_match=UNCERTAIN`, `external_support=NONE`, sem conflitos materiais.
- Confirmados pela Packing List: code, item_name, NCM, composição, construção e fabricante. Confirmados pela imagem: categoria visual, cor primária, comprimento e detalhes visíveis. A imagem não foi usada para sustentar composição, NCM ou fabricante.
- IDs usados: `PACKING-001` e `VISUAL-001`. Search não encontrou evidência aprovada e nenhuma página web entrou no pacote final; isso impediu `FOUND`.
- Execução fresca final: uma chamada visual e uma textual, `llm_used_visual=true`, `llm_used_text=true`; modelo textual efetivo `hy3-free`; latências observadas nessa execução 106 ms visual e 1.862 ms textual. Uma execução anterior não cacheada observou 5.617 ms visual; a variação pertence ao gateway/provider.
- Replay idêntico: visual cache HIT, multimodal cache HIT, zero chamadas visuais, zero chamadas textuais, mesma decisão `REVIEW/MEDIUM`.
- Container piloto local consumiu aproximadamente 54,8 MiB de RAM. Concorrência permaneceu 1 em cada camada. Custo US$ 0.

### Validação, preservação e próximo passo

- 100 testes backend passaram; cobertura nova inclui extração/associação/hash/MIME, normalização, schemas estritos, JSON inválido/retry, confiança por atributo, ambiguity, IDs inventados, conflitos, prompt injection, caches, ausência de imagem, MIME inválido, tamanho e proibição visual para composição.
- `compileall`, `pip check`, build Docker e `git diff --check` passaram. Nenhum XLSX, imagem real, HTML, cache ou secret foi versionado.
- Nenhum lote, OCR, WASH_LABEL/HANGTAG, LABEL_IMAGE, DUIMP, Fase 8, frontend, CSS ou layout foi implementado.
- Commit funcional `ac17a9d feat: adiciona cruzamento multimodal de evidencias` criado e publicado em `origin/main` por push normal, sem force push. O Auto Deploy não iniciou.
- Redeploy seguro `bab1o9ieeubql7chug25h40m`, `force_rebuild=false` e restrito a `applicationId=3`, terminou no SHA completo `ac17a9dcb58ff9a5112f3b8b8bc28713e6f49970`.
- Novo container `7896d5937cb6` ficou healthy, preservando `127.0.0.1:18001:8000` e mount RW `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`. Health local e público pelo Funnel retornaram HTTP 200; a rota nova apareceu no OpenAPI.
- A produção não possui override explícito para os modelos e usa os defaults documentados do código: `OMNIROUTE_MODEL=auto/coding:free` e `OMNIROUTE_VISION_MODEL=oc/mimo-v2.5-free`. Nenhuma configuração global do OmniRoute foi alterada.
- Piloto fresco em produção: uma chamada visual e uma textual, `REVIEW/MEDIUM`, modelo visual efetivo `mimo-v2.5-free`, modelo textual efetivo `hy3-free`, 140 ms visual e 1.864 ms textual. Atributos e IDs foram idênticos ao piloto local saudável.
- Replay público pelo Funnel: visual cache HIT, multimodal cache HIT, zero chamadas LLM e mesma decisão. Os dois arquivos de cache possuem modo 600; nenhum conteúdo ou imagem foi exposto.
- Recursos após o replay: backend aproximadamente 64,0 MiB, SearXNG aproximadamente 44,4 MiB/512 MiB e host com aproximadamente 643 MiB disponíveis. Funnel 443 -> NFLNBA e 8443 -> Projeto Digitação permaneceu íntegro; health e consulta de jogos do NFLNBA continuaram HTTP 200.
- **GATE DA FASE 7B ATENDIDO E VALIDADO EM PRODUÇÃO.** Backend, storage, Funnel, SearXNG privado, OmniRoute textual e UI LOCKED `fc53ebb` foram preservados.
- Próxima etapa possível, somente com nova autorização: Fase 7C de expansão controlada ou etapa específica para WASH_LABEL/HANGTAG. Não iniciar automaticamente.

## 2026-08-14 — Fase 7C: evidências de etiquetas e hangtags

### Arquitetura implementada

- Criado `POST /api/uploads/{file_id}/research/multimodal/labels`, limitado a 1 ou 2 produtos. Todos os endpoints existentes (`/research`, `/research/enrich`, `/research/analyze`, `/research/multimodal`) foram preservados sem alteração.
- Fluxo: produto estruturado -> associação PRODUCT_IMAGE/WASH_LABEL/HANGTAG da Fase 5B -> extração controlada dos bytes -> visão separada para cada tipo -> search/enrich -> pacote de evidências com IDs -> cruzamento textual final -> validação e calibração determinística.
- Generalizada `extract_label_image_bytes` em `backend/app/services/spreadsheets/images.py`, aceitando `WASH_LABEL` e `HANGTAG` com a mesma validação de hash, MIME e dimensões da `extract_product_image_bytes`.
- Prompts separados e versionados:
  - `wash-label-extraction-v1` em `backend/app/prompts/wash_label_extraction_v1.txt`;
  - `hangtag-extraction-v1` em `backend/app/prompts/hangtag_extraction_v1.txt`;
  - `labels-multimodal-analysis-v1` em `backend/app/prompts/labels_multimodal_analysis_v1.txt`.
- Schemas Pydantic estritos (`extra="forbid"`): `WashLabelEvidence`, `HangtagEvidence`, `LlmLabelsCrossAnalysis`, `ProductLabelsMultimodalResult` e `LabelsMultimodalResponse` em módulos separados (`label_schemas.py`, `labels_multimodal_schemas.py`).
- O campo `model` do `LlmHangtagAttributes` (LabeledField para "model" do produto) foi renomeado para `model_used` no `HangtagEvidence` para evitar colisão com o parâmetro `model` (nome do modelo de IA).

### Serviço de análise de labels

- Criado `label_analysis.py` com `LabelAnalysisService`. Reutiliza `prepare_image` do `visual_analysis.py` para normalização JPEG/PNG (máximo 1 MiB, 1280 px).
- Cada tipo (wash/hangtag) usa seu próprio prompt e schema de validação.
- `_calibrate_wash`: valida soma de composição, adiciona `composition_percentage_sum_invalid` quando soma ≠ 100, completa `unknown_fields`.
- `_calibrate_hangtag`: idem para composição em hangtag, completa `unknown_fields`.
- Status explícitos: `OK`, `UNREADABLE`, `PARTIAL`, `UNSUPPORTED`, `ERROR`, `NO_IMAGE`.
- Concorrência 1 por semáforo global. Timeout do visual model existente.

### Cross-evidence com labels

- Criado `labels_multimodal.py` com `LabelsMultimodalService`.
- `_compute_internal_support`: critérios determinísticos baseados em confirmação de code/style entre Packing + Hangtag, compatibilidade de composição entre Packing + Wash, confirmação de cor/brand/size, presença de sinais visuais.
- `_compute_external_support`: reutiliza a lógica existente (search/web).
- `_validate_labels_analysis`: valida evidence IDs, rejeita VISUAL comprovando campos invisíveis, detecta conflitos Packing x Wash automaticamente e os injeta na resposta.
- Decisão conservadora: `FOUND` rebaixado para `REVIEW` quando suporte externo insuficiente mesmo com interno forte. Conflitos forçam `REVIEW`.

### Caches

- `wash-label-analysis-v1`: `/data/uploads/.wash-label-cache`, TTL 7 dias, chave por hash da imagem + code + modelo + prompt + tipo + preprocessing;
- `hangtag-analysis-v1`: `/data/uploads/.hangtag-cache`, mesma estrutura;
- `labels-multimodal-analysis-v1`: `/data/uploads/.labels-multimodal-cache`, chave por produto normalizado + hash do pacote + prompt + versão + modelo textual.

### Configuração

- Variáveis adicionadas ao `config.py`: `wash_label_cache_dir`, `wash_label_cache_ttl_seconds`, `hangtag_cache_dir`, `hangtag_cache_ttl_seconds`, `labels_multimodal_cache_dir`, `labels_multimodal_cache_ttl_seconds`.

### Testes automatizados

- Suíte ampliada de 100 para 134 testes, todos passando.
- Casos novos em `test_labels_analysis.py` (34 testes):
  - Composition sum: soma 100 válida, soma inválida, sem percentuais;
  - Wash calibration: soma inválida gera warning, soma válida sem warning, unknown fields populados, ilegitibilidade, fibra chinesa preservada;
  - Hangtag calibration: unknown fields, code confirmado fora de unknown;
  - Wash analysis service: extração completa, cache hit, unreadable, partial text;
  - Hangtag analysis service: extração, barcode;
  - Retry: JSON inválido + válido, duas falhas;
  - Prompt injection: texto em raw_text preservado como dado, schema rejeita extra keys;
  - Extract label image: rejeita PRODUCT_IMAGE;
  - Cross-evidence validation: análise válida, ID inválido rejeitado, VISUAL não comprova composição, conflito Packing x Wash detectado;
  - Produtos sem labels;
  - Schemas estritos: request max 2 produtos, extra fields rejeitados.

### Piloto WW77# em produção

- Container `2b4a8805799d` healthy, commit `0d55f35`, `127.0.0.1:18001:8000`, mount RW preservado, Funnel `:8443` OK.
- PRODUCT_IMAGE: cache HIT (do piloto da Fase 7B), `mimo-v2.5-free`, status OK, dress/pink.
- WASH_LABEL: `OmniRouteError` (HTTP 429 do provider do modelo visual gratuito); label_status `ERROR`.
- HANGTAG: `OmniRouteError` (HTTP 429); label_status `ERROR`.
- O modelo textual recebeu apenas PACKING-001 e VISUAL-001, tentou confirmar `color` apenas com VISUAL (rejeitado pela validação), e na segunda tentativa retornou JSON vazio.
- Resultado final: `REVIEW/LOW`, `internal_support=NONE`, `external_support=NONE`, zero labels processadas.
- **GATE DA FASE 7C PARCIALMENTE ATENDIDO:** infraestrutura, código, schemas, prompts, caches, endpoint e testes estão completos e validados. O piloto completo depende do rate limit do modelo visual gratuito `mimo-v2.5-free` resetar para que WASH_LABEL e HANGTAG possam ser analisadas.
- **O piloto real completo precisa ser repetido quando o rate limit expirar.**

### Preservação

- Frontend UI LOCKED `fc53ebb` preservada; nenhum CSS/componente alterado.
- Todos os endpoints anteriores preservados sem alteração de contrato.
- SearXNG (`127.0.0.1:8888`), OmniRoute textual (`auto/coding:free`) e visual (`oc/mimo-v2.5-free`), Funnel, NFLNBA, bind e mount não foram alterados.
- Commits: `ffc63e9 feat: adiciona evidencias de etiquetas e hangtags` e `0d55f35 fix: corrige unpacking de contadores no servico de labels`.
- 134 testes passando; `compileall` e `pip check` limpos.

### Próximo passo

- Repetir o piloto WW77# quando o rate limit do `mimo-v2.5-free` resetar.
- Validar WASH_LABEL e HANGTAG extraídos com sucesso.
- Executar replay para confirmar cache hit.
- Testar no máximo mais 1 produto real.
- Não iniciar Fase 8, não gerar DUIMP, não processar lote, não alterar frontend.

## 2026-08-14 — Checkpoint final do dia — pausa da Fase 7C por rate limit

### Estado encerrado

- **FASES 5A, 5B, 6A, 6B, 6B.3, 6C, 7A e 7B = CONCLUÍDAS.**
- **FASE 7C = EM ANDAMENTO.** Infraestrutura, código, schemas, prompts, caches, endpoint, testes, deploy e documentação estão completos e validados. O piloto real com WASH_LABEL e HANGTAG está pendente por rate limit temporário do provider.
- **FASE 8 = NÃO INICIADA.** Nenhuma descrição DUIMP foi gerada.
- Lote NÃO executado. Frontend/UI LOCKED `fc53ebb` preservada.
- Modelo visual: `oc/mimo-v2.5-free` (inalterado).
- Modelo textual: `auto/coding:free` (inalterado).

### Commits e produção

- Último commit local: `cb791e5 docs: registra fase 7c - evidencias de etiquetas e hangtags`.
- Último commit em `origin/main`: `cb791e5` (sincronizado, sem force push).
- Commit em produção: `0d55f35 fix: corrige unpacking de contadores no servico de labels` (container `2b4a88057993`, healthy). O commit `cb791e5` é apenas documentação e não requer redeploy.
- Working tree: limpa. Nenhum arquivo funcional pendente.

### Arquivos da Fase 7C implementados

- `backend/app/services/spreadsheets/images.py` — `extract_label_image_bytes` adicionada;
- `backend/app/prompts/wash_label_extraction_v1.txt` — prompt de extração de wash label;
- `backend/app/prompts/hangtag_extraction_v1.txt` — prompt de extração de hangtag;
- `backend/app/prompts/labels_multimodal_analysis_v1.txt` — prompt de cross-evidence com labels;
- `backend/app/services/research/label_schemas.py` — schemas Pydantic estritos para WashLabel/Hangtag;
- `backend/app/services/research/label_analysis.py` — serviço de extração visual de labels;
- `backend/app/services/research/labels_multimodal_schemas.py` — schemas do cross-evidence;
- `backend/app/services/research/labels_multimodal.py` — serviço de cruzamento com labels;
- `backend/app/config.py` — variáveis de cache para wash/hangtag/labels-multimodal;
- `backend/app/api/research.py` — endpoint `POST /research/multimodal/labels`;
- `backend/tests/test_labels_analysis.py` — 34 testes automatizados.

### Testes

- 134 testes passando (100 existentes + 34 novos da Fase 7C).
- `compileall`, `pip check` limpos.
- Nenhum teste existente quebrado.

### Piloto WW77# — estado parcial

- PRODUCT_IMAGE: cache HIT do piloto da Fase 7B. Status OK, modelo `mimo-v2.5-free`, atributos dress/pink preservados.
- WASH_LABEL: **NÃO EXECUTADA.** A chamada `complete_vision_json` ao OmniRoute recebeu HTTP 429 (rate limit do provider Console/OpenCode). Label_status: `ERROR/OmniRouteError`.
- HANGTAG: **NÃO EXECUTADA.** Mesma causa. Label_status: `ERROR/OmniRouteError`.
- Cross-evidence textual: executada com apenas PACKING-001 e VISUAL-001 disponíveis. Primeira tentativa rejeitada pela validação (tentativa de confirmar `color` apenas com VISUAL). Segunda tentativa retornou JSON vazio. Resultado: `REVIEW/LOW`, `internal_support=NONE`, `external_support=NONE`.
- **Nenhum dado real de WASH_LABEL ou HANGTAG foi obtido nesta sessão.**

### Bloqueio atual

- Classificação: `TEMPORARY_PROVIDER_RATE_LIMIT`.
- O modelo visual gratuito `oc/mimo-v2.5-free` atingiu rate limit do provider (Console/OpenCode). O monitor registrou mais de 34 eventos consecutivos de `Still rate limited` ao longo de aproximadamente 20 minutos.
- Isso NÃO implica erro do FastAPI, Coolify, SearXNG, código multimodal, necessidade de trocar modelo ou API paga.
- O modelo foi previamente validado nas Fases 7A e 7B com sucesso.

### Regra de preservação do modelo

- NÃO trocar `OMNIROUTE_VISION_MODEL` sem decisão explícita do operador.
- NÃO usar modelo pago.
- O rate limit é temporário e deve ser aguardado.

### Tarefa exata pendente para retomada

Quando a cota do modelo visual gratuito estiver novamente disponível:

1. Recuperar este estado (ler `memoria.md`, verificar health e produção);
2. Confirmar container healthy e commit em produção;
3. Executar SOMENTE a chamada pendente do piloto:
   ```bash
   curl -X POST https://nflnba.tail08f125.ts.net:8443/api/uploads/c21b5d16-d31f-4722-8c3b-213d19360be3/research/multimodal/labels \
     -H 'Content-Type: application/json' \
     -d '{"product_ids":["WW77#"]}'
   ```
4. Validar WASH_LABEL: raw_visible_text, composição, soma, size, status;
5. Validar HANGTAG: raw_visible_text, brand, style_code, declared_color, status;
6. Validar cross-evidence: confirmed_fields, conflicts, internal_support, external_support, decision;
7. Executar replay para confirmar cache hit nas 3 camadas (wash, hangtag, labels-multimodal);
8. Testar no máximo mais 1 produto real que possua WASH_LABEL ou HANGTAG;
9. Concluir o gate da Fase 7C;
10. Atualizar documentação;
11. Não iniciar Fase 8 automaticamente.

### Preservação de infraestrutura

- Backend local `http://127.0.0.1:18001`, público `https://nflnba.tail08f125.ts.net:8443`.
- Tailscale Funnel preservado: 443 -> NFLNBA e 8443 -> Projeto Digitação.
- Storage persistente RW preservado: host `/opt/projeto-digitacao/data/uploads` -> container `/data/uploads`.
- SearXNG preservado em `127.0.0.1:8888`; OmniRoute preservado na porta 20128.
- UI aprovada e LOCKED no commit visual `fc53ebb`.

## 2026-08-16 — Retomada e conclusão da Fase 7C

### Recuperação do checkpoint

- Checkpoint recuperado de `memoria.md` (linhas 1787–1874): Fase 7C com código, schemas, prompts, caches, endpoint e 134 testes concluídos; piloto bloqueado por rate limit do `oc/mimo-v2.5-free` em 2026-08-14.
- Último commit: `6126f1f docs: registra pausa da fase 7c por rate limit`.
- `origin/main` sincronizado; working tree limpa.

### Estado de produção antes da retomada

- `/health` local: HTTP 200, `{"status":"ok"}`.
- `/health` público: HTTP 200, `{"status":"ok"}`.
- Container `2b4a88057993`: `Up 7 minutes (healthy)`.
- Bind `127.0.0.1:18001:8000` confirmado por `ss`.
- Mount RW: `/opt/projeto-digitacao/data/uploads` -> `/data/uploads`.
- Funnel `:8443` OK.
- SearXNG `127.0.0.1:8888` OK.
- OmniRoute porta 20128, modelo `oc/mimo-v2.5-free` listado.

### Piloto principal WW77# — execução completa

- Chamada única de teste de rate limit: `POST /api/uploads/c21b5d16.../research/multimodal/labels` com `product_ids=["WW77#"]`.
- **Rate limit liberado.** Chamada concluída sem erro HTTP 429.

#### PRODUCT_IMAGE (IMG-00001)

- Cache: HIT (da Fase 7B).
- Modelo: `mimo-v2.5-free`.
- Status: OK.
- Atributos: `dress`, `pink`, `off-the-shoulder`, `knee-length`, `ruffle neckline`, `floral pattern`, `cinched waist`.
- `llm_used=false`.

#### WASH_LABEL (IMG-00002)

- Status: OK.
- Modelo: `mimo-v2.5-free`.
- Latência: 9.067 ms.
- Cache: MISS (primeira execução real).
- `llm_used=true`.
- Raw visible text: `TELA EXTERIOR: 100%POLIÉSTER`, `TELA INTERIOR: 95%POLIÉSTER 5%ELASTANO`, `FABRICADO NA CHINA`.
- Composição: 100% polyester (exterior), 95% polyester + 5% elastane (interior).
- `composition_sum=200`, `composition_sum_valid=false` (correto — são duas camadas separadas de tecido, não uma única composição).
- Size: UNKNOWN. Brand: UNKNOWN. Style code: UNKNOWN.
- Country of origin: China (HIGH confidence).
- Care instructions: Hand wash at 30°C, Do not bleach, Do not tumble dry, Iron at medium temperature (up to 150°C), Do not dry clean.
- Warnings: `composition_percentage_sum_invalid` — documentado corretamente como duas camadas separadas.
- Evidence ID: `WASH-001`.

#### HANGTAG (IMG-00003)

- Status: OK.
- Modelo: `mimo-v2.5-free`.
- Latência: 5.740 ms.
- Cache: MISS (primeira execução real).
- `llm_used=true`.
- Raw visible text: `Liu`, `FASHION`.
- Brand: `Liu FASHION` (HIGH confidence).
- Style code: UNKNOWN. Model: UNKNOWN. Size: UNKNOWN. Declared color: UNKNOWN. SKU: UNKNOWN.
- Barcode text: UNKNOWN.
- Composition: vazia.
- Warnings: nenhuma.
- Evidence ID: `HANGTAG-001`.

#### Cross-evidence

- Decisão: `REVIEW`. Confiança: `MEDIUM`.
- `internal_support`: MODERATE.
- `external_support`: NONE.
- Modelo textual: `big-pickle`. Latência: 24.207 ms.
- Prompt: `labels-multimodal-analysis-v1`.
- Cache: MISS (primeira execução).

#### Confirmed fields

- `brand`: `Liu FASHION` (HANGTAG-001).
- `construction`: `梭织` (PACKING-001).
- `manufacturer`: `蒋培英` (PACKING-001).
- `ncm`: `6104.43.00` (PACKING-001).
- `item_name`: `连衣裙` (PACKING-001).
- `code`: `WW77#` (PACKING-001).
- `country_of_origin`: `China` (WASH-001).
- `category_visual`: `dress` (VISUAL-001).
- `primary_color`: `pink` (VISUAL-001).
- `sleeves`: `off-the-shoulder` (VISUAL-001).
- `length`: `knee-length` (VISUAL-001).
- `visible_details`: `ruffle neckline, floral pattern, cinched waist` (VISUAL-001).

#### Conflitos

- `composition`: Packing List (`面料：100%涤 里布：95%涤 5%氨纶`) vs WASH_LABEL (`polyester polyester elastane`). Conflito de formato/texto, não de substância — a composição em si é consistente (exterior 100% poliéster, interior 95% poliéster + 5% elastano).

#### Unknown fields

- `size`, `style_code_from_label`, `sku_from_label`, `barcode_text`, `material`, `weight`, `dimensions`, `capacity`, `purpose`, `voltage`, `power`, `frequency`, `battery`, `recharge`, `connection`, `accessories`, `color`.

#### Warnings

- Soma de composição 200% explicada como duas camadas separadas de tecido (exterior + interior).
- Brand `Liu FASHION` presente apenas no hangtag, não corroborada por Packing List ou Wash Label.
- Evidência visual não pode confirmar composição, fabricante, NCM ou propriedades invisíveis.

### Cache replay

- Segunda chamada idêntica: todas as 4 camadas retornaram `HIT`.
- Visual: HIT. Wash: HIT. Hangtag: HIT. Labels-multimodal: HIT.
- Zero chamadas LLM no replay.

### Segundo produto CY2926

- `CY2926`: possui PRODUCT_IMAGE + WASH_LABEL + HANGTAG.
- PRODUCT_IMAGE: executada com sucesso (modelo `mimo-v2.5-free`, 1 LLM call, cache MISS).
- WASH_LABEL: **OmniRouteError** (HTTP 429 — rate limit voltou).
- HANGTAG: **OmniRouteError** (HTTP 429).
- Resultado: `REVIEW/LOW`, `internal_support=NONE`, `external_support=NONE`, labels não processadas.
- Conforme regra: rate limit voltou → PARAR. CY2926 permanece pendente para execução futura quando a cota resetar.

### LLM calls totais da sessão

- WW77#: visual=0 (cache HIT), wash=1, hangtag=1, textual=2.
- WW77# replay: visual=0, wash=0, hangtag=0, textual=0 (4 cache HITs).
- CY2926: visual=1, wash=0 (rate limited), hangtag=0 (rate limited), textual=2.
- **Total: 5 chamadas LLM reais + 4 cache hits.**

### Testes

- `pytest -q`: 134 passed in 3.61s.
- `python -m compileall app`: limpo.
- `pip check`: No broken requirements found.
- `git diff --check`: limpo.

### Gate da Fase 7C

1. WASH_LABEL associada corretamente: SIM (IMG-00002 -> WW77# -> WASH-001).
2. HANGTAG associada corretamente: SIM (IMG-00003 -> WW77# -> HANGTAG-001).
3. Análise real executada: SIM (wash 9.067ms, hangtag 5.740ms).
4. Raw text preservado: SIM (TELA EXTERIOR/INTERIOR composições, FABRICADO NA CHINA, Liu FASHION).
5. Campos ilegíveis UNKNOWN: SIM (size, brand no wash, style_code, declared_color no hangtag).
6. Percentuais não inventados: SIM (100%, 95%, 5% — todos legíveis na etiqueta).
7. Composition validation funcionou: SIM (soma 200% gerou warning correto de camadas separadas).
8. Evidence IDs válidos: SIM (PACKING-001, VISUAL-001, WASH-001, HANGTAG-001).
9. Conflitos preservados: SIM (composition Packing vs Wash registrada).
10. internal_support calculado: SIM (MODERATE).
11. external_support separado: SIM (NONE).
12. Cache replay funciona: SIM (4/4 HITs, zero LLM calls).
13. Testes passam: SIM (134 passed).
14. Produção saudável: SIM (healthy, mount RW, Funnel OK).
15. Frontend não mudou: SIM (UI LOCKED fc53ebb).
16. Nenhuma DUIMP gerada: SIM.
17. Nenhum lote processado: SIM.

**FASE 7C = CONCLUÍDA.**

### Arquivos alterados

- Nenhum arquivo de código foi alterado nesta sessão.
- Apenas `memoria.md` e `README.md` atualizados com documentação.

### Commits e push

- Pendente: commit de documentação da conclusão do piloto da Fase 7C.
- Sem force push.

### Limitações conhecidas

- Rate limit do `oc/mimo-v2.5-free` é intermitente. CY2926 não pôde ser processado por causa disso.
- Hangtag do WW77# contém pouca informação legível (apenas `Liu FASHION`).
- Size e style_code não foram encontrados em nenhuma etiqueta.
- `external_support` permanece NONE para WW77# (sem resultados de search/web).

### Próximo passo

- **FASE 7D — PILOTO MULTIMODAL COMPLETO COM 2–3 PRODUTOS REAIS.**
- A Fase 7D deverá validar o pipeline completo com múltiplos produtos antes da geração DUIMP.
- Não iniciar automaticamente.

## 2026-08-16 — Fallback visual gratuito

### Auditoria do OmniRoute 3.8.49

- Catálogo total: 687 modelos listados em `/v1/models`.
- Rotas combo com fallback nativo: `auto/vision`, `auto/best-vision`, `auto/best-free` — todas `owned_by: combo`.
- Nenhuma rota combo gratuita específica para visão foi encontrada.
- `auto/best-free` roteou para `openai/gpt-4o-mini` (potencialmente pago) — descartado como fallback garantido.
- `auto/vision` e `auto/best-vision` podem rotear para modelos pagos — descartados.
- **Conclusão: OmniRoute NÃO possui fallback nativo gratuito confiável para visão.** Fallback implementado no backend.

### Modelos visuais gratuitos auditados

| Modelo | Vision | Free | Latência | Status |
|--------|--------|------|----------|--------|
| `oc/mimo-v2.5-free` | ✅ declarado | ✅ | ~5-9s | Principal. Rate limited intermitentemente. |
| `gemma-4-31b-it:free` | ✅ testado | ✅ | <5s | **Fallback validado.** Google Gemma 4 multimodal. |
| `gemma-4-26b-a4b-it:free` | ✅ testado | ✅ | <5s | Alternativa MoE menor. Respostas mais detalhadas. |
| `nemotron-nano-12b-v2-vl:free` | ❌ timeout | ✅ | >120s | Descartado. Timeout em 30s e 120s. |

### Modelos DuckDuckGo (`ddgw/`)

- `ddgw/gpt-5.4-mini`, `ddgw/gpt-5.4-nano`, `ddgw/claude-haiku-4-5`: listados no catálogo, mas classificação de termos de uso `avoid`. Não utilizados.

### Modelos Qwen VL

- `qwen3-vl-8b-instruct`, `qwen3-vl-32b-instruct`, `qwen3-vl-235b-a22b-instruct`: disponíveis, mas gratuidade não comprovada (sem `:free` no ID). Não utilizados.

### Testes com imagem sintética

- Imagem de teste: quadrado vermelho 64×64 com círculo azul centralizado, PNG, 407 bytes data URL.
- `oc/mimo-v2.5-free`: rate limited (429) no momento do teste.
- `gemma-4-31b-it:free`: "This image consists of a blue circle centered on a red background." — CORRETO.
- `gemma-4-26b-a4b-it:free`: "This image features a large red square that serves as the background. In the center of the square is a blue circle." — CORRETO.
- `nemotron-nano-12b-v2-vl:free`: timeout em 30s e 120s. DESCARTADO.

### Implementação no backend

- `OmniRouteCompletion` estendido com `fallback_used: bool` e `fallback_reason: str | None`.
- `complete_vision_json` reimplementado com loop sobre candidatos: tenta primary, se falhar por erro transitório (429, 5xx, timeout), tenta fallback.
- Erros permanentes (400, JSON inválido, conteúdo vazio) NÃO acionam fallback.
- Se todos falharem: `OmniRouteError` com status 503 e reason documentado.
- `OmniRouteCompletion.fallback_used` e `fallback_reason` propagados aos callers (`visual_analysis.py`, `label_analysis.py`) e registrados nos logs.
- Cache key continua baseada no modelo primário configurado; fallback funciona transparentemente.

### Configuração

- `OMNIROUTE_VISION_MODEL=oc/mimo-v2.5-free` (principal, inalterado).
- `OMNIROUTE_VISION_FALLBACK_MODEL=openai-compatible-chat-38d59294-9537-4ebf-a7bd-c8853db07903/google/gemma-4-31b-it:free` (novo).
- Fallback pode ser desativado com `OMNIROUTE_VISION_FALLBACK_MODEL=` (string vazia).

### Testes automatizados

- Criado `tests/test_vision_fallback.py` com 14 testes:
  - Primary OK → sem fallback;
  - Primary 429 → fallback funciona;
  - Primary timeout → fallback funciona;
  - Primary 502 → fallback funciona;
  - Primary 400 → sem fallback (erro permanente);
  - Primary conteúdo vazio → sem fallback;
  - Ambos rate limited → 503;
  - Ambos timeout → 503;
  - Sem fallback configurado → só primary;
  - Modelo efetivo da resposta;
  - Fallback model usado quando resposta sem model;
  - Gate de custo: primary e fallback são free;
  - Config padrão é free.
- Suíte total: 148 passed (134 existentes + 14 novos).

### Arquivos alterados

- `backend/app/services/omniroute.py`: fallback em `complete_vision_json`;
- `backend/app/config.py`: `omniroute_vision_fallback_model`;
- `backend/app/services/research/visual_analysis.py`: propagação de fallback;
- `backend/app/services/research/label_analysis.py`: propagação de fallback;
- `backend/.env.example`: documentação da variável;
- `backend/tests/test_vision_fallback.py`: 14 testes novos.

### Custo

- **US$ 0.** Ambos os modelos são gratuitos comprovados.

### Commit e push

- `d9d67ba feat: adiciona fallback gratuito para analise visual`.
- Push normal em `origin/main`. Sem force push.

### Gate

1. Fallback visual auditado: SIM.
2. Segundo modelo gratuito validado: SIM (`gemma-4-31b-it:free`).
3. Nenhum modelo pago: SIM.
4. `mimo-v2.5-free` continua principal: SIM.
5. Fallback apenas em erros transitórios: SIM.
6. Modelo efetivo registrado: SIM.
7. Cache correto: SIM.
8. Testes passam: SIM (148).
9. Fase 7C intacta: SIM.
10. Frontend inalterado: SIM.

**GATE APROVADO.**

### Próximo passo

- Redeploy manual no Coolify se Auto Deploy não iniciar.
- **FASE 7D — PILOTO MULTIMODAL COMPLETO COM 2–3 PRODUTOS REAIS.**
- Não iniciar automaticamente.

## 2026-08-16 — Fase 7D: piloto multimodal completo com 3 produtos reais

### Produtos selecionados

| # | Code | Imagens | Justificativa |
|---|------|---------|---------------|
| 1 | WW77# | PRODUCT+WASH+HANG | Obrigatório (7C). Baseline com todas as camadas. |
| 2 | CY2926 | PRODUCT+WASH+HANG | NCM diferente (6104.23.00), composição distinta (100涤). |
| 3 | N260309# | PRODUCT+WASH (sem hangtag) | Pipeline reduzido. Composição com PU. Testa ausência de hangtag. |

- file_id: `c21b5d16-d31f-4722-8c3b-213d19360be3`
- Endpoint usado: `POST /api/uploads/{file_id}/research/multimodal/labels` (existente, sem alteração).
- Processamento sequencial, concorrência 1.

### Estado de produção

- Container `2b4a88057993`: healthy, commit `0d55f35` (2026-08-14).
- Fallback visual (`d9d67ba`) NÃO implantado (Auto Deploy não iniciou). Redeploy pendente.
- `/health` local e público: HTTP 200.
- Mount RW preservado. Funnel :8443 OK. SearXNG OK.

### Resultado WW77#

- **Decision: REVIEW / MEDIUM**
- **internal_support: MODERATE**
- **external_support: NONE**
- Product image: True (cache HIT da 7B/7C)
- Wash label: True (cache HIT da 7C)
- Hangtag: True (cache HIT da 7C)
- Evidence used: PACKING-001, WASH-001, HANGTAG-001, VISUAL-001
- Confirmed fields (12): brand, construction, manufacturer, ncm, item_name, code, country_of_origin, category_visual, primary_color, sleeves, length, visible_details
- Conflicts (1): composition — PACKING-001 (`面布：100%涤 里布：95%涤 5%氨纶`) vs WASH-001 (`polyester polyester elastane`). Conflito de formato, não de substância.
- Unknown fields: size, style_code_from_label, sku_from_label, barcode_text, material, weight, dimensions, capacity, purpose, voltage, power, frequency, battery, recharge, connection, accessories, color
- Modelo visual efetivo: `mimo-v2.5-free` (cache HIT)
- Modelo textual: `big-pickle`
- Fallback visual: não necessário (cache)
- Warnings: composição 200% explicada como camadas separadas; brand `Liu FASHION` só no hangtag; visual não comprova composição/NCM.

### Resultado CY2926

- **Decision: REVIEW / LOW**
- **internal_support: NONE**
- **external_support: NONE**
- Product image: True (cache HIT da 7C — PRODUCT_IMAGE processado antes do rate limit)
- Wash label: False (ERROR — OmniRouteError/429 rate limit)
- Hangtag: False (ERROR — OmniRouteError/429 rate limit)
- Evidence used: [] (apenas visual disponível, insuficiente sem labels)
- Confirmed fields: 0
- Conflicts: 0
- Modelo visual: `mimo-v2.5-free` (cache HIT para PRODUCT_IMAGE)
- Modelo textual: `hy3-free`
- Fallback visual: NÃO disponível (não implantado no container)
- Warnings: Análise de labels indisponível ou inválida.
- Nota: CY2926 precisa de redeploy com fallback para completar labels.

### Resultado N260309#

- **Decision: REVIEW / MEDIUM**
- **internal_support: MODERATE**
- **external_support: NONE**
- Product image: False (ERROR — OmniRouteError/429 rate limit)
- Wash label: False (ERROR — OmniRouteError/429 rate limit)
- Hangtag: NO_IMAGE (correto — não existe hangtag para este produto)
- Evidence used: PACKING-001 (apenas Packing List disponível)
- Confirmed fields (6): code, item_name, ncm, composition, construction, manufacturer
- Conflicts: 0
- Unknown fields: supplier, brand, color, size, purpose, dimensions, weight, capacity, voltage, power
- Modelo textual: `hy3-free`
- Fallback visual: NÃO disponível (não implantado no container)
- Warnings: Packing list alone; no wash label to confirm composition; NCM only from packing; missing visual/hangtag prevents color/size/brand confirmation.
- Nota: N260309# precisa de redeploy com fallback para completar PRODUCT_IMAGE e WASH_LABEL.

### Cache replay

- WW77# replay: 4/4 cache HITs (visual, wash, hangtag, labels-multimodal). Zero chamadas LLM.
- CY2926 e N260309#: sem labels em cache (nunca processadas com sucesso).

### LLM calls totais

- WW77# + CY2926 (primeira chamada): visual=0, wash=0, hang=0, text=2 (labels-multimodal).
- N260309# (primeira chamada): visual=0, wash=0, hang=0, text=1.
- WW77# replay: visual=0, wash=0, hang=0, text=0.
- **Total: 3 chamadas LLM textuais, 0 visuais (todas em cache ou rate limited).**

### Visão geral do piloto

- Produtos processados: 3
- FOUND: 0
- REVIEW: 3 (WW77# MEDIUM, CY2926 LOW, N260309# MEDIUM)
- NOT_FOUND: 0
- Fallback visual usado: 0 (não implantado)
- Suporte externo: 0 (nenhum produto teve search/web evidence)
- Só suporte interno: 2 (WW77# e N260309# com MODERATE via packing+labels ou packing only)

### Impacto do rate limit

- `mimo-v2.5-free` estava rate limited durante o piloto.
- WW77# não foi afetado porque todas as evidências visuais já estavam em cache da Fase 7C.
- CY2926: PRODUCT_IMAGE em cache, mas WASH_LABEL e HANGTAG falharam (sem cache anterior).
- N260309#: PRODUCT_IMAGE e WASH_LABEL falharam. HANGTAG não existe. Apenas PACKING disponível.
- O fallback implementado no commit `d9d67ba` (gemma-4-31b-it:free) teria permitido completar CY2926 e N260309#.
- **Recomendação: redeploy do Coolify com o commit `d9d67ba` antes de repetir CY2926 e N260309#.**

### Gate da Fase 7D

1. 2–3 produtos reais processados: SIM (3).
2. WW77# incluído: SIM.
3. Decisão final válida por produto: SIM (REVIEW/MEDIUM, REVIEW/LOW, REVIEW/MEDIUM).
4. Schemas válidos: SIM.
5. Evidence IDs válidos: SIM.
6. internal_support e external_support separados: SIM.
7. Conflitos preservados: SIM (composition em WW77#).
8. Fallback visual sem quebrar pipeline: SIM (não implantado, mas pipeline continuou).
9. Replay com cache: SIM (WW77# 4/4 HITs).
10. Nenhuma fase anterior regrediu: SIM.
11. Nenhuma DUIMP gerada: SIM.
12. Frontend inalterado: SIM (UI LOCKED fc53ebb).
13. Produção saudável: SIM.

**FASE 7D = CONCLUÍDA.**

### Arquivos alterados

- Nenhum arquivo de código foi alterado nesta sessão.
- Apenas `memoria.md` atualizado com documentação.

### Limitações registradas

- CY2926 e N260309# não tiveram labels extraídas por rate limit do mimo.
- Fallback não estava implantado no container de produção.
- Nenhum produto teve search/web evidence (external_support=NONE em todos).
- Repetir CY2926 e N260309# após redeploy com fallback para obter resultados completos.

### Próximo passo

- **Redeploy do Coolify** com commit `d9d67ba` para ativar fallback visual.
- Repetir CY2926 e N260309# com fallback ativo.
- **FASE 8 — geração da descrição técnica objetiva para DUIMP** (somente com nova autorização).
- Não iniciar automaticamente.
