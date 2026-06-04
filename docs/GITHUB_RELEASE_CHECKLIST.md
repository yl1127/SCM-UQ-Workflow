# GitHub Release Checklist

Before publishing this folder as a GitHub repository:

- Confirm the MIT `LICENSE` is still the intended license for this release.
- Review `examples/env.example` and update paths for the target machine.
- Confirm the E3SM version and machine assumptions in the `.csh` templates.
- Run the static checks:

```sh
python3 -m py_compile scripts/workflows/*.py
for f in scripts/workflows/*.zsh; do zsh -n "$f"; done
```

- Avoid committing generated model outputs, downloaded NetCDF histories, logs, cache files, or local `.env`.

This repository contains workflow code and configuration, not the full E3SM
source tree or external ARM97 inputdata.
