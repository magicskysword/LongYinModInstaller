# 龙胤立志传 Mod 安装器

这是一个面向《龙胤立志传》的Mod安装器，使用 Python 构建，默认工作流如下：

- 自动读取 Steam 库与游戏目录，目标 AppID 固定为 `3202030`
- 自动把内置的 `MelonLoader.x64.zip` 解包到游戏目录，并把 `Dependencies.zip` 合并到 `MelonLoader/`
- 支持卸载 MelonLoader，会删除 `MelonLoader/` 和 `version.dll`
- 读取 Mod 仓库配置，从 GitHub Raw 或镜像站拉取 `mods.json`
- 支持两种 Mod 下载来源：`RepoRelease` 和 `File`
- `RepoRelease` 可配置 `latest` 或具体 tag，并按 GitHub Release 资产自动匹配 `dll/zip`
- `zip` 包会自动拆分：DLL 放入 `Mods`，`mod*` 数据目录放入 `Mods\\ModsOfLong`
- 安装动作会记录 manifest，卸载时按记录反向恢复
- 根据配置安装 Mod，并列出当前 `Mods` 目录里已经安装的 DLL

默认远程仓库基址为 `https://github.com/magicskysword/LongYinModInstaller`，程序会优先尝试读取该仓库 `master` 分支上的 Raw / jsDelivr `mod_repository/mods.json`；如果远程源不可用，则自动回退到仓库内置的本地 `mod_repository/mods.json`。

打包后的 `dist` 目录会额外包含这些与 `LongYinModInstaller.exe` 同级的文件：

- `catalog_sources.json`
- `catalog_sources.example.json`
- `mod_repository/`

其中 `catalog_sources.json` 是程序实际读取的镜像配置文件，本地回退仓库则来自同级目录下的 `mod_repository/mods.json`。

## 开发环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m longyin_mod_installer
```

## 打包

```powershell
.\build.ps1
```

打包结果默认输出到 `dist\LongYinModInstaller.exe`。

## Mod 仓库说明

仓库列表文件位于 `mod_repository/mods.json`，当前已经放入两个 GitHub Release 测试 Mod：

- `TheBookOfLong.dll`
- `LongYinTalentTweaks.dll`
