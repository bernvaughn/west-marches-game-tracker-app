# Vendored front-end assets

- Bootstrap 5.3.3 (`bootstrap-5.3.3/`), from https://registry.npmjs.org/bootstrap/-/bootstrap-5.3.3.tgz. MIT.
- Bootswatch Journal 5.3.3 (`bootswatch-5.3.3/journal/`), from https://registry.npmjs.org/bootswatch/-/bootswatch-5.3.3.tgz. MIT.

Changes from upstream:

- The `sourceMappingURL` comments are removed (no `.map` files are vendored).
- The Journal CSS had `@import url(https://fonts.googleapis.com/...News+Cycle...)`. It is removed, because the site loads nothing from a CDN. Headings use Journal's fallback font stack.

The Journal CSS is a full Bootstrap build with the theme, so `base.html` links only Journal and the Bootstrap JS bundle. The plain Bootstrap CSS stays here for reference.
