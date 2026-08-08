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
