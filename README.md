# 雷神加速器 Home Assistant 集成

把雷神加速器（leigod）接入 Home Assistant，支持**短信验证码登录**、加速时长暂停/恢复、剩余时长监控，并可与其他设备（如 Xbox、PS5）做自动化联动。

> 非官方集成。通过雷神 Web API 实现，接口可能随官方调整而失效。

---

## 功能

| 功能 | 说明 |
|---|---|
| 📱 短信验证码登录 | 集成内直接填手机号收验证码，无需手动复制 Token |
| 🔑 Token 登录 | 备用方式，从浏览器复制 `account_token` 粘贴即可 |
| 🚀 加速开关 | `switch` 实体，开 = 继续计时，关 = 暂停计时 |
| ⏱ 剩余时长 | 剩余可用时长（小时） |
| 📊 账号状态 | 计时中 / 已暂停 |
| 🔄 自动重认证 | 登录态过期时 HA 会提示重新登录，无需删除重装 |
| 🎨 品牌图标 | 自带雷神官方图标 |

---

## 安装

### 方式一：HACS（推荐）

1. HACS → 集成 → 右上角 ⋮ → **自定义存储库**
2. 仓库地址填：`https://github.com/ley108/ha-leishen`，类别选 **Integration**
3. 在 HACS 中搜索「雷神加速器」安装
4. **重启 Home Assistant**

### 方式二：手动安装

1. 下载 [Release](https://github.com/ley108/ha-leishen/releases/latest) 里的 `leishen.zip`
2. 把 `custom_components/leishen` 整个文件夹复制到 HA 配置目录下：
   ```
   config/
   └── custom_components/
       └── leishen/
           ├── __init__.py
           ├── api.py
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── manifest.json
           ├── sensor.py
           ├── switch.py
           ├── strings.json
           ├── brand/
           └── translations/
   ```
3. **重启 Home Assistant**

> ⚠️ 修改集成代码后必须重启 HA 进程，仅"重新加载集成"不会重新导入 Python 模块。

---

## 配置

设置 → 设备与服务 → 右下角 **添加集成** → 搜索「雷神加速器」。

会看到两种登录方式：

### 手机号 + 短信验证码（推荐）

1. 输入雷神账号绑定的手机号（国内区号填 `86`）
2. 提交后雷神会下发短信验证码
3. 填入 6 位验证码，完成

### 手动粘贴 Token

浏览器登录 https://www.leigod.com → F12 → Console 执行：

```js
JSON.parse(localStorage.getItem('account_token')).account_token
```

复制输出的字符串粘贴进去。

> Token 有效期约 7 天。过期后 HA 会弹出"需要重新认证"，两种方式都可用。

---

## 实体

| 实体 | 类型 | 说明 |
|---|---|---|
| `switch.leishen_accelerate` | switch | 开 = 继续计时，关 = 暂停计时 |
| `sensor.leishen_status` | sensor | `计时中` / `已暂停` |
| `sensor.leishen_remaining` | sensor | 剩余时长（h） |

---

## 自动化示例：Xbox 关机自动暂停

Xbox 集成会生成 `media_player.xxx` 实体，关机/待机时状态为 `off` / `standby`。

```yaml
automation:
  - alias: "雷神：Xbox 关闭 → 自动暂停"
    id: leishen_pause_on_xbox_off
    mode: single
    trigger:
      - platform: state
        entity_id: media_player.my_xbox      # ← 改成你的 Xbox 实体
        to: "off"
        for: "00:02:00"
      - platform: state
        entity_id: media_player.my_xbox
        to: "standby"
        for: "00:02:00"
    condition:
      - condition: state
        entity_id: switch.leishen_accelerate
        state: "on"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.leishen_accelerate

  - alias: "雷神：Xbox 开机 → 恢复加速"
    id: leishen_resume_on_xbox_on
    mode: single
    trigger:
      - platform: state
        entity_id: media_player.my_xbox
        from: ["off", "standby"]
        to: ["on", "playing", "idle"]
        for: "00:00:30"
    condition:
      - condition: state
        entity_id: switch.leishen_accelerate
        state: "off"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.leishen_accelerate
```

> 建议加 `for` 防抖。Xbox 开机瞬间状态会跳变，不加延迟容易误触发。

---

## 重要说明：这个开关控制的是什么

雷神加速器是按分钟计费的，`暂停` / `恢复` 控制的是**时长计费**，不是断开网络。

- **关闭开关** = 停止扣时长（如果用的是路由器插件，加速通道仍然在线）
- **打开开关** = 继续扣时长



## 常见问题

**Q：添加集成后实体是 `unknown`？**
A：检查 HA 日志中 `custom_components.leishen` 的记录，通常是 Token 失效或接口返回异常。

**Q：开关点了没反应 / 报错？**
A：查看日志中 `custom_components.leishen` 的记录。401/400006 类错误说明 Token 失效，重新认证。

**Q：能同时添加多个雷神账号吗？**
A：可以，每个账号单独添加一次集成。

**Q：手机号登录收不到短信？**
A：雷神有频率限制，等几分钟再试；也可改用 Token 方式。

---

## 许可

MIT License。使用风险自负，请遵守雷神加速器用户协议。
