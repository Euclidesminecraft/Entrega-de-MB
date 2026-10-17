# Entrega-de-MB

MegaFlow — servidor HTTP leve que gere pedidos de entrega de "MB" (megabytes) vinculados a confirmações de pagamento M-Pesa. A interface administrativa é `dashboard.html` e a API é servida por `main.py`.

Principais arquivos

- `main.py` — servidor em Python (ThreadingHTTPServer) que guarda o estado em `megaflow.json` e serve `dashboard.html` na rota `/`.
- `dashboard.html` — painel web (frontend) usado para gerir pedidos e preços.
- `buildozer.spec` — configuração para empacotar a app no Android com Buildozer (bootstrap: `webview`).

Como executar localmente

1. Clone o repositório:

   git clone https://github.com/Euclidesminecraft/Entrega-de-MB.git
   cd Entrega-de-MB

2. Execute o servidor (requer Python 3.8+):

   python main.py

3. Abra no navegador em http://127.0.0.1:8000 — o dashboard pedirá o token que é escrito automaticamente em `megaflow.json` na primeira execução.

Variáveis de ambiente

- `ANDROID_PRIVATE` — se definida (caminho), o ficheiro `megaflow.json` será guardado nessa pasta em vez da pasta do projecto; útil para empacotar em Android onde a app tem um directório privado.

Empacotar para Android (resumo)

Este projecto usa o bootstrap `webview` de python-for-android: a app roda um servidor HTTP local e abre o `dashboard.html` numa WebView.

Exemplo mínimo com Buildozer (supondo Buildozer instalado):

1. Instalar dependências do sistema recomendadas pela documentação do Buildozer / p4a.
2. Ajustar `buildozer.spec` conforme necessário (já removi NDK/p4a.branch hardcoded para evitar incompatibilidades).
3. Empacotar:

   buildozer android debug

4. Instalar/rodar no dispositivo:

   buildozer android debug deploy run

Notas sobre segurança e operação

- O dashboard exige um token (`x-token`) para a maioria das rotas; o token é gerado na primeira execução e armazenado em `megaflow.json`.
- No Android, cuidado com exposição de rede e configurações de permissões; `buildozer.spec` define `android.permissions = INTERNET,WAKE_LOCK`.

O que eu já corrigi

- Removi definições hardcoded `android.ndk` e `p4a.branch` do `buildozer.spec` para evitar erros de compatibilidade com ambientes de build.

Quer que eu:

- Faça uma revisão automática do `main.py` e aplique pequenas melhorias (ex.: tratamento de erros, logging)?
- Crie um branch com testes ou exemplos de execução automatizada?

Se indicar o que prefere, eu faço os commits seguintes.