# 腾讯企业邮箱 EML 归档工具

这个工具通过 IMAP 拉取腾讯企业邮箱邮件，把每封邮件保存成原始 `.eml`
文件，然后可以继续转换成 `.html` 和可搜索的 `.txt` 文件。

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

如果网页登录密码不能用，需要在腾讯企业邮箱后台开启 IMAP/SMTP，并使用客户端密码或授权码。

`mailboxes` 填 IMAP 邮箱文件夹名。脚本启动时会打印所有文件夹、邮件数量和对应的本地目录名。

示例：

```json
"mailboxes": ["INBOX", "Sent Messages", "其他文件夹/gitlab"]
```

## 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

如果本地用户包导致 `pip` 异常，可以用：

```bash
PYTHONNOUSERSITE=1 python3 -m pip install --user -r requirements.txt
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
mail_archive/raw/<邮箱文件夹名__短hash>/
```

例如：

```text
mail_archive/raw/INBOX__dc063b45c9/
```

目录名后面的短 hash 用来避免不同 IMAP 文件夹映射到同一个本地目录，例如 `A/B` 和 `A_B`。

重复运行时，已经存在的 `UID.eml` 文件会跳过。

## 转换成 HTML

把归档好的 `.eml` 转成 `.html`，尽量保留邮件原始 HTML 内容。内联图片和附件会保存到 `assets/` 目录。

```bash
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html
```

输出目录：

```text
mail_archive/html/<邮箱文件夹名__短hash>/
```

脚本会读取 input 目录下所有邮箱子目录。

## 转换成 TXT

把 `.html` 转成适合搜索的 `.txt`：

```bash
python3 html_to_text.py --input mail_archive/html --output mail_archive/text
```

输出目录：

```text
mail_archive/text/<邮箱文件夹名__短hash>/
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
