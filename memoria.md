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
