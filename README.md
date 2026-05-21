# Holo Cortex Zero

Holo Cortex Zero (HCZ) is a metacognitive multi-model agent platform.

> From the depth of the Holo Cortex, emergence starts at Zero
> 于全息智脑深处，涌现始于原点

This repository is the Docker-deployable source tree for HCZ. Full project
documentation is still being prepared; deployment guides are available in
[Chinese](README_DEPLOY.md) and [English](README_DEPLOY_EN.md).

## Quick Deploy

```bash
cp .env.share.example .env
bash holo-cortex-zero-main/docker/install.sh
```

Before first startup, edit `.env` and replace all `change_me_*` placeholder
passwords with strong private values.

For servers in mainland China, the install script can write build-time mirror
settings:

```bash
bash holo-cortex-zero-main/docker/install.sh cn
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).

Commercial use, modification, redistribution, and derivative works are allowed
under the license. Please retain attribution to the original HCZ source when
publishing modified, redistributed, or commercial versions.

Initial source attribution: Haicaizi / Holo Cortex Zero.
