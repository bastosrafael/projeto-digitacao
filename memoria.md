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
