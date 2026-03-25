# Mod 仓库格式

`mods.json` 用来描述安装器可读取的 Mod 列表与配置。

当前内置文件结构：

- `mods.json`：仓库索引
- `files/`：示例 Mod 二进制

如果你后续要继续扩展仓库，建议保持以下原则：

- `id` 用稳定英文标识，不要随显示名变化
- `file_name` 填最终落地到游戏目录中的 DLL 名
- `download.type` 目前支持 `file` 与 `repo_release`
- `file` 可直接填 `url` / `mirrors`，也兼容 `repo_path` 作为仓库内开发回退
- `repo_release` 需要提供 `repo` 与 `tag`，安装器会从 Release 资产中自动匹配 `.dll` 或 `.zip`
