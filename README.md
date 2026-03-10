# Sistema 1 — Gerenciador de Clientes (Natividade Digital)

CRM operacional para agência de tráfego pago com backend + frontend.

## Funcionalidades

- Dashboard dark com sidebar e KPIs: MRR, clientes ativos, inadimplentes, valor em atraso e churn.
- Cadastro e busca de clientes com perfil completo.
- Histórico de atendimentos (reunião, e-mail, ligação, WhatsApp).
- Tarefas com responsável, prioridade e conclusão.
- Funil de vendas em Kanban com drag & drop.
- Financeiro por cliente (mensalidades/status).

## Como rodar

### Linux / Mac

```bash
./start.sh
```

### Windows

```powershell
start.bat
```

Também funciona direto:

```bash
python3 app.py --port 5000
```

Abra no navegador: `http://127.0.0.1:5000`

## Se não abrir (ERR_CONNECTION_REFUSED)

Isso quase sempre significa que o servidor **não está rodando** ou a porta está ocupada.

1. Verifique se o terminal mostrou: `Servidor iniciado em http://127.0.0.1:5000`
2. Teste saúde da aplicação:
   ```bash
   curl http://127.0.0.1:5000/health
   ```
   Deve retornar: `{"status":"ok"}`
3. Se a porta 5000 estiver ocupada, rode em outra porta:
   ```bash
   python3 app.py --port 5001
   ```
   E abra `http://127.0.0.1:5001`

## Testes automatizados

```bash
python3 -m unittest tests/test_api.py
```
