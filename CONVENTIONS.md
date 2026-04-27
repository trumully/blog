# Conventions

## File naming

### TS/JS

- Source files: `kebab-case.ts` or `kebab-case.mts` for ESM modules, configs, and scripts.
- Astro component/layout files: `PascalCase.astro` or `kebab-case.astro` for other Astro files.

## Naming

### TS/JS

- Types, interfaces, classes: `PascalCase`
- Functions, variables, properties: `camelCase`

## File layout

Higher-level functions should come before lower-level ones e.g. public before private. Ideally topologically sorted meaning each function appears before any it calls into.

## Formatting

Code formatting enforced automatically by project formatters.

- **TS/JS**: Oxfmt
- **Astro**: Oxfmt + Prettier

Run `npm run fmt` to apply formatting fixes.

## Spelling

**US English** spelling throughout all code, comments, and documentation.

## Error handling

Categorize errors into one of:

### User error

- Propagate by return value not exception
- Shown to user

### External error

E.g. network error, file system error.

- Propagate by return value, not exception. Means catching exceptions from external function calls.
- Retried if possible

### Unexpected error

Bugs caused by developer.

- Propagate by exception
- Caught at top level

## Content Schemas

**Blog post** (`src/blog/*.md`) frontmatter (all required):

```yaml
title: "Post Title"
date: 2026-01-01
description: "Short description"
tags: ["tag1", "tag2"]
```

**Comment** (`src/content/comments/*.md`) frontmatter:

```yaml
author: "Name" # required
date: 2026-01-01 # required
url: "https://..." # optional
```
