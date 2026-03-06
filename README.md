# blog

Personal blog built with [Astro](https://astro.build), deployed at https://trumully.github.io/blog.

## Features

- Paginated post listing (5 per page)
- Tag-based filtering
- Archive view grouped by year/month
- RSS feed & sitemap
- Light/dark theme toggle
- Terminal-inspired design (JetBrains Mono)

## Getting Started

Requires Node 24 (managed via [Volta](https://volta.sh)).

```sh
npm install
npm run dev  # localhost:4321
```

## Commands

| Command                | Action                   |
| ---------------------- | ------------------------ |
| `npm run dev`          | Start dev server         |
| `npm run build`        | Build to `./dist/`       |
| `npm run preview`      | Preview production build |
| `npm run lint`         | Run ESLint               |
| `npm run lint:fix`     | Fix ESLint issues        |
| `npm run prettier`     | Check formatting         |
| `npm run prettier:fix` | Fix formatting           |

## Deployment

Deployed to Netlify. Pushing to `main` triggers a production deploy; PRs get a preview URL posted as a comment.
