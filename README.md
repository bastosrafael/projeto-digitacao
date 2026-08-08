# Projeto Digitação

Aplicação para conversar com IA e, em fases futuras, enriquecer planilhas de produtos. O estado atual implementa o backend das fases 1 a 3: health check, chat por meio do OmniRoute local e execução validada em container Docker.

## Requisitos

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
- `OMNIROUTE_TIMEOUT_SECONDS`: timeout por tentativa.
- `OMNIROUTE_MAX_RETRIES`: quantidade de novas tentativas (0 a 5).
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

## Preparação para Coolify

O deploy ainda não foi realizado. Para uma configuração futura no Coolify:

- use `backend/` como contexto de build e `backend/Dockerfile` como Dockerfile;
- configure a porta interna da aplicação como `8000`;
- não publique a porta 8000 diretamente no host;
- deixe o proxy/reverse proxy do Coolify encaminhar o domínio para a porta interna 8000 do container;
- configure o health check HTTP com o caminho `/health`;
- não altere o comando de inicialização da imagem, salvo necessidade comprovada.

Configure as seguintes variáveis no painel do Coolify, sem colocá-las no repositório:

```dotenv
OMNIROUTE_BASE_URL=http://192.168.15.112:20128/v1
OMNIROUTE_API_KEY=<segredo-configurado-no-coolify>
OMNIROUTE_MODEL=auto/coding:free
```

Se o OmniRoute local continuar sem exigir autenticação, `OMNIROUTE_API_KEY` pode permanecer vazia. A chave, quando necessária, deve existir somente como variável protegida do backend.

A imagem `projeto-digitacao-backend:local` foi construída e validada com `/health` e `/api/chat`. Excel, frontend e deploy não fazem parte do estado atual.
