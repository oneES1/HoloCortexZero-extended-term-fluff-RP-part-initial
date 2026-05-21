# 2026-04-01 Postgres 权限反复复发根因分析

## 结论
- 这类故障反复出现，不是因为修权脚本本身失效，而是因为当前部署结构仍允许 **非 Postgres 容器以 root 身份写整棵 `HCZ_DATA_DIR`**。
- `postgres_data` 与应用运行目录共处同一宿主 bind mount 根下，只要后续有任意 root 链路再次触碰该目录，`999:999` 就会漂移回 `root:root`。
- 之前的修复大多是在“把已经坏掉的权限修回来”，但没有消除这个结构性复发源，所以会反复。

## 本次实证
- 登录 500 根因：`could not open file "global/pg_filenode.map": Permission denied`
- 故障时宿主目录状态：
  - `postgres_data` -> `root:root`
  - `postgres_data/global/pg_filenode.map` -> `root:root`
- 运行中的 Postgres 进程身份：`999:999`
- 直接在 `hcz_postgres` 容器内执行 `chown 999:999` 可立即生效，说明容器内修权能力正常
- 主动执行一次 `hcz_permissions_init` 后，整棵 `postgres_data` 恢复为 `999:999`
- 恢复后 `psql select 1` 成功，说明数据库内容本身未损坏，故障就是 ownership 漂移

## 为什么会反复
- `holo_cortex_zero` 挂载了整棵 `${HCZ_DATA_DIR}` 到 `<CONTAINER_DATA_DIR>`，且容器默认 root 运行
- `hcz_napcat` 同样挂载了整棵 `${HCZ_DATA_DIR}` 到 `<CONTAINER_DATA_DIR>`，并以 `uid 0` 运行
- 因此 Postgres 数据目录并没有被隔离在“只有 Postgres 能写”的边界内
- 当前 `hcz_permissions_init` 与 `hcz_postgres` entrypoint 只在特定启动路径上修权：
  - `hcz_permissions_init`：`docker/init_runtime_permissions.sh`
  - `hcz_postgres`：`scripts/hcz_postgres_entrypoint.sh`
- 一旦权限漂移发生在这些修权步骤之后，或由其他 root 链路在运行中再次改坏，就会出现“上次修好了，这次又炸”

## 结构性根因
- 根因不是 PostgreSQL 本身，也不是单次偶发命令
- 根因是 **共享数据根目录的写权限边界设计过宽**：
  - 非 Postgres 服务不该拥有 `postgres_data` 的可写挂载
  - root 容器不该通过整棵 `<CONTAINER_DATA_DIR>` 间接覆盖数据库目录 ownership

## 根治方向
- 删除非 Postgres 容器对整棵 `${HCZ_DATA_DIR}` 的 rw 挂载，改为只挂必须子目录
- 明确禁止 `holo_cortex_zero`、`hcz_napcat` 触碰 `postgres_data`
- 若条件允许，将 Postgres 数据改为独立 volume 或独立宿主目录边界
- 修权脚本保留，但不再把它当作唯一防线；真正目标是让其他容器根本看不到 `postgres_data`

## 当前相关位置
- `docker-compose.yml`
- `holo-cortex-zero-main/docker/init_runtime_permissions.sh`
- `holo-cortex-zero-main/scripts/hcz_postgres_entrypoint.sh`
- `holo-cortex-zero-main/scripts/hcz_napcat_entrypoint.sh`
