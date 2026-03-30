# XJTLU 期末考试卷下载器

从 XJTLU ETD 系统批量下载期末考试卷 PDF 的桌面工具。

当前主线版本已经重构为 **PySide6 桌面 GUI + Playwright 下载内核**，目标是通过 GitHub Releases 提供可直接解压运行的便携程序包。

> 适用场景：先在程序内完成一次 ETD 登录，然后批量保存自己有权限访问的历年期末试卷 PDF。

## 问题背景 ❓

XJTLU ETD 系统只允许在线查看 PDF 试卷，**不提供直接下载功能**。这导致：
- 🔒 无法离线查看试卷，每次都要联网打开
- 📵 网络不稳定时反复加载浪费时间
- 📚 无法批量整理和存档历年真题
- 😤 想打印复习使用但不能保存本地

**本工具通过浏览器自动化技术，安全合法地解决这一问题！** ✨

---

## ⚖️ 重要法律声明与使用条款

**在使用本工具之前，请务必阅读并同意以下条款：**

### 允许的使用方式 ✅

本工具**仅供以下用途使用**：

1. **个人学习** - 下载论文供自己复习使用
2. **学术研究** - 用于课程学习或论文研究
3. **教学准备** - 教师准备教学材料
4. **非商业目的** - 完全用于教育，不涉及任何商业行为

### 严格禁止的使用方式 ❌

**以下行为严格禁止，违者需承担法律责任：**

1. **❌ 商业使用** - 不得用于任何商业目的、出售或盈利
2. **❌ 未授权分发** - 不得将下载的论文分享给他人或上传到网络
3. **❌ 公开发布** - 不得发布到社交媒体、网站、论坛等公开渠道
4. **❌ 泄露未发布内容** - 不得泄露当前年度未发布的考试题目
5. **❌ 修改或演绎** - 不得修改论文内容或创建衍生作品进行传播
6. **❌ 违反学校政策** - 必须遵守 XJTLU 关于考试论文的所有规定

### 知识产权保护 🔐

```
所有下载的论文属于西交利物浦大学及出题教师的知识产权，
受中国知识产权法保护。未经授权的分发或使用将构成侵权。
```

**根据 XJTLU 政策：**
> "用户不得对数据库中的任何材料进行修改、分发、发布、传送或创建衍生作品，
> 用于任何公开或商业目的。"

### 法律责任 ⚠️

**违反本条款可能导致：**

1. **民事责任** - 侵权赔偿
2. **刑事责任** - 根据中国《刑法》关于侵犯知识产权的规定
3. **学校处分** - 根据 XJTLU 学生行为准则
4. **证件处理** - 可能影响学位证书或成绩单

### 免责声明 📄

本工具开发者不对以下情况负责：

- 用户违反本使用条款导致的任何法律后果
- 用户因不当使用论文而被学校处分
- 用户的下载行为触发学校或网络安全监控
- 任何数据丢失或损坏

**使用本工具即表示你已完全理解并同意上述所有条款。**

---

## 功能特点

- 桌面 GUI：基于 PySide6，提供任务表格、日志面板和保存目录管理
- 批量下载：支持一次导入多条 PDF Viewer 链接并顺序处理
- 会话复用：程序自管 ETD 登录会话，避免每次都重新认证
- 交互优化：支持回车直接添加、剪贴板批量导入、重复链接自动跳过
- 文件安全：自动生成文件名并处理重名冲突
- 便携发布：支持通过 GitHub Releases 下载 Windows / macOS 便携包
- CLI 兼容：保留原有 CLI 和旧入口兼容层，方便逐步迁移

## 快速开始

### Windows

```bash
# 方式 1：从 GitHub Releases 下载 zip，解压后直接运行 exe

# 方式 2：本地源码运行
install_win.bat
run_win.bat
```

### macOS

```bash
chmod +x install_mac.sh && ./install_mac.sh
./run_mac.sh
```

### GitHub Release 便携包

