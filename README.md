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
  -> HTTPS Tailscale Funnel :8443
  -> http://127.0.0.1:18001
  -> FastAPI no Coolify (porta interna 8000)
  -> OmniRoute na rede local (192.168.15.112:20128)
  -> rota/modelo configurado por OMNIROUTE_MODEL
  -> resposta da IA
```

O navegador nunca deve acessar o OmniRoute diretamente. A chave, quando necessária, existe somente como variável do backend.

O frontend ainda não está publicado. Durante o desenvolvimento na HOMELAB, o navegador usa somente `/api/chat`; o Vite encaminha a requisição diretamente para o bind local estável do backend.

## Repositório

- GitHub: `https://github.com/bastosrafael/projeto-digitacao.git`
- Branch principal: `main`
- Diretório do backend: `/backend`
- Diretório do frontend: `/frontend`

## Frontend React + Vite

O frontend da Fase 4 é uma interface responsiva de chat feita com React 19 e Vite 8. Ele oferece mensagens de usuário e assistente, loading, erros amigáveis, envio com Enter, quebra de linha com Shift+Enter, limpeza da conversa, scroll automático e histórico no `localStorage` do navegador.

O botão de anexo é apenas visual nesta fase e informa que o upload de planilha será habilitado posteriormente.

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

O frontend ainda não foi publicado no Netlify. O endpoint público estável do backend já foi definido pelo Tailscale Funnel; a próxima fase ainda deve implementar o proxy de produção/Netlify Function, proteção da API e política de CORS. O proxy do Vite existe somente no servidor de desenvolvimento.

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
```

Se o OmniRoute local continuar sem exigir autenticação, `OMNIROUTE_API_KEY` pode permanecer vazia. A chave, quando necessária, deve existir somente como variável protegida do backend.

A imagem `projeto-digitacao-backend:local` também foi construída e validada localmente. Excel e frontend ainda não fazem parte do estado atual.

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
