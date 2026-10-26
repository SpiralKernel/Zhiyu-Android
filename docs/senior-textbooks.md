# 高中数理教材与课程目录证据

本文记录 `app/data/senior_curriculum.json` 的教材来源、目录覆盖和版本证据。完整 PDF 原件保存在 git 忽略目录 `data/sources/textbooks/senior-private/`，不进入版本控制。

## 覆盖范围

- 数学：北京师范大学出版社体系的必修第一册、必修第二册、选择性必修第一册、选择性必修第二册。
- 物理：人民教育出版社体系的必修第一册、必修第二册、必修第三册、选择性必修第一册、选择性必修第二册、选择性必修第三册。
- 合计 10 册、50 个目录章目单元、100 条学习目标。JSON 字段贴合 `course_catalog.BOOKS`：每册含 `id/subject/grade/term/stage/edition/basis/scope_note/sources/units`，每目标含 `aliases/can_do/checks/prerequisites/practical/required/unit_id/book_id/subject`，并保留稳定 `book_id` 与 `source_sha256`。`grade` 和 `term` 暂为空值，表示不把册次假定为固定的年级或学期。
- 目录中列出的每章均进入 JSON 单元。教材的节、实验和应用主题用于具体化目标；目录的附录、索引、课题研究等非正文单元未另立知识单元。
- 课程目标是项目对目录主题的归纳；具体基础动作另拆为[基础题型清单](senior-foundations.md)，逐题复核后关联。

## 教材清单与校验信息

以下页数取自本地 PDF `pdfinfo`，SHA-256 对私有归档文件计算；归档副本与源文件逐字节复制。

| book_id | 教材 | 页数 | SHA-256 | 私有归档文件 | 目录单元（依教材顺序） |
|---|---|---:|---|---|---|
| `math-senior-compulsory-1` | 北师大版 数学必修第一册 | 249 | `7c5fdfef2b040204f59de56787e23e55debe3b44ffe4740b56caa2f8f9c29cd1` | `math-compulsory1.pdf` | 预备知识；函数；指数运算与指数函数；对数运算与对数函数；函数应用；统计；概率；数学建模活动（一） |
| `math-senior-compulsory-2` | 北师大版 数学必修第二册 | 281 | `7c948d1dc0e8926bab53235f3e0e87505dbe2c4c92110cf86ec77071ae91ba4c` | `math-compulsory2.pdf` | 三角函数；平面向量及其应用；数学建模活动（二）；三角恒等变换；复数；立体几何初步 |
| `math-senior-selective-1` | 北师大版 数学选择性必修第一册 | 272 | `12231be1b17b39e46b15df624bfb2e28749ab933c7da93274d7edcaf96377671` | `math-selective1.pdf` | 直线与圆；圆锥曲线；空间向量与立体几何；数学建模活动（三）；计数原理；概率；统计案例 |
| `math-senior-selective-2` | 北师大版 数学选择性必修第二册 | 112 | `1528c17c17e5a9bac6c4fd1745018ea8867ef9bfccb768f5847cfae93d860495` | `math-selective2.pdf` | 数列；导数及其应用 |
| `physics-senior-compulsory-1` | 人教版 物理必修第一册 | 135 | `2ea495d62e5e2a47f7399187d22f33541681562f2c084ccc830f64df1c501399` | `physics-compulsory1.pdf` | 运动的描述；匀变速直线运动的研究；相互作用——力；运动和力的关系 |
| `physics-senior-compulsory-2` | 人教版 物理必修第二册 | 115 | `64d6abd953bdbd2fb5a4deb9060079c3776f205edf01435e39f853e874b39f74` | `physics-compulsory2.pdf` | 抛体运动；圆周运动；万有引力与宇宙航行；机械能守恒定律 |
| `physics-senior-compulsory-3` | 人教版 物理必修第三册 | 144 | `912b1b318a811381c463fa6d933ebf9df91f09579baeb062e673a58db72f48bc` | `physics-compulsory3.pdf` | 静电场及其应用；静电场中的能量；电路及其应用；电能 能量守恒定律；电磁感应与电磁波初步 |
| `physics-senior-selective-1` | 人教版 物理选择性必修第一册 | 131 | `f9c98f34029eb41906fb7419e5b47e27b03eafd2d00d8522f496992187df4dc6` | `physics-selective1.pdf` | 动量守恒定律；机械振动；机械波；光 |
| `physics-senior-selective-2` | 人教版 物理选择性必修第二册 | 123 | `e7b8d61f3c98f1352f5d2d0ecf44d13f110ba3d833c68a4fd2e94b495166e81f` | `physics-selective2.pdf` | 安培力与洛伦兹力；电磁感应；交变电流；电磁振荡与电磁波；传感器 |
| `physics-senior-selective-3` | 人教版 物理选择性必修第三册 | 144 | `f330599ea414fddb103e57f4a72452478acda1641efb44e4fb35c38a10e0d8a7` | `physics-selective3.pdf` | 分子动理论；气体、固体和液体；热力学定律；原子结构和波粒二象性；原子核 |

原始来源目录均位于：

`/home/sink/网盘/夸克网盘/来自：分享/小学、初中、高中教材全部版本【电子课本】/2026秋高中【电子课本】-新教材/`

数学源文件位于 `全部版本 • 高中数学【电子课本】/北师大•高中数学【电子课本】/`；物理源文件位于 `全部版本 • 高中物理【电子课本】/人教版•高中物理【电子课本】/`。原始文件名统一带有“最新【版本】高中数学/物理•册名.pdf”。

## 目录核对方法与版本边界

- 数学四册为扫描版。目录页以 PDF 图像方式逐页查看：必修第一册 PDF 第 5–8 页，必修第二册第 5–8 页，选择性必修第一册第 5–8 页，选择性必修第二册第 5–6 页。页眉分别标出册名；选择性必修两册的页眉清楚写有“数学 选择性必修 第一册/第二册”。
- 物理目录页使用 `pdftotext -layout` 从各 PDF 前 8 页提取，并对照书内封面册名。三册必修目录连续列出第一至第十三章，三册选择性必修封面明确标示“选择性必修”，其目录分别列四、五、五章。
- 源目录名“2026秋高中【电子课本】-新教材”是网盘文件夹名，不足以证明教材版次年份。PDF 封面/版权页未能在本次核验中可靠确认具体版次和印次，因此 JSON 的 `edition` 只记录出版社版本体系（北师大版、人教版），不猜测年份、版次或印次。
- 物理源文件的文件名使用“选修第一/二/三册”，但各册内部封面与版权页均标“选择性必修”，因此按新教材选择性必修归档和建模，不以旧选修书名替代。
- 当前所需教材在本地全部找到，无需以网上 PDF 补缺。
- 2026-10-16基础题扩充时重看必修第一册PDF第8页，确认原目录登记遗漏第八章“数学建模活动（一）”。已追加稳定单元 `math-senior-compulsory-1:u8` 及两个目标；原有单元/题目ID不变。此前49章/98目标是旧登记范围，不能作为完整教材范围。
