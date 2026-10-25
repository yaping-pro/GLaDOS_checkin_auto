import requests, json, os, time, hmac, hashlib, base64


def send_telegram(title, content, token=""):
    """Telegram 主通道：按 4000 字符切分，纯文本发送，避免 HTML 解析失败。

    token 缺省回退 TG_BOT_TOKEN；调用方按严重度选择 alerts（P1）或 digest（P2）。
    """
    token = token or os.environ.get("TG_BOT_TOKEN", "")
    chat = os.environ.get("TG_CHAT_ID", "")
    api = os.environ.get("TG_API_HOST", "https://tg.yaping.dpdns.org").rstrip("/")
    if not token or not chat:
        return
    text = f"{title}\n\n{content.strip()}"
    chunks, cur = [], ""
    for line in text.splitlines(keepends=True):
        if cur and len(cur) + len(line) > 4000:
            chunks.append(cur)
            cur = line
        else:
            cur += line
    if cur:
        chunks.append(cur)
    for i, chunk in enumerate(chunks, 1):
        prefix = f"({i}/{len(chunks)})\n" if len(chunks) > 1 else ""
        try:
            res = requests.post(
                f"{api}/bot{token}/sendMessage",
                data={"chat_id": chat, "text": prefix + chunk},
                timeout=15,
            )
            print(f"Telegram 推送响应[{i}/{len(chunks)}]:", res.text[:200])
        except Exception as e:
            print("Telegram 推送失败:", e)


# -------------------------------------------------------------------------------------------
# github workflows
# -------------------------------------------------------------------------------------------
if __name__ == '__main__':
# 推送内容
    sendContent = ''
