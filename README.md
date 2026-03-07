# blog

Personal blog built with [Astro](https://astro.build), deployed at https://trumully.github.io/blog.

## Comments
To comment on a post, submit a pull request here adding a YAML file to:

`src/content/comments/{post-name}/`

File name: `{unix-timestamp}-{your-name}.yaml`

```yaml
---
author: Your Name
date: 2026-03-07T10:00:00Z
content: |
  Your comment here.
url: https://your-website.com  # optional
---
```

## Contributions
This is my personal blog, but I am happy to accept contributions such as:
- Comments (as above)
- Corrections (typos, etc)