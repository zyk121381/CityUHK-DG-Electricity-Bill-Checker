<div align="right">
  <a title="English" href="README.md"><img src="https://img.shields.io/badge/-English-545759?style=for-the-badge" alt="English"></a>
  <a title="简体中文" href="README_CN.md"><img src="https://img.shields.io/badge/-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-A31F34?style=for-the-badge" alt="简体中文"></a>
</div>

<div align="center">

# ⚡ 香港城市大学（东莞）宿舍电量查询器

**定时查询香港城市大学（东莞）宿舍的剩余电量，把结果推到微信、飞书或邮箱。**

![WakaTime](https://wakatime.com/badge/user/a2c9dcda-13d4-4457-81cb-c15737459130/project/d9aa1e22-a180-4625-a957-95f73c0005f4.svg) ![Release](https://img.shields.io/github/v/release/zyk121381/CityUHK-DG-Electricity-Bill-Checker?style=flat) ![License](https://img.shields.io/badge/license-Apache%202.0-green) [![](https://img.shields.io/badge/Sponsor-f43f5e?logo=buymeacoffee&logoColor=white)](https://xa.2xrr.com/cashier/0e4c816c785bac0055)

</div>

## ✨ 功能特性

### 🔐 登录

电费平台挂在学校统一身份认证后面。网页登录要 SM2 加密、图形验证码和二次认证。

工具走的是 IdP 自己的 OAuth2 password grant，拿到的会话再换应用 token。

- 只需要学号和密码。不用手动打开浏览器 → 登录 → 抓包响应 → 复制cookie → 修改.env；
- 链路：`login_data` → `init_code` → `rest_token` → SSO 授权码 → `loginSSOMini` → token；
- 遇到 `401` 会把整条链重跑一遍并重试一次；
- 还支持另外两种模式：`sso`（会话 cookie）和 `token`（手动贴 UUID）。

### 📊 读数与分析

- 剩余电量，单位 kWh。配置里填上单价就会多给一个金额，填 0 就从账单自动反推（目前根据本人上个月的用电量和账单测算，似乎电价不太固定：8月算出来的是0.2640，9月算出来的是0.3364）；
- 与上次读数的差值。正数是充电，负数耗电；
- 日均用电，并注明这个均值算自哪一段日期（服务端历史一般都在几周前，非实时）；
- 预计还能用几天，以及预计哪天见底；
- 最新账单、往期账单，以及未缴账单提醒。

### 📈 趋势

- 日用量和月用量两条序列。Markdown 报告里压成一行 sparkline，终端和 HTML 报告里画成带标签的条形图；
- 数据来源：本地读数攒够 `min_local_days` 天才拿来算日均（间隔按真实时间折算，不按日历天数），不够就用服务端最近 14 天的日均。取最近 `analysis_window_days` 天的数据来平均，报告会写明来源和真实区间；
- 区间写的是真实区间。

### 🔔 推送

目前共支持八个渠道。想通过哪个渠道收消息，去 `.env` 中填哪些渠道的参数：

| 渠道 | 环境变量 | 获取方式 |
| --- | --- | --- |
|`email` | `SMTP_HOST`、`SMTP_PORT`、`SMTP_SSL`、`SMTP_USER`、`SMTP_PASSWORD`、`SMTP_TO`、`SMTP_SUBJECT_PREFIX` | 服务商的 SMTP 设置页（常见的有 smtp.qq.com / 465、smtp.163.com / 465、smtp.gmail.com / 587） |
| `wxpusher` | `WXPUSHER_SPT`、`WXPUSHER_CONTENT_TYPE` | <a href="https://wxpusher.zjiecode.com/api/qrcode/RwjGLMOPTYp35zSYQr0HxbCPrV9eU0wKVBXU1D5VVtya0cQXEJWPjqBdW3gKLifS.jpg"><img src="https://wxpusher.zjiecode.com/api/qrcode/RwjGLMOPTYp35zSYQr0HxbCPrV9eU0wKVBXU1D5VVtya0cQXEJWPjqBdW3gKLifS.jpg" width="100" height="100" alt="wxpusher 扫码获取 SPT" style="max-width:100px;height:auto"></a> |
|`showdoc`| `SHOWDOC_URL` | https://push.showdoc.com.cn/#/push |
| `pushplus` | `PUSHPLUS_TOKEN`、`PUSHPLUS_TOPIC` | https://www.pushplus.plus |
| `serverchan` | `SERVERCHAN_SENDKEY` | https://sct.ftqq.com |
| `feishu` | `FEISHU_WEBHOOK` | 群设置 → 群机器人 → 添加 → 复制 webhook。以交互卡片发送 |
| `wecom_bot` | `WECOM_WEBHOOK` | 群设置 → 群机器人 → 添加 → 复制 webhook |
| `webhook` | `WEBHOOK_URL` | 自建接口 |

- 同一份报告渲染三遍：Markdown、HTML、纯文本；
- 标题跟着推送频率变：一天里的第一条是「电量日报」，之后是「电量更新」，触发阈值是「电量告警」；
- 报告每次运行都推；只有告警才去重，`--force` 可以不管去重；
- 抓取失败会发通知。

### 🌍 语言

默认英文。改 `config.yaml` 的 `app.locale: zh` 就全部切成中文。

### 🗄️ 存储与定时

- 读数存在 SQLite，一条一行，带唯一键，同一分钟跑两次也不会写重复；
- 日用量由相邻的本地读数算出来，不直接用服务端的口径；
- Linux 每天 08:00 由 systemd timer 触发（`Persistent=true`，带随机延迟），Windows 用计划任务。

## 🚀 部署与运行

### 1. 安装

```bash
git clone https://github.com/zyk121381/CityUHK-DG-Electricity-Bill-Checker.git
cd CityUHK-DG-Electricity-Bill-Checker
python3 -m venv .venv           # Windows: python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Debian 和 Ubuntu 上 `python3 -m venv` 可能报 `ensurepip is not available`，先装 venv 包，版本跟你的 Python 对上：

```bash
sudo apt install -y python3.12-venv
```

`python3 -m venv` 半途而废留下的就是这个状态——`.venv` 里有 `bin/python` 却没有 `pip`，`rm -rf .venv` 重来一遍即可。

配置 `config.yaml` 和 `.env`：

- `config.yaml` —— 跑 `python run.py init` 生成，再改
- `.env` —— 你的学号、密码和推送渠道；传上去后 `chmod 600 .env`

### 2. 配置

```bash
cp config.example.yaml config.yaml
cp .env.example .env
python run.py init             # 也可以让它直接生成这两份
```

`.env` 放所有凭据和推送渠道：

```ini
# --- 校园平台 ---
EPAY_ACCOUNT=你的学号
EPAY_PASSWORD=你的密码

# --- 启用哪些渠道 ---
NOTIFY_CHANNELS=wxpusher,email

# --- ShowDoc ---
SHOWDOC_URL=
# --- WxPusher ---
WXPUSHER_SPT=
WXPUSHER_CONTENT_TYPE=3
# --- PushPlus ---
PUSHPLUS_TOKEN=
# --- Server酱 ---
SERVERCHAN_SENDKEY=
# --- 飞书 ---
FEISHU_WEBHOOK=
# --- 企业微信 ---
WECOM_WEBHOOK=
# --- 邮箱 ---
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_SSL=true
SMTP_USER=you@example.com
SMTP_PASSWORD=
SMTP_TO=you@example.com
SMTP_SUBJECT_PREFIX=[电量]
# --- 自定义 webhook ---
WEBHOOK_URL=
```

`config.yaml` 只放行为：接口链、告警阈值、电价。

```yaml
electricity:
  price_per_kwh: 0           # 0 = 从账单自动反推

notify:
  push_report: true           # 常规报告：每次运行都推
  alert_once_per_day: true    # 告警：同一天同样的告警只推一次（--force 可绕过）
  alerts:
    enabled: true             # 是否开启告警
    low_balance_kwh: 20       # 剩余电量低于这个数就告警
    low_days_left: 5          # 预计可用天数低于这个数就告警
    spike_ratio: 2.0          # 单日用电超过近期均值的几倍算异常
    silent_days: 2            # 连续多少天没抓到新数据就告警

storage:
  analysis_window_days: 7   # 日均用电取最近几天的数据来平均
  min_local_days: 3          # 本地读数至少覆盖几天才拿来算日均

app:
  locale: en              # en（默认）或 zh
```

### 3. 验证

```bash
python run.py doctor        # 配置完整性、渠道列表、token 是否有效
python run.py check --no-notify
python run.py notify-test   # 给每个启用的渠道发一条测试消息
```

在服务器上，`bash scripts/run-check.sh --no-notify` 是同样的事，只是不推送。交给定时任务之前先跑一遍——失败原因会直接打印出来，同时追加到 `logs/task.log`。

## ⏰ 定时任务

### Linux

```bash
bash scripts/install-linux.sh
```

装完会建好虚拟环境、写入 systemd 单元并启用 timer。每天本地时间 08:00 触发，随机延迟最多 5 分钟，关机期间错过的会在开机后补跑。

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1
```

注册一个每天调用 `scripts\run-check.ps1` 的计划任务。

### 用面板的计划任务

有些服务器面板自带「计划任务」，任务类型选 Shell 脚本，脚本内容填一行：

```bash
bash /opt/cityu-power/scripts/run-check.sh
```

把路径换成项目实际所在的目录——用绝对路径，面板任务不会从项目目录里启动。
解释器选 `bash`，用户选跑项目的那个账号，别用 root。

两个容易踩的坑：

- 脚本框里填的是**命令**，不是脚本正文。`run-check.sh` 自己会找项目目录、虚拟环境和日志文件；把它的内容粘进去，它就会跑到临时目录里去找项目。
- 别把 `--no-notify` 留在里面。这个参数的意思是「只抓不推」，任务会照跑，但消息永远到不了你手上。

### GitHub Actions

仓库里的 `.github/workflows/check.yml` **默认只手动触发**：Actions → 宿舍电量检查 → Run workflow。
不定时跑，想每天自动检查，按下面几步操作：

1. Fork 这个仓库到你自己的账号。
2. 在你的 fork 里编辑 `.github/workflows/check.yml`，把定时那段加回来：

   ```yaml
   on:
     schedule:
       # 00:00 UTC = 北京时间 08:00
       - cron: "0 0 * * *"
     workflow_dispatch:
   ```

3. 在 Settings → Secrets and variables → Actions 里添加：
   - `CONFIG_YAML` —— 完整的 `config.yaml` 内容
   - `EPAY_ACCOUNT`、`EPAY_PASSWORD` —— 你的学号和密码
   - `NOTIFY_CHANNELS` —— 要用哪些渠道，例如 `wxpusher,email`
   - 启用的每个渠道各填一个 secret，名字和 `.env` 里完全一致
4. 先在 Actions 页面手动跑一次，确认没问题。

**温馨提示**：
1. 仓库 60 天没有任何活动，GitHub 会自动停用定时任务；
2. runner 在大陆之外，`onebill.cityu-dg.edu.cn` 未必能访问得到。自己服务器上装 systemd timer 更稳。

## 🖥️ 命令

| 命令 | 作用 |
| --- | --- |
| `python run.py init` | 从模板生成 `config.yaml` 和 `.env` |
| `python run.py doctor` | 检查配置、缺失的环境变量、渠道和 token |
| `python run.py probe` | 打一次真实接口，导出原始响应 |
| `python run.py login` | 跑鉴权链并缓存 token |
| `python run.py token` | 手动替换缓存 token（先校验再落盘） |
| `python run.py check` | 抓取 + 分析 + 入库 + 推送（`--no-notify`、`--force`） |
| `python run.py report` | 用已有数据重新出报告（`--html`） |
| `python run.py history` | 查看最近读数（`-n 50`） |
| `python run.py price` | 查看每期账单反推出来的电价 |
| `python run.py notify-test` | 给每个启用的渠道发测试消息 |
| `python run.py purge` | 清理 N 天前的读数（`--keep-days 400`） |

## 🏗️ 技术栈

- **运行时**：Python 3.10+
- **HTTP**：httpx 0.27
- **配置**：PyYAML 6
- **存储**：标准库 SQLite
- **定时**：systemd timer（Linux）/ 计划任务（Windows）

## 📂 项目结构

```
CityUHK(DG) Electricity Bill Checker/
├── run.py                          # 入口
├── config.yaml                     # 接口链、鉴权、阈值、电价
├── config.example.yaml             # 配置模板
├── .env.example                    # 凭据与渠道模板
├── requirements.txt
├── src/cityu_power/
│   ├── cli.py                      # 子命令、推送策略、失败上报
│   ├── config.py                   # YAML 加载、${ENV} 展开、路径解析
│   ├── analyzer.py                 # 均值、差值、预测、告警、趋势
│   ├── i18n.py                     # 报告文案，中英两套
│   ├── report.py                   # Markdown / HTML / 纯文本三种渲染
│   ├── storage.py                  # SQLite 表结构、读数历史、去重键
│   ├── models.py                   # Reading 与 DailyUsage 数据类
│   ├── providers/
│   │   ├── base.py                 # ProviderError 与提供方接口
│   │   ├── http.py                 # 配置驱动的请求链 + 鉴权策略
│   │   └── mock.py                 # 离线演示数据
│   └── notify/
│       ├── base.py                 # 渠道基类、格式偏好
│       ├── channels.py             # 八个渠道的实现
│       └── __init__.py             # 注册表、环境变量配置、分发
├── scripts/
│   ├── install-linux.sh            # 建 venv + 装 systemd 单元
│   ├── cityu-power.service         # oneshot 服务定义
│   ├── cityu-power.timer           # 每天 08:00 触发
│   ├── register-task.ps1           # Windows 计划任务
│   ├── run-check.sh                # Linux 运行脚本
│   ├── run-check.ps1               # Windows 运行脚本
│   └── seed_demo.py                # 造一个月假数据
├── tests/test_smoke.py             # 本地假服务器，不联网
├── data/                           # 数据库、token 缓存、HTML 报告（已 gitignore）
├── logs/                           # 日志（已 gitignore）
├── LICENSE
├── README.md                       # 英文文档
└── README_CN.md                    # 中文文档
```

## 🔌 接口清单

工具使用的全部接口。除 `updateRemainCapacity`（让平台去抄一次表）外全是只读。

| 方法 | 接口 | 用途 |
| --- | --- | --- |
| `GET` | `/api/walletManagement/getWallet` | 房间号与 `meterSn` |
| `POST` | `/api/walletManagement/updateRemainCapacity` | 当前剩余电量 |
| `POST` | `/api/analysis/getEnergyUsageByDay` | 每日用电，最近 60 条 |
| `POST` | `/api/analysis/getEnergyUsageByMonth` | 每月用电，最近 12 个月 |
| `POST` | `/api/bill/myHistory` | 账单历史 |
| `POST` | `/api/bill/myUnpaid` | 未缴账单 |

鉴权接口：

| 方法 | 接口 | 用途 |
| --- | --- | --- |
| `GET` | `/api/public/bff/v1.2/frontend/login_data` | IdP 的 clientId |
| `GET` | `/api/public/bff/v1.2/one_time_login/init_code` | 随机串，作为 `sm2_code` 提交 |
| `POST` | `/api/public/bff/v1.2/rest_token` | OAuth2 password grant |
| `GET` | `/api/getSsoMiniInfo` | SSO 授权地址（公开接口） |
| `POST` | `/api/loginSSOMini` | 用授权码换应用 token |

新增一个数据点只需要改 `config.yaml`。请求链和取值路径都是声明式的。

- 授权地址来自 `getSsoMiniInfo`，属于**小程序客户端**。拿到的 code 必须用 `loginSSOMini` 兑换，用 `loginSSO` 会返回 `invalid_grant`；
- `sm2_code` 是 `init_code` 给的随机串，不是加密后的密码。这条链路密码是明文提交的，只有注册流程才走 SM2；
- `login_data` 返回的 IdP `clientId` 不是应用的 `client_id`，拿后者去 `rest_token` 会报 `Unauthorized grant type: password`；
- `getEnergyUsageByDay` 返回的是最近 60 条记录，会停在几周前。

## ⚙️ 实现说明

1. 充值、支付、退款接口都不会调用。唯一会改动数据的 `POST` 是 `updateRemainCapacity`，每次运行只发一次；
2. HTTP 提供方执行的是 YAML 里写好的步骤列表，取值走 JSON 路径。换接口、改字段名是改 YAML，不是改代码；
3. 每个均值和趋势都写明算自哪一段日期。停在几周前的历史会如实标注；
4. 抓取失败时会发通知，写明可能的原因和修复命令；
5. 两个包，SQLite 用标准库，不常驻进程。

## 📫 反馈
欢迎交流任何值得动手做的事。最方便的方式是下面的留言反馈页面。

[博客](https://www.040426.xyz) · [留言反馈](https://feedback.valerianblog.link) · [打赏](https://xa.2xrr.com/cashier/0e4c816c785bac0055)

如果这里的内容对你有一点帮助，可以[请我喝杯咖啡](https://xa.2xrr.com/cashier/0e4c816c785bac0055)。

<p align="center">
    <!-- 二维码：https://goqr.me/api/ -->
    <!-- 明暗双版本，避免暗色模式下二维码白得刺眼 -->
    <a href="https://xa.2xrr.com/cashier/0e4c816c785bac0055">
        <picture>
            <source media="(prefers-color-scheme: dark)" srcset="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https%3A%2F%2Fxa.2xrr.com%2Fcashier%2F0e4c816c785bac0055&bgcolor=0d1117&color=e6edf3"/>
            <source media="(prefers-color-scheme: light)" srcset="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https%3A%2F%2Fxa.2xrr.com%2Fcashier%2F0e4c816c785bac0055&bgcolor=ffffff&color=000000"/>
            <img width="100" src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https%3A%2F%2Fxa.2xrr.com%2Fcashier%2F0e4c816c785bac0055&bgcolor=ffffff&color=000000" alt="打赏二维码" title="打赏二维码"/>
        </picture>
    </a>
</p>

## 📄 开源许可证

本项目基于 [Apache 2.0 License](LICENSE) 协议发布。

---

<div align="center">
<b>半夜被热醒？该交电费了。⚡</b>
</div>