# glados账号cookie 直接使用数组 如果使用环境变量需要字符串分割一下
    cookies = os.environ.get("GLADOS_COOKIE", []).split("&")
    if cookies[0] == "":
        print('未获取到COOKIE变量') 
        cookies = []
        exit(0)
    url= "https://glados.rocks/api/user/checkin"
    url2 = "https://glados.rocks/api/user/status"
    url3 = "https://glados.rocks/api/user/points"
    url_exchange = "https://glados.rocks/api/user/exchange"
    referer = 'https://glados.rocks/console/checkin'
    origin = "https://glados.rocks"
    useragent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    payload = {
        'token': 'glados.rocks'
    }
    has_warning = False
    has_cookie_expired = False
    for idx, cookie in enumerate(cookies, 1):
        headers = {'cookie': cookie, 'referer': referer, 'origin': origin, 'user-agent': useragent}
        checkin = requests.post(url, headers={**headers, 'content-type': 'application/json;charset=UTF-8'}, data=json.dumps(payload))
        state = requests.get(url2, headers=headers)
        points_req = requests.get(url3, headers=headers)

        state_json = {}
        try:
            state_json = state.json()
        except Exception:
            pass

        checkin_json = {}
        try:
            checkin_json = checkin.json()
        except Exception:
            pass

        points_json = {}
        try:
            points_json = points_req.json()
        except Exception:
            pass

        email = state_json.get('data', {}).get('email', '')
        is_invalid = (
            not email or
            state_json.get('code') != 0 or
            checkin_json.get('code') in [-2, 401, 403] or
            '没有权限' in checkin.text or
            'Please Login' in checkin.text
        )
        if is_invalid:
            has_cookie_expired = True
            print(f'账号[{idx}]----结果--Cookie已失效(鉴权失败)----')
            lines = [
                f"🚨 账号[{idx}]：登录态已失效",
                "❌ 状态：鉴权失败（Session 过期或未登录）",
                "🛠 处置：请重新在浏览器登录并提取 Cookie，更新 GitHub Secrets `GLADOS_COOKIE`！"
            ]
            sendContent += "\n".join(lines) + "\n\n"
            continue

        days_left = int(float(state_json.get('data', {}).get('leftDays', 0)))
        points = int(float(points_json.get('points', 0)))
        mess = checkin_json.get('message', '签到完成')

        print(f'{email}----结果--{mess}----积分({points})----剩余({days_left})天')
        lines = [
            f"👤 账号：{email}",
            f"📝 签到结果：{mess}",
            f"💰 当前结余积分：{points} 分",
            f"⏳ 剩余服务天数：{days_left} 天"
        ]

        # 智能自动兑换防御：当剩余天数 <= 7 天且积分充足时自动续期
        exchanged = False
        exchange_plan = None
        if days_left <= 7:
            if points >= 500:
                exchange_plan = ("plan500", 500, 100)
            elif points >= 200:
                exchange_plan = ("plan200", 200, 30)
            elif points >= 100 and days_left <= 2:
                exchange_plan = ("plan100", 100, 10)

        if exchange_plan:
            plan_key, cost_points, add_days = exchange_plan
            try:
                ex_res = requests.post(
                    url_exchange,
                    headers={**headers, 'content-type': 'application/json;charset=UTF-8'},
                    data=json.dumps({"planType": plan_key}),
                    timeout=10
                ).json()
                if ex_res.get('code') == 0:
                    exchanged = True
                    points = int(float(ex_res.get('points', points - cost_points)))
                    days_left += add_days
                    lines.append(f"\n🎉【已自动续期】成功兑换【{cost_points}积分 = {add_days}天】！\n👉 最新服务天数：{days_left} 天，剩余积分：{points} 分")
                else:
                    lines.append(f"\n⚠️【自动兑换失败】{ex_res.get('message', '未知错误')}")
            except Exception as e:
                lines.append(f"\n⚠️【自动兑换异常】{str(e)}")

        if days_left <= 7 and not exchanged:
            has_warning = True
            lines.append(f"\n⚠️【到期预警】服务仅剩 {days_left} 天，请及时续期！")
            if points >= 500:
                lines.append(f"💡 当前积分充足（{points}分），强烈推荐前往控制台兑换【500积分 = 100天】！")
            elif points >= 200:
                lines.append(f"💡 当前可兑换【200积分 = 30天】进行续命过渡（剩余 {points} 分）！")
            elif points >= 100:
                lines.append(f"💡 当前可兑换【100积分 = 10天】（剩余 {points} 分）！")
            else:
                lines.append(f"⚠️ 积分仅剩 {points} 分，不足最低兑换门槛（100分），请留意服务中断！")
        else:
            if points < 200:
                lines.append(f"🎯 积分目标：距离 200 分（30天续期档）还差 {200 - points} 分")
            elif points < 500:
                lines.append(f"🎯 积分目标：已达成 200 分档！距离 500 分（永久续期档）还差 {500 - points} 分")
            else:
                lines.append(f"🎉 积分已达 {points} 分！可随时兑换 500 积分 = 100 天！")
        sendContent += "\n".join(lines) + "\n\n"

    if has_cookie_expired:
        notice_title = "🚨 GLaDOS 签到报警：Cookie 已失效！"
    elif has_warning:
        notice_title = "⚠️ GLaDOS 续期预警通知"
    else:
        notice_title = "🎉 GLaDOS 自动签到通知"

    # 兼容 Bark 推送 (iOS)
    bark_key = os.environ.get("BARK_KEY", "")
    if bark_key:
        try:
            requests.get(f"https://api.day.app/{bark_key}/{notice_title}/{sendContent}", timeout=10)
        except Exception as e:
            print("Bark 推送失败:", e)

    # 飞书机器人推送
    feishu_webhook = os.environ.get("FEISHU_WEBHOOK", "")
    feishu_secret = os.environ.get("FEISHU_SECRET", "")
    if feishu_webhook:
        try:
            timestamp = str(int(time.time()))
            feishu_payload = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": notice_title,
                            "content": [
                                [
                                    {"tag": "text", "text": sendContent.strip()}
                                ]
                            ]
                        }
                    }
                }
            }
            if feishu_secret:
                string_to_sign = f'{timestamp}\n{feishu_secret}'
                hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
                sign = base64.b64encode(hmac_code).decode('utf-8')
                feishu_payload["timestamp"] = timestamp
                feishu_payload["sign"] = sign

            res = requests.post(feishu_webhook, json=feishu_payload, timeout=10)
            print("飞书推送响应:", res.text)
        except Exception as e:
            print("飞书推送失败:", e)

    # Telegram 推送（主力通道）：Cookie 失效属 P1 走 alerts，其余日常结果走 digest
    if has_cookie_expired:
        send_telegram(notice_title, sendContent, os.environ.get("TG_ALERTS_BOT_TOKEN", ""))
    else:
        send_telegram(notice_title, sendContent, os.environ.get("TG_DIGEST_BOT_TOKEN", ""))

