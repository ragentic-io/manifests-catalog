## Application

- Id: `apps/<id>`
- Change: new draft / update / promote to published / remove

## Checklist

- [ ] `python tools/catalog.py validate` passes locally
- [ ] Only `apps/` and `CATALOG.md` changed (signed files are written by the Sign workflow)
- [ ] `provenance.url` points at the provider's own, current definition, and its license allows redistribution
- [ ] No real credentials anywhere in `manifest.json`
- [ ] For promotion to `published`: `setup.credential`, `setup.probe`, `rights` and the `a2ui` setup form are complete, and I tested the connection with my own account
