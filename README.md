# Projeto Digitação

Aplicação para conversar com IA e, em fases futuras, enriquecer planilhas de produtos. O backend possui health check, chat por meio do OmniRoute local, deploy saudável no Coolify e acesso HTTPS pelo LocalTunnel. O código está publicado no GitHub.

## Arquitetura atual

```text
Internet
  -> HTTPS LocalTunnel (projeto-digitacao-api.loca.lt)
  -> container localtunnel-projeto-digitacao (rede Docker coolify)
  -> FastAPI no Coolify (porta interna 8000)
  -> OmniRoute na rede local (192.168.15.112:20128)
  -> rota/modelo configurado por OMNIROUTE_MODEL
  -> resposta da IA
```

O navegador nunca deve acessar o OmniRoute diretamente. A chave, quando necessária, existe somente como variável do backend.

## Repositório

- GitHub: `https://github.com/bastosrafael/projeto-digitacao.git`
- Branch principal: `main`
- Diretório do backend: `/backend`

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
8. configure a porta interna/exposta como `8000`, sem publicar `8000:8000` diretamente no host;
9. configure o health check HTTP com o caminho `/health`;
10. adicione as variáveis abaixo no painel, marcando a chave como secret quando aplicável;
11. salve e acione o deploy/redeploy;
12. confirme nos logs que o Uvicorn iniciou em `0.0.0.0:8000` e que o health check ficou saudável.

Resumo da configuração:

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

A imagem `projeto-digitacao-backend:local` também foi construída e validada localmente. Excel e frontend ainda não fazem parte do estado atual.

### Validação do deploy

Primeiro, confirme no Coolify que `/health` está saudável. Em seguida, use a URL real atribuída pelo operador:

```bash
export BACKEND_PUBLIC_URL='https://projeto-digitacao-api.loca.lt'
curl --fail --show-error "$BACKEND_PUBLIC_URL/health"
curl --fail --show-error -X POST "$BACKEND_PUBLIC_URL/api/chat" \
  -H 'Content-Type: application/json' \
  -H 'bypass-tunnel-reminder: true' \
  -d '{"message":"Responda apenas: deploy funcionando"}'
```

O segundo teste comprova o fluxo Coolify -> `192.168.15.112:20128` -> OmniRoute -> modelo. Se falhar, verifique primeiro os logs da aplicação e a conectividade de saída do container, sem alterar redes globais ou o OmniRoute.

### URL pública

- Backend deste projeto: `https://projeto-digitacao-api.loca.lt`.
- O container `localtunnel-projeto-digitacao` está na rede `coolify`, usa restart policy `unless-stopped` e encaminha HTTPS para a porta interna 8000 do backend.
- O header `bypass-tunnel-reminder: true` evita a página intermediária do LocalTunnel em chamadas de API.
- O container `localtunnel` original atende outro serviço na porta 3001 em `https://nflnba.loca.lt`. Ele não pertence ao Projeto Digitação e não deve ser alterado, removido ou reutilizado.

### Estabilidade do destino interno

O túnel do projeto aponta atualmente para o nome completo do container gerado pelo Coolify. Esse nome inclui um sufixo da implantação e pode mudar em um redeploy. Na inspeção da Fase 3C, somente o nome completo resolvia no DNS da rede `coolify`; o UUID base e o nome lógico indicado pelas labels não resolviam. Portanto, o risco de quebra após redeploy permanece.

Não foi encontrada uma alteração segura que pudesse ser aplicada sem recriar o túnel ou modificar o proxy/rede do Coolify. Até existir um alias persistente suportado pela configuração da aplicação, após cada redeploy o operador deve:

1. obter o novo nome com `docker ps --filter label=coolify.applicationId=3 --format '{{.Names}}'`;
2. testar do container do túnel se `http://NOVO_NOME:8000/health` retorna HTTP 200;
3. em uma janela de manutenção e com autorização explícita, recriar somente `localtunnel-projeto-digitacao` trocando `--local-host` pelo novo nome;
4. preservar `--network coolify`, `--restart unless-stopped`, `--port 8000` e `--subdomain projeto-digitacao-api`;
5. validar novamente `/health` e `/api/chat` externamente.

Não execute esse procedimento preventivamente enquanto o túnel estiver funcionando. Não foi localizada uma opção comprovada de alias persistente para o tipo de aplicação atual.

Uma solução definitiva suportada pelo modelo de rede do Coolify seria uma migração planejada para um único stack Docker Compose contendo serviços `backend` e `tunnel`. Dentro do mesmo stack, o túnel poderia usar `backend` como hostname estável. Essa migração deve ser feita manualmente pelo operador, sem redes customizadas nem portas publicadas no host, validada com um destino temporário e somente depois substituir a aplicação/túnel atuais. Ela não foi executada na Fase 3C. Referência: [Docker Compose Build Packs do Coolify](https://coolify.io/docs/applications/build-packs/docker-compose).
