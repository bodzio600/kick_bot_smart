<div align="center">

# 💥 Kick Viewer Bot

![Python](https://img.shields.io/badge/python-3.10-blue.svg?style=for-the-badge&logo=python)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)

**Automated viewer bot for Kick.com streams with realistic human-like behavior**

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Environment Variables](#-environment-variables)
- [Proxies](#-proxies)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## ✨ Features

- 🎭 **Realistic Viewer Simulation** - Mimics human behavior with natural fluctuations
- 📊 **Dynamic Viewer Management** - Automatically adjusts viewer count with major and minor fluctuations
- 🔄 **Auto Stream Detection** - Monitors stream status and pauses when offline
- 🌐 **Proxy Support** - Rotate through multiple proxies for connection diversity
- 🐳 **Docker Ready** - Easy deployment with Docker Compose
- 📈 **Real-time Statistics** - Live monitoring of active connections and viewer counts
- ⚡ **High Performance** - Handles multiple concurrent connections efficiently

---

## 📦 Prerequisites

- Docker & Docker Compose installed
- Proxies list (HTTP/HTTPS proxies)
- Python 3.10+ (if running without Docker)

---

## 🚀 Installation

1. **Clone the repository**

git clone https://github.com/bodzio600/kick-viewer-bot.git
cd kick-viewer-bot

text

2. **Create proxies file**

touch proxies.txt

text

3. **Add your proxies** to `proxies.txt` (one per line):

ip:port

ip:port:username:password

4. **Configure environment variables** in `docker-compose.yml`

---

## ⚙️ Configuration

Edit `docker-compose.yml` to customize your settings:

environment:

    CHANNEL=your_channel_name

    SPAWN_VIEWERS=50

    FLUCTUATION_PERCENT=0.4

    MAJOR_FLUCTUATION_INTERVAL=120,240

    MINOR_FLUCTUATION_INTERVAL=60,120

    TIMEOUT_WORKERS=0,1

    TIMEOUT_PING=3,8

    LOG_INTERVAL=10

text

---

## 🎯 Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `CHANNEL` | Target Kick.com channel name | *Required* | `anka_e` |
| `SPAWN_VIEWERS` | Target number of viewers to spawn | *Required* | `50` |
| `FLUCTUATION_PERCENT` | Percentage of viewer fluctuation (±) | `0.15` | `0.4` (40%) |
| `MAJOR_FLUCTUATION_INTERVAL` | Time range for major fluctuations (seconds) | `180,600` | `120,240` |
| `MINOR_FLUCTUATION_INTERVAL` | Time range for minor adjustments (seconds) | `60,180` | `60,120` |
| `TIMEOUT_WORKERS` | Delay range between spawning workers (seconds) | `10,120` | `0,1` |
| `TIMEOUT_PING` | Delay range between WebSocket pings (seconds) | `2,12` | `3,8` |
| `LOG_INTERVAL` | Status log update interval (seconds) | `10` | `10` |

### Fluctuation Behavior

- **FLUCTUATION_PERCENT**: Controls the bounds of viewer count fluctuation
  - Example: `0.4` = ±40% of `SPAWN_VIEWERS`
  - If `SPAWN_VIEWERS=50`, range is `30-70 viewers`

- **MAJOR_FLUCTUATION_INTERVAL**: Aggressive fluctuations (~30% change)
  - Simulates significant viewer drops/gains
  - Random interval between min and max seconds

- **MINOR_FLUCTUATION_INTERVAL**: Subtle adjustments (1-5% change)
  - Simulates natural viewer drift
  - More frequent than major fluctuations

---

## 📝 Proxies

Create a `proxies.txt` file in the root directory with your proxies:

**Format 1: IP:Port**

1.2.3.4:8080
5.6.7.8:3128

text

**Format 2: IP:Port:Username:Password**

1.2.3.4:8080:user:pass
5.6.7.8:3128:admin:secret

text

> ⚠️ **Important**: At least one proxy is required for the bot to function

---

## 🎮 Usage

### Start the bot

docker-compose up -d

text

### View logs

docker-compose logs -f kick_viewer

text

### Stop the bot

docker-compose down

text

### Restart the bot

docker-compose restart

text

### Check status

docker-compose ps

text

---

## 📊 Log Output

The bot provides detailed real-time statistics:

👁️ Watching: 45 | 🎯 Target viewers: 48 | 📊 Viewers range: [30-70] |
❌ Failed: 3 | 👥 Viewers: 52 | 🟢 Live : True |
⚡ Threads: 48 Active/ 22 InActive/ 70 Total

text

**Legend:**
- 👁️ **Watching**: Currently active connections
- 🎯 **Target viewers**: Current target (changes with fluctuations)
- 📊 **Viewers range**: Min-max based on fluctuation percentage
- ❌ **Failed**: Total failed connection attempts
- 👥 **Viewers**: Actual viewer count from Kick API
- 🟢 **Live**: Stream online status
- ⚡ **Threads**: Connection pool status

---

## 🐛 Troubleshooting

### Bot not starting
- Ensure `proxies.txt` exists and contains valid proxies
- Check Docker logs: `docker-compose logs kick_viewer`

### No connections established
- Verify proxies are working
- Check if channel name is correct
- Ensure stream is live

### High failure rate
- Proxies may be banned/invalid - update `proxies.txt`
- Reduce `SPAWN_VIEWERS` count
- Increase `TIMEOUT_WORKERS` interval

### Memory issues
- Reduce `SPAWN_VIEWERS`
- Adjust Docker memory limits in `docker-compose.yml`

---

## ⚠️ Disclaimer

This tool is for educational purposes only. Using viewbots may violate Kick.com's Terms of Service and could result in account suspension or ban. Use at your own risk.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<div align="center">

**Made with ❤️ by the community**

</div>