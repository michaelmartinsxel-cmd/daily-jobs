# daily-jobs

Painel de vagas de finanças atualizado todo dia às 9h (horário de Brasília), publicado no GitHub Pages.
Usa só ferramentas gratuitas: GitHub Actions + GitHub Pages + APIs públicas de vagas.

## Como funciona

GitHub Actions (todo dia 12:00 UTC = 9:00 BRT)
- lê o config.yml
- busca vagas no JSearch e no Adzuna (Brasil / São Paulo) e no We Work Remotely
- descarta vagas de nível fora do perfil (pelo título) e com experiência acima do limite
- calcula o % de match com as competências do perfil
- gera public/index.html e publica no GitHub Pages

## Configuração (uma vez)

1. Settings > Pages > Source: GitHub Actions
2. Settings > Secrets and variables > Actions > New repository secret:

| Secret | Onde conseguir |
|---|---|
| JSEARCH_API_KEY | rapidapi.com (API "JSearch", plano gratuito) |
| ADZUNA_APP_ID | developer.adzuna.com (cadastro gratuito) |
| ADZUNA_APP_KEY | developer.adzuna.com |

3. Actions > Daily Job Search > Run workflow (primeira execução manual)

O painel fica em https://SEU_USUARIO.github.io/NOME_DO_REPOSITORIO

## Ajustes

Tudo é feito no config.yml: cidade, termos de busca, competências e níveis descartados.
