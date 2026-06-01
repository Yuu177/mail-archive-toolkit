# IMAP 邮件 EML 归档工具

这个工具通过 IMAP 拉取邮箱邮件，把每封邮件保存成原始 `.eml` 文件，然后可以继续转换成 `.html` 和方便搜索的 `.txt` 文件。

只要邮箱服务支持 IMAP，配置正确的服务器、端口、账号和客户端密码后就可以使用。下面的默认配置使用腾讯企业邮箱作为示例。

使用的库：

- `IMAPClient`：连接 IMAP 并拉取邮件。
- `mail-parser`：解析 `.eml` 邮件。
- `html2text`：把 HTML 转成文本。
- `tqdm`：显示进度条。

## 配置

复制 `config.example.json` 为 `config.json`，然后填写邮箱账号和客户端密码：

```json
{
  "email": "your.name@example.com",
  "password": "your-client-password",
  "imap_host": "imap.exmail.qq.com",
  "imap_port": 993,
  "mailboxes": ["INBOX"],
  "output_dir": "mail_archive/raw"
}
```

需要在邮箱后台开启 IMAP/SMTP，腾讯企业邮箱通常使用 `imap.exmail.qq.com:993`。

腾讯企业邮箱网页版设置参考：

1. 进入 `设置` -> `客户端设置`。
2. 在 `开启服务` 里开启 `IMAP/SMTP服务`。
3. 在 `收取选项` 里勾选 `收取“我的文件夹”`，收取范围选择 `全部邮件`。

`mailboxes` 填 IMAP 邮箱文件夹名。脚本启动时会打印所有文件夹和邮件数量。

示例：

```json
"mailboxes": ["INBOX", "Sent Messages", "其他文件夹/gitlab"]
```

## 安装依赖

**当前依赖版本只在 Python 3.8 环境下测试过**

```bash
pip install -r requirements.txt
```

## 拉取 EML

拉取配置文件里所有邮箱文件夹的全部邮件：

```bash
python3 sync_eml.py
```

测试时只拉取每个配置文件夹最近 20 封：

```bash
python3 sync_eml.py --limit 20
```

输出目录：

```text
mail_archive/raw/<邮箱文件夹名>/
```

例如：

```text
mail_archive/raw/INBOX/
mail_archive/raw/其他文件夹/gitlab/
```

本地路径会保留邮箱文件夹名中的 `/` 层级。为了避免写到归档目录之外，文件夹名不能是绝对路径，路径段也不能是空、`.` 或 `..`。

重复运行时，已经存在的 `UID.eml` 文件会跳过。

## 转换成 HTML

把归档好的 `.eml` 转成 `.html`，尽量保留邮件原始 HTML 内容。内联图片和附件会保存到 `mail_archive/html/.mail-archive-assets/`。转换 TXT 时不会读取这个资源目录。

```bash
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html
```

输出目录：

```text
mail_archive/html/<邮箱文件夹名>/
```

例如：

```text
mail_archive/html/INBOX/
mail_archive/html/其他文件夹/gitlab/
```

脚本会递归读取 input 目录下所有邮箱子目录，并保留相对目录结构。
如果目标 `.html` 已存在，默认会跳过；需要重新生成时加 `--force`：

```bash
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html --force
```

## 转换成 TXT

把 `.html` 转成适合搜索的 `.txt`：

```bash
python3 html_to_text.py --input mail_archive/html --output mail_archive/text
```

如果目标 `.txt` 已存在，默认会跳过；需要重新生成时加 `--force`。

输出目录：

```text
mail_archive/text/<邮箱文件夹名>/
```

例如：

```text
mail_archive/text/INBOX/
mail_archive/text/其他文件夹/gitlab/
```

搜索文本：

```bash
rg "关键词" mail_archive/text
```

## 推荐流程

测试最近 10 封：

```bash
python3 sync_eml.py --limit 10
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html
python3 html_to_text.py --input mail_archive/html --output mail_archive/text
```

全量处理：

```bash
python3 sync_eml.py
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html
python3 html_to_text.py --input mail_archive/html --output mail_archive/text
```

也可以直接运行：

```bash
sh run.sh
```
