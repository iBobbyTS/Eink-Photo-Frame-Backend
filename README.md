# Eink-Photo-Frame-Backend

一个基于树莓派和 Waveshare 彩色电子墨水屏（7.3" epd7in3f）的壁纸自动展示系统。支持定时刷新图像、模糊适配比例、Web API 远程控制、Home Assistant 集成等功能。

## 📦 功能特色

- 自动从指定文件夹中轮换图片
- 图片按屏幕比例裁切、缩放、背景模糊处理
- 基于 Flask 提供 REST API
- Home Assistant 集成控制刷新
- systemd 启动服务（开机自动运行）
- 支持远程显示最新添加的图片


---

## 🚀 安装步骤

### 1. 安装系统依赖


### 2. 安装 Python
如果已经有Python环境，可以直接使用，Python 3.13暂时不支持，已测试3.11和3.12。
如果没有安装Python，可以使用以下命令安装
```bash
wget https://github.com/astral-sh/python-build-standalone/releases/download/20250409/cpython-3.12.10+20250409-aarch64-unknown-linux-gnu-install_only.tar.gz
tar -xzf cpython-3.12.10+20250409-aarch64-unknown-linux-gnu-install_only.tar.gz
sudo mv python /opt/python3.12.10
export PATH="/opt/python3.12.10/bin:$PATH"
```

### 3. 安装 Python 库依赖

```bash
pip install -r requirements.txt
```

### 4. 启动测试

```bash
cd Eink-Wallpaper
python main.py
```

访问 `http://<raspberrypi-ip>:36547/api/switch_now` 测试是否正常刷新屏幕。

---

## 🔧 配置 systemd 服务（开机自启）

### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/eink.service
```

粘贴以下内容（如有不同路径，请自行修改）：

```ini
[Unit]
Description=Eink Start Script
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/opt/python3.12.10/bin/python main.py
WorkingDirectory=/home/ibobby/Eink-Wallpaper
Restart=on-failure
User=ibobby
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### 2. 启用并启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable eink.service
sudo systemctl start eink.service
```

查看状态：

```bash
journalctl -u eink.service -b --no-pager
```

---

## 🌐 Home Assistant 集成

### 1. `configuration.yaml`

```yaml
# 用 input_boolean 替代 input_button（可以被 HomeKit 识别为开关）
input_boolean:
  switch_wallpaper_now:
    name: Switch Wallpaper Now
  switch_to_new_wallpaper:
    name: Switch to Latest Wallpaper

# REST 命令（保持不变）
rest_command:
  switch_wallpaper_now:
    url: "http://ibobby-rpi-eink.local:36547/api/switch_now"
    method: GET

  switch_to_new_wallpaper:
    url: "http://ibobby-rpi-eink.local:36547/api/display_new"
    method: GET

# 模板传感器和原始传感器（保持不变）
template:
  - sensor:
      - name: "Eink Switch Time"
        unique_id: sensor.eink_switch_time
        unit_of_measurement: "°C"
        state: "{{ states('sensor.eink_switch_time') }}"
        availability: "{{ states('sensor.eink_switch_time') not in ['unavailable', 'unknown'] }}"
  - sensor:
      - name: "Eink Switch Time Value"
        unique_id: sensor.eink_switch_time_value
        state: "0"
        device_class: temperature
        unit_of_measurement: "°C"

# HomeKit：现在把按钮也暴露
homekit:
  filter:
    include_entities:
      - sensor.eink_switch_time
      - input_boolean.switch_wallpaper_now
      - input_boolean.switch_to_new_wallpaper
```

### 2. `automations.yaml`

```yaml
- alias: "HomeKit: Switch Wallpaper Now"
  trigger:
    platform: state
    entity_id: input_boolean.switch_wallpaper_now
    to: 'on'
  action:
    - service: rest_command.switch_wallpaper_now
    - delay: "00:00:01"
    - service: input_boolean.turn_off
      target:
        entity_id: input_boolean.switch_wallpaper_now

- alias: "HomeKit: Switch to Latest Wallpaper"
  trigger:
    platform: state
    entity_id: input_boolean.switch_to_new_wallpaper
    to: 'on'
  action:
    - service: rest_command.switch_to_new_wallpaper
    - delay: "00:00:01"
    - service: input_boolean.turn_off
      target:
        entity_id: input_boolean.switch_to_new_wallpaper
```
---

## 📷 默认图片路径

你可以将壁纸放入目录：

```
/mnt/Data/装机/Wallpaper/树莓派
```

脚本将定时自动轮换其中图片。

---

## ✅ 接口说明（Flask）

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/switch_now` | GET | 立即更换壁纸 |
| `/api/display_new` | GET | 显示最新添加的图片，并延迟下一次 |
| `/api/get_status` | GET | 获取剩余分钟数与定时器状态 |

---

## ✨ 墨水屏驱动来源

- [Waveshare/e-Paper](https://github.com/waveshare/e-Paper)

---

## 📄 License

MIT License

