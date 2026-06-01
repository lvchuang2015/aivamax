---
title: "JarveePro 导入账户中文教学｜Facebook 批量导入账号详细步骤"
source_url: "https://blog.jarveepro.com/knowledge/%E4%B8%AD%E6%96%87%E6%95%99%E7%A8%8B/JarveePro-%E5%AF%BC%E5%85%A5%E8%B4%A6%E6%88%B7%E4%B8%AD%E6%96%87%E6%95%99%E5%AD%A6Facebook-%E6%89%B9%E9%87%8F%E5%AF%BC%E5%85%A5%E8%B4%A6%E5%8F%B7%E8%AF%A6%E7%BB%86%E6%AD%A5%E9%AA%A4/5432"
category: "knowledge"
fetched_at: "2026-05-29T15:10:04+00:00"
status_code: 200
content_hash: "11090e48ba132a3a16a9662446aa9bf55884c415"
tags: ["jarveepro", "jarveepro/knowledge"]
---

# JarveePro 导入账户中文教学｜Facebook 批量导入账号详细步骤

Source: [https://blog.jarveepro.com/knowledge/%E4%B8%AD%E6%96%87%E6%95%99%E7%A8%8B/JarveePro-%E5%AF%BC%E5%85%A5%E8%B4%A6%E6%88%B7%E4%B8%AD%E6%96%87%E6%95%99%E5%AD%A6Facebook-%E6%89%B9%E9%87%8F%E5%AF%BC%E5%85%A5%E8%B4%A6%E5%8F%B7%E8%AF%A6%E7%BB%86%E6%AD%A5%E9%AA%A4/5432](https://blog.jarveepro.com/knowledge/%E4%B8%AD%E6%96%87%E6%95%99%E7%A8%8B/JarveePro-%E5%AF%BC%E5%85%A5%E8%B4%A6%E6%88%B7%E4%B8%AD%E6%96%87%E6%95%99%E5%AD%A6Facebook-%E6%89%B9%E9%87%8F%E5%AF%BC%E5%85%A5%E8%B4%A6%E5%8F%B7%E8%AF%A6%E7%BB%86%E6%AD%A5%E9%AA%A4/5432)

Category: `knowledge`

## Summary

（示例中“Column1/Column2/Column3/Column4”就是界面中表格最上方显示的列名）

## Headings

- JarveePro 导入账户中文教学｜Facebook 批量导入账号详细步骤
- 一、导入前先准备好文件（CSV / TXT）
- 二、界面操作（按顺序）
- 三、右侧每一项怎么填（中文逐项解释）
- 四、根据你截图的具体示例（直接对应的选择建议）
- 五、常见问题与解决办法（排查流程）
- 六、几个常用批量处理小技巧（Excel / 文本编辑）
- 七、快速对照表（常用映射）
- 八、示例

## Content

JarveePro 导入账户中文教学｜Facebook 批量导入账号详细步骤

2025-10-11

下面是一份面向不会看英文客户的中文一步步教学，按截图（左侧是表格预览，右侧是

Please mark the columns to import

区）来讲，包含示例与常见问题解决办法。

（示例中“Column1/Column2/Column3/Column4”就是界面中表格最上方显示的列名）

一、导入前先准备好文件（CSV / TXT）

每行一条账号记录，列与列之间用同一种分隔符（常见：逗号

或 制表符

\t

）。

推荐用 Excel 保存为

CSV UTF-8

，或者保存为 TXT（行分隔

\r\n

，列分隔

文件示例（每一行为一个账号）：

[email protected]

,abc123456,

,socks5://1.2.3.4:1080

1378617182343,abc123456,

上面两行分别是：

账号或邮箱,密码,辅助邮箱,代理

二、界面操作（按顺序）

打开

Import Account

左侧：选择

Category Type = Facebook

，并选好 Category Name（或新建）。

点击

Open File

，选你准备好的 CSV/TXT。界面会在中间显示表格预览（Column1, Column2...）。

如果显示不正确，检查左侧的

Row Separator

（一般

\r\n

）和

Column Separator

\t

），修改后点击重新载入（Reload txt file）。

右侧的 “Please mark the columns to import” 就是关键：对照中间表格，把每个下拉框选择成对应的列（Column1/2/3...）。

全选、确认无误后点击

OK

完成导入。

三、右侧每一项怎么填（中文逐项解释）

I only have cookies（仅有 cookies）

如果你的文件里只有 cookie 字符串（没有账号/密码），勾选这个选项。只需要在 Cookies 下拉里选择对应的列，导入时会把该列当作 cookie 导入。

Account / Email（账号 / 邮箱）

选择包含账号名或邮箱的列（例如

[email protected]

1378617182343

）。看中间预览哪一列是邮箱/账号就选哪列。

Password（密码）

选择包含密码的列（例如

abc123456

）。

Cookies（Cookies 字符串）

如果你有 cookie，请选择包含完整 cookie 字符串的列。

常见格式

c_user=xxx; xs=xxx; datr=xxx;

（即

name=value; name2=value2; ...

，整段作为一个字符串）。

Proxy（代理）

选择包含代理信息的列。

常用格式

socks5://IP:端口

IP:端口

用户名:密码@IP:端口

（带账号密码的代理）

如果你的文件里只有 IP 或端口，需要在导入前批量拼好格式（见后面批量处理方法）。

2FA（两步验证 / 验证码）

如果账号需要填写 2 步验证码并且你有固定的验证码列（例如人工采集到的临时代码），在这里选择该列。

Token（访问令牌）

有些服务用长字符串 token 登录（不常见）。如果你有，将那列映射到 Token。没有可不选。

四、根据你截图的具体示例（直接对应的选择建议）

截图里中间表格示例显示：

Column1 = 是账号ID

Column2 = 密码（

abc123456...

Column3 = 辅助邮箱（hotmail 等）

Column4 = 代理（

socks5://...

在右侧下拉应该这样选（针对该截图）

Account / Email →

Column1

（如果这列是你登录用的账号/ID）

Password →

Column2

Cookies → （如果没有 cookie 列则不选）

Proxy →

Column4

其他（2FA/Token）如果没有就不选

五、常见问题与解决办法（排查流程）

导入后失败 / 登录不成功

检查密码是否正确（有无多余空格）。

检查代理是否有效（尝试手动用一个账号连接测试）。

检查 cookie 是否完整（部分 cookie 丢失会导致登录失败）。

是否需要 2FA（需要验证码或手动验证）。

表格列对不上 / 列内容乱码

用记事本或 Excel 打开，确认列分隔符（逗号 vs 制表符）。

保存为

CSV UTF-8

，避免中文或特殊字符乱码。

代理格式不被识别

统一格式为

IP:端口

IP:端口:用户名:密码

如果代理信息分两列（IP 与 端口），用 Excel 拼接成一列再导出：例如在新列输入公式

=A2 & ":" & B2

我只有 cookies 没有密码

勾选右侧的

I only have cookies

，并把 Cookies 下拉选择成对应列，导入后 JarveePro 会用 cookie 登录（成功率视 cookie 有效性）。

保存文件/编码提示

Windows 用户：Excel -> “另存为” -> 选择

CSV UTF-8

，或用记事本存

UTF-8

编码。

文本编辑器（Notepad++）也可用来替换分隔符、去除 BOM。

六、几个常用批量处理小技巧（Excel / 文本编辑）

在 Excel 中把代理列拼接成

socks5://IP:端口

在新列写公式（假设 IP 在 A 列，端口在 B 列）：

="socks5://" & A2 & ":" & B2

，下拉填充后复制为值再导出 CSV。

把 cookie 放在单列

如果 cookie 数据跨多列，用

=A2 & "; " & B2 & "; " & C2

拼接成一列。

去除多余空格

Excel 用

TRIM()

去空格：

=TRIM(A2)

七、快速对照表（常用映射）

你的文件里这一列示例

在界面右侧选哪个

[email protected]

或手机号/ID

Account / Email → 对应 ColumnX

abc123456

Password → 对应 ColumnX

（辅助邮箱）

Auxiliary / Secondary Email（若有此项）→ ColumnX

c_user=...; xs=...;

（cookies）

Cookies → ColumnX

socks5://1.2.3.4:1080

1.2.3.4:1080

Proxy → ColumnX

123456

（验证码）

2FA → ColumnX

长串访问令牌

Token → ColumnX

八、示例

## Extracted Links

- https://blog.jarveepro.com/Home/Blog
- https://blog.jarveepro.com/Home/KnowledgeBaseList
- https://blog.jarveepro.com/cdn-cgi/l/email-protection
- https://blog.jarveepro.com/knowledge/%E4%B8%AD%E6%96%87%E6%95%99%E7%A8%8B/JarveePro-%E5%AF%BC%E5%85%A5%E8%B4%A6%E6%88%B7%E4%B8%AD%E6%96%87%E6%95%99%E5%AD%A6Facebook-%E6%89%B9%E9%87%8F%E5%AF%BC%E5%85%A5%E8%B4%A6%E5%8F%B7%E8%AF%A6%E7%BB%86%E6%AD%A5%E9%AA%A4/5432
- https://twitter.com/share?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2F%E4%B8%AD%E6%96%87%E6%95%99%E7%A8%8B%2FJarveePro-%E5%AF%BC%E5%85%A5%E8%B4%A6%E6%88%B7%E4%B8%AD%E6%96%87%E6%95%99%E5%AD%A6Facebook-%E6%89%B9%E9%87%8F%E5%AF%BC%E5%85%A5%E8%B4%A6%E5%8F%B7%E8%AF%A6%E7%BB%86%E6%AD%A5%E9%AA%A4%2F5432
- https://www.facebook.com/jarveeproadmin
- https://www.facebook.com/sharer/sharer.php?u=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2F%E4%B8%AD%E6%96%87%E6%95%99%E7%A8%8B%2FJarveePro-%E5%AF%BC%E5%85%A5%E8%B4%A6%E6%88%B7%E4%B8%AD%E6%96%87%E6%95%99%E5%AD%A6Facebook-%E6%89%B9%E9%87%8F%E5%AF%BC%E5%85%A5%E8%B4%A6%E5%8F%B7%E8%AF%A6%E7%BB%86%E6%AD%A5%E9%AA%A4%2F5432
- https://www.jarveepro.com/
- https://www.jarveepro.com/all-features.html
- https://www.jarveepro.com/contact-us.html
- https://www.jarveepro.com/contact.html
- https://www.jarveepro.com/discord-features.html
- https://www.jarveepro.com/facebook-features.html
- https://www.jarveepro.com/get-now.html
- https://www.jarveepro.com/instagram-features.html
- https://www.jarveepro.com/linkedIn-features.html
- https://www.jarveepro.com/pinterest-features.html
- https://www.jarveepro.com/pricing.html
- https://www.jarveepro.com/reddit-features.html
- https://www.jarveepro.com/tiktok-features.html
- https://www.jarveepro.com/tumblr-features.html
- https://www.jarveepro.com/twitter-features.html
- https://www.jarveepro.com/videos-tutorials.html
- https://www.jarveepro.com/whatsapp-features.html
- https://www.jarveepro.com/youtube-features.html
- https://www.pinterest.com/pin/create/button/?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2F%E4%B8%AD%E6%96%87%E6%95%99%E7%A8%8B%2FJarveePro-%E5%AF%BC%E5%85%A5%E8%B4%A6%E6%88%B7%E4%B8%AD%E6%96%87%E6%95%99%E5%AD%A6Facebook-%E6%89%B9%E9%87%8F%E5%AF%BC%E5%85%A5%E8%B4%A6%E5%8F%B7%E8%AF%A6%E7%BB%86%E6%AD%A5%E9%AA%A4%2F5432
