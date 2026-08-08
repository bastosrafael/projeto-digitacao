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
