#!/usr/bin/env bash
# ⚠️ 演示用假 webhook（非真实）—— 硬编码飞书 webhook，供巡检演示
FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/FAKE-0000-demo-do-not-use"
curl -s -X POST "$FEISHU_WEBHOOK" -d '{"msg":"demo"}'
