# Contributing

## Branching

```
main      ← stable, deployed to production
develop   ← integration branch, deployed to staging
feature/<short-name>   e.g. feature/publishing-linkedin-video
fix/<short-name>
```

1. Branch from `develop`.
2. Commit small, focused changes with clear messages.
3. Push and open a pull request into `develop`. The PR template lists the Definition of
   Done.
4. CI must pass (backend checks and tests, frontend lint and build, Docker builds) and
   another developer reviews.
5. `develop` is merged into `main` for a release, then deployed
   ([docs/deployment.md](docs/deployment.md)).

## Local checks before a PR

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run   # commit migrations with model changes
python manage.py test

cd ../frontend
npm run lint
npm run build
```

## Conventions

- **Backend:**
  - Each feature lives in an app under `backend/apps/`.
  - Company-scoped views use `common.mixins.CompanyScopedMixin`, and `required_page` for
    client pages.
  - Long-running work goes in a Celery task, never in a request.
  - Record important actions with `log_activity()`.
  - New settings go in `config/settings/base.py` **and** `backend/.env.example`.
- **AI providers:** add a class implementing the modality's abstract provider, plus a
  branch in its factory and a row in `common/ai_config.py`.
- **Frontend:**
  - Pages in `src/pages`, API calls in `src/api`, shared UI in `src/components`.
  - Styles use the CSS tokens in `src/index.css`.
  - Tables that should collapse into cards on phones get `className="table table-stack"`
    and `data-label` on each `<td>`.
- **Tests:** every new endpoint or task gets tests under `backend/tests/<app>/`. Shared
  fixtures are in `tests/helpers.py`.
- **Docs:** after model or URL changes run `python manage.py generate_reference_docs`.