- 当前最新版本：[`v0.1.2`](https://github.com/kevinlasnh/xjtlu-final-paper-pdf-downloader/releases/tag/v0.1.2)
- Windows: `XJTLU-PDF-Downloader-win-x64.zip`
- macOS Intel: `XJTLU-PDF-Downloader-macos-x64.zip`
- macOS Apple Silicon: `XJTLU-PDF-Downloader-macos-arm64.zip`

> 最新 `v0.1.2` release 已上传三份便携包。Windows 已在本地验证源码运行和便携包启动；macOS x64 / arm64 已在 GitHub Actions 成功构建并上传，但尚未本地手工启动验收。

## 系统兼容性测试状态

| 平台 | 状态 | 说明 |
|------|------|------|
| **Windows** | ✅ 已测试 | 已验证源码运行、GUI 主流程和便携版 `.exe` 启动 |
| **macOS** | ✅ 已发布 | `v0.1.2` 已成功构建并发布 x64 / arm64 便携包，尚未本地手工启动验收 |
| **Linux** | ⚠️ 未作为主发布目标 | 保留源码运行脚本，但当前 release 不提供 Linux 便携包 |

> 当前主发布目标是 Windows 和 macOS 便携包。

## 手动安装

### 依赖要求

- Python 3.8+
- PySide6
- Playwright Chromium

### 安装步骤

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器
python -m playwright install chromium
```

## 使用方法

### GUI 版本

1. **启动程序**：运行对应平台脚本，或在源码模式下执行 `python desktop_app.py`

2. **登录 ETD**：
   - 点击“登录 ETD”
   - 在程序打开的浏览器窗口中完成一次登录
   - 关闭浏览器窗口后，程序会保存并复用这份登录会话

3. **添加任务**：
   - 将 PDF Viewer URL 粘贴到输入框中，直接按 `Enter`
   - 或点击“粘贴并添加”，从剪贴板中批量提取 URL
   - 任务会进入下方表格，重复链接会自动跳过

4. **设置保存位置**：
   - 点击 "📂 Browse..." 选择文件保存的目标文件夹

5. **开始下载**：
   - 点击“开始下载”
   - 程序将顺序处理任务列表中的全部链接并保存到指定目录
   - 日志面板会显示当前进度和失败原因

### CLI 命令行版本

**交互模式** (适合少量下载):
```bash
python3 cli.py
# 按提示输入 URL，输入 'q' 退出
```

**参数模式** (适合批量下载):
```bash
# 下载单个文件
python3 cli.py -u "https://etd.xjtlu.edu.cn/..."

# 批量下载多个文件
python3 cli.py -u "URL1" -u "URL2" -u "URL3"

# 指定输出目录
python3 cli.py -u "URL" -o ~/Downloads/papers

# 从文件读取 URL (每行一个)
python3 cli.py -f urls.txt
```

**更多选项**:
```bash
python3 cli.py --help
```

## URL 格式示例

程序支持如下格式的 URL：

```
https://etd.xjtlu.edu.cn/static/readonline/web/viewer.html?file=%2Fapi%2Fv1%2FFile%2FBrowserFile%3F...
```

## 项目结构

```
 xjtlu-final-paper-pdf-downloader/
├── desktop_app.py       # 新桌面 GUI 启动入口
├── cli.py               # CLI 命令行程序
├── main.py              # 旧 Tkinter GUI，保留作兼容/对照，不再作为主线入口
├── XJTLU_PDF_Downloader.spec  # 旧打包配置，当前主线使用 desktop_app.spec
├── src/xjtlu_downloader/
│   ├── app.py           # 桌面应用入口
│   ├── core/            # 服务层、路径、解析和文件工具
│   ├── domain/          # 领域模型和错误码
│   ├── infra/           # Playwright 下载与会话管理
│   └── ui/              # PySide6 主窗口
├── scripts/             # 便携包构建脚本
├── tests/               # 单元测试与 GUI 回归测试
├── downloader.py        # 旧下载入口兼容层
├── url_parser.py        # 旧 URL 解析兼容层
├── desktop_app.spec     # 当前桌面端便携打包配置
├── requirements.txt     # Python 依赖
└── README.md            # 说明文档
```

## 注意事项

⚠️ **重要提示**：

1. 需要先在 XJTLU ETD 网站上找到试卷，然后复制 PDF 查看器的 URL
2. 当前版本建议先在程序中点击“登录 ETD”，让程序保存自己的登录会话
3. URL 中包含时效性签名，请在有效期内及时下载
4. 下载请求的 IP 与登录上下文应保持一致
5. 本工具仅供 XJTLU 学生学习复习使用

## 如何获取试卷链接

1. 访问 [XJTLU ETD 系统](https://etd.xjtlu.edu.cn/)
2. 搜索你需要的课程期末试卷
3. 点击查看 PDF，在浏览器地址栏复制完整 URL
4. 将 URL 粘贴到本程序中下载

## 技术栈

- Python 3.8+
- PySide6 (桌面 GUI)
- Playwright (浏览器自动化)

## 遇到问题？

如果遇到个别复杂问题导致程序无法正常运行，请：

1. **查看错误提示**：程序会用中文详细说明问题原因和解决方案
2. **GitHub Issue**：在[项目 Issues](https://github.com/kevinlasnh/xjtlu-final-paper-pdf-downloader/issues)中留言描述问题
3. **询问 Agent**：你也可以询问 Codex / Claude Code 协助排查

遇到会话、403 或打开失败问题时，优先确认：
- 你是否已经点击“登录 ETD”并在程序浏览器中登录
- 当前 viewer URL 是否刚从 ETD 页面复制
- 登录网络环境与下载网络环境是否一致

## License

本项目采用 **AGPL-3.0 + Commercial License** 双重许可模式。

### 🟢 AGPL-3.0 许可（免费，适合开源/学生使用）

**你可以免费使用，前提是：**

✅ **允许的用途：**
- 个人学习和研究
- 教育和学术目的
- 非营利组织
- 开源项目（遵循 AGPL-3.0）

✅ **必须满足的条件：**
1. 保留所有版权声明
2. 公开你的源代码
3. 你的整个项目也必须采用 AGPL-3.0 许可
4. 记录你所做的修改
5. 如果在网络/服务器上运行，必须向用户提供源代码访问权

❌ **不能做的事：**
- 将代码用于闭源应用
- 提供付费服务而不公开源代码
- 在商业产品中使用而不遵循 AGPL-3.0

**详见：** [GNU AGPL-3.0 License](https://www.gnu.org/licenses/agpl-3.0.html)

---

### 🔵 商业许可（需要付费）

**如果你需要以下任一场景，必须获得商业许可证：**

❌ 在闭源应用中使用  
❌ 作为商业产品或服务的一部分  
❌ 提供付费 SaaS/云服务  
❌ 内部业务运营（超过 5 个用户）  
❌ 嵌入硬件或 IoT 设备出售  
❌ 作为付费软件包的一部分分发  

**商业许可证的优势：**
- ✨ 无需公开源代码
- ✨ 无 AGPL 约束
- ✨ 灵活集成到任何产品
- ✨ 完全的商业分发权
- ✨ 优先技术支持

**获取商业许可证：**

请联系开发者 **Pengkai Chen**：
- 📧 **邮箱**：Kevinlasnh@outlook.com  
- 📞 **电话**：+86 135-9049-3083  
- 💬 **GitHub**：在项目 issue 中标记 `commercial-license`

---

### 快速判断：你需要哪个许可证？

```
你的代码是否从这个项目中获利？
    ↓ YES → 需要商业许可证
    ↓ NO  → 继续看下面

你愿意开源整个项目吗（AGPL-3.0）？
    ↓ YES → 可以使用免费的 AGPL-3.0
    ↓ NO  → 需要商业许可证

还不确定？→ 联系 Kevinlasnh@outlook.com
```

---

### ⚠️ 重要警告

**不获取商业许可证进行商业使用将违反著作权法！** 可能导致：
- 立即中止许可
- 法律诉讼
- 赔偿损失和许可费
- 禁止令

详见项目 [LICENSE](LICENSE) 文件。
