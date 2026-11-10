# 来源与第三方文件

硬件工程按本次用户需求生成。使用 KiCad 官方符号和封装，项目附有当前电源模式的 CH340C 派生符号；没有将库一致性等同于厂家电气核验。

- KiCad 库来源为当前安装的 KiCad 9 标准库，遵循 KiCad 库的 CC BY-SA 4.0 及其例外；相关许可入口：<https://www.kicad.org/libraries/license/>。
- 项目中的 3D 模型来自官方 KiCad packages3D，具体提交、哈希、许可和 CREDITS 保存在 `3dmodels/`。
- `scripts/usb_impedance.py` 移植了 KiCad 的 GPL-2.0-or-later 计算实现；保留脚本版权说明以及 `references/GPL-2.0-or-later.txt`，不将其许可简化为其他许可。
- `datasheets/` 的 WCH、Diodes、ST 文档保留各原作者版权，下载和镜像来源已记录。
- KiCad Happy 和 MCP Server 位于执行环境工具目录，未复制为本项目原创建模工具，也未放入制造文件包。
