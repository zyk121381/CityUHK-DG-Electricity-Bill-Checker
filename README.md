<div align="right">
  <a title="English" href="README.md"><img src="https://img.shields.io/badge/-English-A31F34?style=for-the-badge" alt="English"></a>
  <a title="简体中文" href="README_CN.md"><img src="https://img.shields.io/badge/-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-545759?style=for-the-badge" alt="简体中文"></a>
</div>

<div align="center">

# ⚡ CityUHK (DG) Dorm Electricity Checker

**Checks the remaining electricity of a CityUHK (DG) dorm room on a schedule and sends the result to WeChat, Feishu or email.**

![WakaTime](https://wakatime.com/badge/user/a2c9dcda-13d4-4457-81cb-c15737459130/project/d9aa1e22-a180-4625-a957-95f73c0005f4.svg) ![Release](https://img.shields.io/github/v/release/zyk121381/CityUHK-DG-Electricity-Bill-Checker?style=flat) ![License](https://img.shields.io/badge/license-Apache%202.0-green) [![](https://img.shields.io/badge/Sponsor-f43f5e?logo=buymeacoffee&logoColor=white)](https://xa.2xrr.com/cashier/0e4c816c785bac0055)

</div>

## ✨ Features

### 🔐 Sign-in

The payment platform sits behind the university IdP. Its web login uses SM2 encryption, a CAPTCHA and a second factor.

The tool uses the IdP's own OAuth2 password grant instead, and trades the session it gets for an application token.

- Student ID and password only. No opening a browser → signing in → copying the cookie response → editing .env;
- Chain: `login_data` → `init_code` → `rest_token` → SSO code → `loginSSOMini` → token;
- A `401` re-runs the whole chain and retries the request once;
- Two other modes are supported as well: `sso` (session cookie) and `token` (paste a UUID by hand).

### 📊 Reading and analysis

- Remaining balance in kWh. Set a unit price in the config and you also get a currency figure — leave it at 0 and the rate is worked out from your bills (the price does not look fixed — on my account August works out at 0.2640 and September at 0.3364);
- Difference from the previous reading. Positive means a top-up, negative means consumption;
- Daily average, together with the range of dates it was calculated from (the server's history usually ends weeks ago, so it is not live);
- Days of runway left, and the day the balance is expected to run out;
- Latest bill, the months before it, and a warning when a bill is unpaid.

### 📈 Trends

- Daily and monthly series. The Markdown report squeezes them into a one-line sparkline; the terminal and HTML reports draw labelled bars;
- Source: local readings once three days have accumulated, otherwise the server history. The report names the source and prints the real range;
- The range is the real one.

### 🔔 Notifications

Eight channels so far. Fill in the parameters of the one you want in `.env`:

| Channel | Environment variables | How to get it |
| --- | --- | --- |
| `email` | `SMTP_HOST`、`SMTP_PORT`、`SMTP_SSL`、`SMTP_USER`、`SMTP_PASSWORD`、`SMTP_TO`、`SMTP_SUBJECT_PREFIX` | The provider's SMTP settings page (smtp.qq.com / 465, smtp.163.com / 465, smtp.gmail.com / 587 are common) |
| `wxpusher` | `WXPUSHER_SPT`、`WXPUSHER_CONTENT_TYPE` | <a href="https://wxpusher.zjiecode.com/api/qrcode/RwjGLMOPTYp35zSYQr0HxbCPrV9eU0wKVBXU1D5VVtya0cQXEJWPjqBdW3gKLifS.jpg"><img src="https://wxpusher.zjiecode.com/api/qrcode/RwjGLMOPTYp35zSYQr0HxbCPrV9eU0wKVBXU1D5VVtya0cQXEJWPjqBdW3gKLifS.jpg" width="100" height="100" alt="wxpusher 扫码获取 SPT" style="max-width:100px;height:auto"></a> |
| `showdoc` | `SHOWDOC_URL` | https://push.showdoc.com.cn/#/push |
| `pushplus` | `PUSHPLUS_TOKEN`、`PUSHPLUS_TOPIC` | https://www.pushplus.plus |
| `serverchan` | `SERVERCHAN_SENDKEY` | https://sct.ftqq.com |
| `feishu` | `FEISHU_WEBHOOK` | Group settings → bot → add → copy the webhook. Sent as an interactive card |
| `wecom_bot` | `WECOM_WEBHOOK` | Group settings → bot → add → copy the webhook |
| `webhook` | `WEBHOOK_URL` | Your own endpoint |

- One report is rendered three ways: Markdown, HTML and plain text;
- The title follows how often you push: the first one of the day is a daily report, the ones after that are updates, and a threshold breach is an alert;
- The report goes out on every run; only alerts are de-duplicated, and `--force` skips that;
- A failed fetch sends a notice.

### 🌍 Language

English by default. Change `app.locale: zh` in `config.yaml` to switch everything to Chinese.

### 🗄️ Storage and scheduling

- Readings are kept in SQLite, one row each, with a unique key, so two runs in the same minute do not write duplicates;
- Daily usage is worked out from consecutive local readings rather than taken from the server's own numbers;
- On Linux a systemd timer fires it at 08:00 (`Persistent=true`, with a random delay), on Windows it is a scheduled task.

## 🚀 Getting Started

### 1. Install

```bash
git clone https://github.com/zyk121381/CityUHK-DG-Electricity-Bill-Checker.git
cd CityUHK-DG-Electricity-Bill-Checker
python3 -m venv .venv           # Windows: python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

On Debian and Ubuntu, `python3 -m venv` can fail with `ensurepip is not available`. Install the venv package first, with the version that matches your Python:

```bash
sudo apt install -y python3.12-venv
```

The same package is what a `python3 -m venv` that half-succeeded leaves behind — a `.venv` with a `bin/python` but no `pip`. `rm -rf .venv` and do it again.

Configure `config.yaml` and `.env`:

- `config.yaml` — run `python run.py init` to generate it, then edit it
- `.env` — your student ID, password and push channels; `chmod 600 .env` afterwards

### 2. Configure

```bash
cp config.example.yaml config.yaml
cp .env.example .env
python run.py init             # or let this generate both files
```

`.env` holds all the credentials and the push channels:

```ini
# --- Campus platform ---
EPAY_ACCOUNT=your_student_id
EPAY_PASSWORD=your_password

# --- Which channels are active ---
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
# --- Feishu ---
FEISHU_WEBHOOK=
# --- WeCom ---
WECOM_WEBHOOK=
# --- Email ---
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_SSL=true
SMTP_USER=you@example.com
SMTP_PASSWORD=
SMTP_TO=you@example.com
SMTP_SUBJECT_PREFIX=[Power]
# --- Custom webhook ---
WEBHOOK_URL=
```

`config.yaml` holds behaviour only: the endpoint chain, the alert thresholds and the unit price.

```yaml
electricity:
  price_per_kwh: 0           # 0 = derive it from the bills

notify:
  push_report: true           # push a report on every run
  alert_once_per_day: true    # one alert of the same kind per day (--force skips it)
  alerts:
    enabled: true             # turn the alerts on or off
    low_balance_kwh: 20       # alert when the balance drops below this
    low_days_left: 5          # alert when fewer days are left than this
    spike_ratio: 2.0          # a day is unusual above this multiple of the recent average
    silent_days: 2            # alert after this many days without a new reading

app:
  locale: en              # en (default) or zh
```

### 3. Verify

```bash
python run.py doctor        # config completeness, channel list, token validity
python run.py check --no-notify
python run.py notify-test   # send one message to every active channel
```

On a server, `bash scripts/run-check.sh --no-notify` does the same thing without pushing. Run it once before handing the job over to the scheduler — if it fails, the reason is printed and also appended to `logs/task.log`.

## ⏰ Scheduling

### Linux

```bash
bash scripts/install-linux.sh
```

Creates a virtualenv, installs the systemd unit and enables the timer. It runs at 08:00 local time with a random delay of up to five minutes, and catches up after downtime.

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1
```

Registers a daily scheduled task that calls `scripts\run-check.ps1`.

### Scheduled tasks in a web panel

If your server has a panel with a scheduled task feature, pick *Shell script* and paste one line:

```bash
bash /opt/cityu-power/scripts/run-check.sh
```

Replace the path with wherever the project lives — use an absolute path, a panel task does not start inside the project.
Set the interpreter to `bash` and the user to the account that owns the project, not root.

Two things that catch people out:

- The script box takes a **command**, not the body of the script. `run-check.sh` finds the project directory, the virtual environment and the log file on its own; pasting its contents in makes it look for the project in a temporary folder.
- Leave `--no-notify` out. That flag means "fetch but do not push", so the task runs on schedule and nothing ever reaches you.

### GitHub Actions

The workflow in `.github/workflows/check.yml` **only runs on demand**: Actions → 宿舍电量检查 → Run workflow.
Nothing runs on a schedule, to have it check every day, set it up like this:

1. Fork this repository to your own account.
2. In your fork, edit `.github/workflows/check.yml` and put the schedule back:

   ```yaml
   on:
     schedule:
       # 00:00 UTC = 08:00 Beijing time
       - cron: "0 0 * * *"
     workflow_dispatch:
   ```

3. Add the secrets under Settings → Secrets and variables → Actions:
   - `CONFIG_YAML` — the whole `config.yaml`
   - `EPAY_ACCOUNT`, `EPAY_PASSWORD` — your student ID and password
   - `NOTIFY_CHANNELS` — which channels to use, e.g. `wxpusher,email`
   - one secret per channel you enabled, named exactly as in `.env`
4. Run it once from the Actions page to check the setup.

**Worth knowing**:
1. GitHub turns scheduled workflows off after 60 days without activity in the repository;
2. The runners sit outside the Chinese mainland, so `onebill.cityu-dg.edu.cn` may not answer them. A systemd timer on your own server is steadier.

## 🖥️ Commands

| Command | Purpose |
| --- | --- |
| `python run.py init` | Generate `config.yaml` and `.env` from templates |
| `python run.py doctor` | Check config, required env vars, channels and token |
| `python run.py probe` | Hit the real API once and dump raw responses |
| `python run.py login` | Run the auth chain and cache the token |
| `python run.py token` | Manually replace the cached token (validated first) |
| `python run.py check` | Fetch, analyse, store and push (`--no-notify`, `--force`) |
| `python run.py report` | Re-render the report from stored data (`--html`) |
| `python run.py history` | Show recent readings (`-n 50`) |
| `python run.py price` | Show the unit price implied by each bill |
| `python run.py notify-test` | Send a test message to every active channel |
| `python run.py purge` | Delete readings older than N days (`--keep-days 400`) |

## 🏗️ Tech Stack

- **Runtime**: Python 3.10+
- **HTTP**: httpx 0.27
- **Config**: PyYAML 6
- **Storage**: SQLite from the standard library
- **Scheduling**: systemd timer (Linux) / Scheduled Tasks (Windows)

## 📂 Project Structure

```
CityUHK(DG) Electricity Bill Checker/
├── run.py                          # Entry point
├── config.yaml                     # Endpoint chain, auth, thresholds, price
├── config.example.yaml             # Config template
├── .env.example                    # Credentials and channel template
├── requirements.txt
├── src/cityu_power/
│   ├── cli.py                      # Subcommands, notify policy, failure reports
│   ├── config.py                   # YAML loading, ${ENV} expansion, path resolution
│   ├── analyzer.py                 # Averages, deltas, forecasts, alerts, trends
│   ├── i18n.py                     # Report wording, English and Chinese
│   ├── report.py                   # Markdown / HTML / plain-text renderers
│   ├── storage.py                  # SQLite schema, reading history, dedupe keys
│   ├── models.py                   # Reading and DailyUsage dataclasses
│   ├── providers/
│   │   ├── base.py                 # ProviderError, provider interface
│   │   ├── http.py                 # Config-driven request chain + auth strategies
│   │   └── mock.py                 # Offline demo data
│   └── notify/
│       ├── base.py                 # Channel base class, format preference
│       ├── channels.py             # The eight channel implementations
│       └── __init__.py             # Registry, env-driven config, fan-out
├── scripts/
│   ├── install-linux.sh            # venv + systemd unit installation
│   ├── cityu-power.service         # oneshot service definition
│   ├── cityu-power.timer           # daily 08:00 schedule
│   ├── register-task.ps1           # Windows scheduled task
│   ├── run-check.sh                # Linux runner
│   ├── run-check.ps1               # Windows runner
│   └── seed_demo.py                # Generate a month of fake readings
├── tests/test_smoke.py             # Local fake server, no network required
├── data/                           # SQLite DB, token cache, HTML report (gitignored)
├── logs/                           # Log file (gitignored)
├── LICENSE
├── README.md                       # English documentation
└── README_CN.md                    # Chinese documentation
```

## 🔌 API Surface

Every endpoint the tool talks to. All of them are read-only except `updateRemainCapacity`, which makes the platform read the meter.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/walletManagement/getWallet` | Room number and `meterSn` |
| `POST` | `/api/walletManagement/updateRemainCapacity` | Current balance in kWh |
| `POST` | `/api/analysis/getEnergyUsageByDay` | Daily usage, last 60 records |
| `POST` | `/api/analysis/getEnergyUsageByMonth` | Monthly usage, last 12 months |
| `POST` | `/api/bill/myHistory` | Bill history |
| `POST` | `/api/bill/myUnpaid` | Outstanding bills |

Authentication endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/public/bff/v1.2/frontend/login_data` | IdP client ID |
| `GET` | `/api/public/bff/v1.2/one_time_login/init_code` | Random string, sent as `sm2_code` |
| `POST` | `/api/public/bff/v1.2/rest_token` | OAuth2 password grant |
| `GET` | `/api/getSsoMiniInfo` | SSO authorize URL (public) |
| `POST` | `/api/loginSSOMini` | Exchange the authorize code for a token |

Adding a new data point means editing `config.yaml` only. The request chain and the extraction paths are declarative.

- The authorize URL comes from `getSsoMiniInfo`, which belongs to the **mini-program client**. The code must be exchanged with `loginSSOMini`; `loginSSO` returns `invalid_grant`;
- `sm2_code` is a random string from `init_code`, not an encrypted password. The password is sent in plain text on this path; only the registration flow uses SM2;
- The IdP `clientId` returned by `login_data` is not the application `client_id`; sending the latter to `rest_token` gives `Unauthorized grant type: password`;
- `getEnergyUsageByDay` returns the most recent 60 records, and they can stop weeks ago.

## ⚙️ Implementation Notes

1. Recharge, payment and refund endpoints are never called. The only `POST` that changes anything is `updateRemainCapacity`, and it is sent once per run;
2. The HTTP provider runs a list of steps written in YAML and extracts fields by JSON path. A new endpoint or a renamed field is a YAML edit, not a code edit;
3. Every average and trend states the range of dates it came from. History that stopped weeks ago is labelled as such;
4. When a fetch fails, a notification goes out with the likely cause and the command that fixes it;
5. Two packages, SQLite from the standard library, no long-running process.

## 📫 Feedback
Welcome to talk about anything worth building. The easiest way is the feedback page below.

[Blog](https://www.040426.xyz) · [Feedback](https://feedback.valerianblog.link) · [Donate](https://xa.2xrr.com/cashier/0e4c816c785bac0055)

If any of this helped you, [buy me a coffee](https://xa.2xrr.com/cashier/0e4c816c785bac0055).

<p align="center">
    <!-- QR code: https://goqr.me/api/ -->
    <!-- Light and dark versions, so it does not glare in dark mode -->
    <a href="https://xa.2xrr.com/cashier/0e4c816c785bac0055">
        <picture>
            <source media="(prefers-color-scheme: dark)" srcset="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https%3A%2F%2Fxa.2xrr.com%2Fcashier%2F0e4c816c785bac0055&bgcolor=0d1117&color=e6edf3"/>
            <source media="(prefers-color-scheme: light)" srcset="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https%3A%2F%2Fxa.2xrr.com%2Fcashier%2F0e4c816c785bac0055&bgcolor=ffffff&color=000000"/>
            <img width="100" src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https%3A%2F%2Fxa.2xrr.com%2Fcashier%2F0e4c816c785bac0055&bgcolor=ffffff&color=000000" alt="Donation QR code" title="Donation QR code"/>
        </picture>
    </a>
</p>

## 📄 License

Released under the [Apache 2.0 License](LICENSE).

---

<div align="center">
<b>Woke up hot? Top up your balance. ⚡</b>
</div>
