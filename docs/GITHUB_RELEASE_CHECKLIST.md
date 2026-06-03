# GitHub Release Checklist

Before publishing this folder as a GitHub repository:

- Choose and add a license file, for example MIT, BSD-3-Clause, Apache-2.0, or a project-specific license.
- Review `examples/env.example` and update paths for the target machine.
- Confirm the E3SM version and machine assumptions in the `.csh` templates.
- Run the static checks:

```sh
python3 -m py_compile scripts/*.py scripts/workflows/*.py
for f in scripts/workflows/*.zsh; do zsh -n "$f"; done
node --check scripts/workflows/build_arm97_workflow_ppt.js
```

- Avoid committing generated model outputs, downloaded NetCDF histories, logs, cache files, or local `.env`.

This repository contains workflow code and configuration, not the full E3SM
source tree or external ARM97 inputdata.
