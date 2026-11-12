# Vendored front-end assets

- Bootstrap 5.3.3 (`bootstrap-5.3.3/`), from https://registry.npmjs.org/bootstrap/-/bootstrap-5.3.3.tgz. MIT.
- Bootswatch Journal 5.3.3 (`bootswatch-5.3.3/journal/`), from https://registry.npmjs.org/bootswatch/-/bootswatch-5.3.3.tgz. MIT.

Changes from upstream:

- The `sourceMappingURL` comments are removed (no `.map` files are vendored).
- The Journal CSS had `@import url(https://fonts.googleapis.com/...News+Cycle...)`. It is removed, because the site loads nothing from a CDN. Headings use Journal's fallback font stack.

The Journal CSS is a full Bootstrap build with the theme, so `base.html` links only Journal and the Bootstrap JS bundle. The plain Bootstrap CSS stays here for reference.

## Added for the design system (U35)

- Bootstrap Icons 1.11.3 (`bootstrap-icons-1.11.3/`), from https://registry.npmjs.org/bootstrap-icons/-/bootstrap-icons-1.11.3.tgz. MIT. The full `bootstrap-icons.svg` sprite, unchanged.
- Source Serif 4 (`source-serif-4/`), Latin subset, weights 600 and 700, from https://registry.npmjs.org/@fontsource/source-serif-4/-/source-serif-4-5.2.5.tgz (`files/source-serif-4-latin-{600,700}-normal.woff2`). SIL Open Font License 1.1 (`OFL.txt`). Unchanged.
