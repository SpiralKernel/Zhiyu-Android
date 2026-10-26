# 安卓构建与发布

本仓库的 APK 完全在设备内运行，不是云端网页壳。`app/` 和 `web/` 都会打入 APK。

## 首次构建

1. 安装 Python 3.12、uv、完整 JDK 21（包含 javac）、Android SDK Platform/Build Tools 35，并接受 SDK 许可。
2. 根目录运行 `uv sync --python 3.12 --frozen`。
3. 运行 `uv run python scripts/fetch_android_assets.py`。下载当前发行版的签名题库，以及 ARM64 / x86_64 的 pydantic-core Android wheel；先验证全部签名和 SHA256，再写入忽略提交的构建缓存。
4. 运行 `uv run python scripts/prepare_android.py`，只准备代码、界面和内容种子，不读取本机学生数据库。
5. 在 `android/local.properties` 设置 `sdk.dir=你的SDK路径`（或设置 `ANDROID_HOME`），并设置 `JAVA_HOME` 指向 JDK21。
6. 运行 `cd android && ./gradlew :app:assembleDebug`，得到 ARM64 调试 APK。模拟器使用 `-PmobileAbi=x86_64`。

首次运行 Gradle Wrapper 会下载 Gradle8.13；Chaquopy17.1使用Python3.12。Maven 仓库包含阿里云镜像和官方回退，不改变依赖坐标。默认仅含ARM64，避免把模拟器运行库放入正式包。

如果已经手动下载全部Release构建附件，步骤3可改为：

```bash
uv run python scripts/fetch_android_assets.py --source-dir /path/to/attachments
```

`android/wheels/checksums.json` 固定原生 wheel 的摘要。构建来源、NDK版本及源码SHA见该目录README；可自行从官方源码交叉编译。不要用Linux桌面wheel代替Android扩展。

## 本地签名

正式维护者沿用原版签名；仓库、Release和题库下载服务均不存放私钥。`android/signing.properties`格式：

```properties
storeFile=/private/path/zhiyu.jks
storePassword=YOUR_LOCAL_PASSWORD
keyAlias=YOUR_ALIAS
keyPassword=YOUR_LOCAL_PASSWORD
```

该文件与JKS必须只保存在维护者本机。运行 `./gradlew :app:assembleRelease`。无签名配置时Gradle可能产出未签名包，不可当正式安装包发布。更换签名无法覆盖旧安装；应妥善备份原签名和密码。

## 当前发行版

`v0.8.1` / versionCode2，Android API24+，ARM64。Release APK对应本仓库的app、web与原生源文件；发布准备脚本、仓库名和文档另行做了可移植整理，不改变运行时行为。

Release包含：

- `Zhiyu-0.8.1-arm64.apk`：签名安装包。
- `SHA256SUMS.txt`：全部发行附件的摘要。
- `manifest.json`、`bank-2026102501.jsonl.gz`：RSA3072签名的内容种子，6,901题，不含账号与学习数据。
- 两个`pydantic_core-2.46.5-…android_24….whl`：从官方源码构建的Android原生依赖，分别供手机与模拟器使用。

APK签名证书SHA256为`0c05f5520cf8958ca16ce7615fa9e2c094201d74f01aa724126d0211b1801343`。首次发布APK SHA256为`0b2d618b41764ac00f66557954112d000534a6aa9d37931d2c59519c641c822e`。

## 题库发布

日常构建复用已验证的公开题包，不需要题库发布私钥。维护者发布新题包时，才用`build_mobile_content.py`从维护库导出内容并独立签名。APK固定公钥，安装更新只更新题库行，不覆盖学生数据库。不要把原始维护库或签名私钥作为Release附件。

已有APK继续使用独立静态HTTPS题库源；它与网页账号服务无关。仅在主动检查或下载题库时访问，不上传学生记录。

## 验证边界

独立源码605项通过，5项可选本地题源/PDF验真检查跳过；课程结构与标签规则照常验证，不分发私有教材PDF。原开发环境安卓版608项通过、1项跳过。Android35 x86_64模拟器已验证离线注册、主题/字号、头像裁剪、改名、相册、压感笔迹、PNG提交导出、重启草稿恢复与平板尺寸布局。图片提交UI验收使用明确标记的评阅响应桩，未付费调用模型。未在实体ARM平板上验证触控笔延迟和防误触。
