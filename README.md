# daily-jobs

Dashboard de vagas atualizado todo dia às 9h (BRT), hospedado na Vercel.  
Funciona 100% com ferramentas gratuitas: **GitHub Actions + Vercel + APIs públicas**.  
Não usa Claude nem qualquer LLM.

## Como funciona

```
GitHub Actions (cron 12:00 UTC = 9:00 BRT)
  └── Python lê config.yml
        ├── Busca RSS (We Work Remotely) + APIs (JSearch, Adzuna)
        ├── Filtra por nível de experiência
        ├── Calcula Match % (stack do usuário vs requisitos)
        ├── Gera public/index.html via Jinja2
        └── Deploy na Vercel (URL fixa)
```

## Como usar após fork

### 1. Faça fork do repositório

### 2. Edite `config.yml`

Personalize seu perfil, stacks e keywords — é o único arquivo que você precisa editar.

### 3. Configure os GitHub Secrets

| Secret | Obrigatório | Descrição |
|---|---|---|
| `VERCEL_TOKEN` | ✅ | Token da Vercel (`vercel login` → Settings → Tokens) |
| `VERCEL_ORG_ID` | ✅ | ID da sua org/conta na Vercel |
| `VERCEL_PROJECT_ID` | ✅ | ID do projeto na Vercel (criado na 1ª execução) |
| `JSEARCH_API_KEY` | opcional | [RapidAPI — JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) |
| `ADZUNA_APP_ID` | opcional | [Adzuna API](https://developer.adzuna.com/) |
| `ADZUNA_APP_KEY` | opcional | [Adzuna API](https://developer.adzuna.com/) |

> **Como obter VERCEL_ORG_ID e VERCEL_PROJECT_ID:**  
> Rode `vercel link` na pasta do projeto localmente. Os IDs ficam em `.vercel/project.json`.

### 4. Rode o workflow manualmente pela primeira vez

Vá em **Actions → Daily Job Search → Run workflow**.  
Isso cria o projeto na Vercel e gera o primeiro dashboard.

### 5. Acesse a URL gerada

A URL aparece no log do workflow. O dashboard atualiza automaticamente todo dia às 9h BRT.

## Estrutura do projeto

```
daily-jobs/
├── config.yml                     ← edite este arquivo
├── vercel.json
├── public/
│   └── index.html                 ← gerado automaticamente
├── scripts/
│   └── job-search/
│       ├── search.py
│       ├── requirements.txt
│       └── template.html
└── .github/
    └── workflows/
        └── daily-job-search.yml
```

## Dashboard

- Cards ordenados por **match %** decrescente
- Badge **verde** ≥70% · **amarelo** 40-69% · **vermelho** <40%
- Tags de skills encontradas (verde) e faltantes (cinza)
- Filtros por modalidade (Remote / Hybrid) e por faixa de match
- CSS inline, responsivo, sem dependências
