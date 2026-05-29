# StockNoti

ระบบวิเคราะห์หุ้นและแจ้งเตือนเข้า Discord แบบรายวัน เน้นใช้งานฟรีเป็นหลัก โดยรวบรวมราคา, กราฟเทคนิค, งบการเงิน, ข่าว, sentiment และความเสี่ยง แล้วจัดอันดับหุ้นที่น่าสนใจ 5 อันดับแรก และหุ้นที่ควรรอก่อน 5 อันดับ

> ข้อมูลนี้เป็นเครื่องมือช่วยทำการบ้าน ไม่ใช่คำแนะนำการลงทุนโดยตรง ควรดูงบและข่าวจากแหล่งทางการก่อนตัดสินใจเสมอ

## ความสามารถ

- จัดอันดับหุ้นรายวันจาก watchlist
- วิเคราะห์หุ้นรายตัวตาม ticker ที่ผู้ใช้เรียก เช่น `AAPL`, `NVDA`, `ADVANC.BK`
- บอกคะแนนรวมและคะแนนย่อย: เทคนิค, พื้นฐาน, ข่าว, ความเสี่ยง
- บอกแนวรับและแนวต้านจากกราฟย้อนหลัง
- ส่งข้อความ Discord เป็น embed อ่านง่าย เหมาะกับมือใหม่
- ใช้ `yfinance` ได้ฟรีทันที และรองรับ API ฟรีเพิ่มเติมจาก Finnhub / Alpha Vantage

## แหล่งข้อมูล

- `yfinance`: ราคา, กราฟย้อนหลัง, ข้อมูลงบและตัวเลขพื้นฐานบางส่วน
- Finnhub: ข่าวรายบริษัทผ่าน free API key
- Alpha Vantage: ข่าวและ sentiment ผ่าน free API key

ถ้าไม่ใส่ API key ระบบยังรันได้ด้วย `yfinance` แต่ข่าวและ sentiment อาจน้อยลง

## ติดตั้ง

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item config\watchlist.example.yaml config\watchlist.yaml
```

จากนั้นแก้ไฟล์ `.env`:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
FINNHUB_API_KEY=
ALPHA_VANTAGE_API_KEY=
```

และแก้ `config/watchlist.yaml` เป็นหุ้นที่อยากติดตาม

## วิธีใช้งาน

จัดอันดับรายวัน:

```powershell
python -m stocknoti.cli daily
```

ส่งรายงานเข้า Discord:

```powershell
python -m stocknoti.cli daily --send-discord
```

วิเคราะห์หุ้นรายตัว:

```powershell
python -m stocknoti.cli analyze NVDA
python -m stocknoti.cli analyze ADVANC.BK --send-discord
```

ดู payload ของ Discord ก่อนส่งจริง:

```powershell
python -m stocknoti.cli analyze AAPL --json
```

## ใช้งานเป็น Discord Bot

โหมด bot จะใช้ slash commands ใน Discord และต้องมี process ที่เปิดค้างไว้ เช่น เครื่องตัวเอง, VPS หรือ worker hosting

เพิ่มค่าใน `.env`:

```env
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
DISCORD_DAILY_CHANNEL_ID=
STOCKNOTI_DAILY_ENABLED=false
STOCKNOTI_DAILY_TIME=08:30
STOCKNOTI_TIMEZONE=Asia/Bangkok
```

รัน bot:

```powershell
python -m stocknoti.bot
```

หรือใช้ผ่าน CLI:

```powershell
python -m stocknoti bot
```

คำสั่งใน Discord:

- `/analyze symbol:AAPL` วิเคราะห์หุ้นรายตัว
- `/daily top:5` จัดอันดับหุ้นจาก watchlist
- `/watchlist` ดูรายชื่อหุ้นที่ติดตาม
- `/stock_help` ดูคำสั่งทั้งหมด

ถ้าเปิด `STOCKNOTI_DAILY_ENABLED=true` และใส่ `DISCORD_DAILY_CHANNEL_ID` bot จะส่งรายงานรายวันเองเวลา `STOCKNOTI_DAILY_TIME` ตาม timezone ที่ตั้งไว้

### วิธีสร้าง Discord Bot Token

1. เข้า Discord Developer Portal
2. สร้าง Application ใหม่
3. ไปที่แท็บ Bot แล้วกด Add Bot
4. กด Reset Token หรือ Copy Token แล้วใส่ใน `DISCORD_BOT_TOKEN`
5. ไปที่ OAuth2 > URL Generator
6. เลือก scopes: `bot` และ `applications.commands`
7. เลือก permissions: `Send Messages`, `Embed Links`, `Read Message History`
8. เปิด URL ที่สร้าง แล้ว invite bot เข้า server

ถ้าตั้ง `DISCORD_GUILD_ID` เป็น server id ของคุณ คำสั่ง slash commands จะ sync เร็วขึ้นตอนทดสอบ

## ตั้งให้รันทุกวันบน Windows

ตัวอย่างให้รันทุกวันเวลา 08:30:

```powershell
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"cd 'C:\Users\flame\OneDrive\เอกสาร\StockNoti'; .\.venv\Scripts\Activate.ps1; python -m stocknoti.cli daily --send-discord`""
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:30AM
Register-ScheduledTask -TaskName "StockNoti Daily" -Action $Action -Trigger $Trigger -Description "Daily stock recommendation report to Discord"
```

## รันต่อเนื่องด้วย GitHub Actions

โปรเจกต์นี้มี workflow ที่ `.github/workflows/daily-stocknoti.yml` แล้ว โดยตั้งให้รันทุกวันเวลา 08:30 ตามเวลาไทย และกดรันเองได้จากแท็บ Actions

ให้ตั้งค่า secrets ใน GitHub Repository:

- `DISCORD_WEBHOOK_URL` จำเป็นสำหรับส่งเข้า Discord
- `FINNHUB_API_KEY` ใส่หรือไม่ใส่ก็ได้
- `ALPHA_VANTAGE_API_KEY` ใส่หรือไม่ใส่ก็ได้

วิธีตั้งค่า:

1. เข้า repository บน GitHub
2. ไปที่ Settings > Secrets and variables > Actions
3. กด New repository secret
4. เพิ่ม `DISCORD_WEBHOOK_URL` และ API key ที่มี
5. ไปที่แท็บ Actions > StockNoti Daily Report > Run workflow เพื่อทดสอบทันที

รายชื่อหุ้นที่รันจริงอยู่ใน `config/watchlist.yaml` แก้ไฟล์นี้แล้ว push ขึ้น GitHub ได้เลย

## แนวคิดคะแนน

คะแนนรวมถ่วงน้ำหนักจาก:

- เทคนิค 38%: SMA20/50/200, RSI, MACD, volume, trend
- พื้นฐาน 32%: รายได้, กำไร, margin, ROE, P/E, debt/equity
- ข่าว 18%: sentiment จาก API หรือ keyword เบื้องต้น
- ความเสี่ยง 12%: beta, ระยะห่างแนวรับ/แนวต้าน

สูตรนี้ออกแบบให้เป็นจุดเริ่มต้น ปรับน้ำหนักได้ใน `stocknoti/scoring.py`
