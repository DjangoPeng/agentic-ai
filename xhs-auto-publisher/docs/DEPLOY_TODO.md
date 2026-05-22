# 龙虾部署执行清单

目标机器：

- Ubuntu 24.04.4 LTS
- root 用户
- 项目目录：`~/projects/xhs-auto-publisher`

## 第一步：放置项目

确认代码位于：

```bash
~/projects/xhs-auto-publisher
```

## 第二步：安装系统依赖

执行：

```bash
bash ~/projects/xhs-auto-publisher/deploy/install_system_ubuntu.sh
```

完成后回报：

- `xvfb` 是否安装成功
- 系统依赖是否安装成功
- 是否有报错

## 第三步：初始化项目环境

执行：

```bash
cd ~/projects/xhs-auto-publisher
bash deploy/bootstrap_project.sh
```

完成后回报：

- `.venv` 是否创建成功
- `pip install -r requirements.txt` 是否成功
- `python -m playwright install chromium` 是否成功

## 第四步：配置环境变量

执行：

```bash
cd ~/projects/xhs-auto-publisher
cp deploy/env.example .env
```

按需要修改：

```env
MODE=publish
LOGIN_TIMEOUT=300
```

说明：

- `MODE=draft`：只走到草稿或发布前
- `MODE=publish`：真正触发发布
- `LOGIN_TIMEOUT`：等待扫码秒数

## 第五步：手动验证

执行：

```bash
cd ~/projects/xhs-auto-publisher
bash deploy/run_with_xvfb.sh
```

观察结果：

- 是否成功启动浏览器
- 是否生成二维码截图
- 是否生成龙虾通知 payload
- 是否生成 `runtime/runs/<timestamp>/`

关键文件：

- `runtime/runs/<run_id>/screenshots/login_qr.png`
- `runtime/lobster-notify/<run_id>/login_qr.payload.json`

## 第六步：龙虾转发飞书群

龙虾需要读取：

```text
runtime/lobster-notify/<run_id>/login_qr.payload.json
```

然后：

1. 读取 `delivery.path`
2. 把这张二维码图片发到飞书群
3. 把 `delivery.caption_lines` 一并发出

协议文档：

- [LOBSTER_NOTIFY_PROTOCOL.md](./LOBSTER_NOTIFY_PROTOCOL.md)

## 第七步：托管为 systemd 服务

如果手动验证通过，再执行：

```bash
cp ~/projects/xhs-auto-publisher/deploy/systemd/xhs-auto-publisher-cloud.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable xhs-auto-publisher-cloud.service
```

如需手动启动：

```bash
systemctl start xhs-auto-publisher-cloud.service
```

查看日志：

```bash
journalctl -u xhs-auto-publisher-cloud.service -n 200 --no-pager
```

## 回报格式

每完成一步，请回报：

1. 执行了什么命令
2. 成功还是失败
3. 如果失败，贴关键报错
4. 当前卡在哪一步
