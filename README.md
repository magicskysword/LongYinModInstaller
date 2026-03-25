# 龙胤立志传 Mod 安装器

这是一个面向《龙胤立志传》的Mod安装器，使用 Python 构建，默认工作流如下：

- 自动读取 Steam 库与游戏目录，目标 AppID 固定为 `3202030`
- 自动把内置的 `MelonLoader.x64.zip` 解包到游戏目录
- 读取 Mod 仓库配置，从 GitHub Raw 或镜像站拉取 `mods.json`
- 支持两种 Mod 下载来源：`RepoRelease` 和 `File`
- `RepoRelease` 可配置 `latest` 或具体 tag，并按 GitHub Release 资产自动匹配 `dll/zip`
- `zip` 包会自动拆分：DLL 放入 `Mods`，`mod*` 数据目录放入 `Mods\\ModsOfLong`
- 安装动作会记录 manifest，卸载时按记录反向恢复
- 根据配置安装 Mod，并列出当前 `Mods` 目录里已经安装的 DLL

如果远程源未配置或不可用，程序会自动回退到仓库内置的本地 `mod_repository/mods.json`。

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

仓库列表文件位于 `mod_repository/mods.json`，当前已经放入两个本地示例 Mod：

- `TheBookOfLong.dll`
- `LongYinTalentTweaks.dll`
