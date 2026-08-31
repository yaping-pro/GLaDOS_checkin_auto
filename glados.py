import requests, json, os, time, hmac, hashlib, base64
# -------------------------------------------------------------------------------------------
# github workflows
# -------------------------------------------------------------------------------------------
if __name__ == '__main__':
# pushplus秘钥 申请地址 http://www.pushplus.plus
    sckey = os.environ.get("PUSHPLUS_TOKEN", "")
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
    referer = 'https://glados.rocks/console/checkin'
    origin = "https://glados.rocks"
    useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
    payload = {
        'token': 'glados.one'
    }
    has_warning = False
    for cookie in cookies:
        headers = {'cookie': cookie, 'referer': referer, 'origin': origin, 'user-agent': useragent}
        checkin = requests.post(url, headers={**headers, 'content-type': 'application/json;charset=UTF-8'}, data=json.dumps(payload))
        state = requests.get(url2, headers=headers)
        points_req = requests.get(url3, headers=headers)

        try:
            days_left = int(float(state.json()['data']['leftDays']))
        except Exception:
            days_left = 0

        try:
            points = int(float(points_req.json().get('points', 0)))
        except Exception:
            points = 0

        email = state.json().get('data', {}).get('email', '未知用户')

        if 'message' in checkin.text:
            mess = checkin.json()['message']
            print(f'{email}----结果--{mess}----积分({points})----剩余({days_left})天')
            lines = [
                f"👤 账号：{email}",
                f"📝 签到结果：{mess}",
                f"💰 当前结余积分：{points} 分",
                f"⏳ 剩余服务天数：{days_left} 天"
            ]
            if days_left <= 7:
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
        else:
            print(f'{email} cookie已失效')
            sendContent += f'{email} cookie已失效，请重新获取 Cookie 更新 Secrets！\n\n'
            has_warning = True

    if sckey != "":
        try:
            push_url = "https://www.pushplus.plus/send"
            res = requests.post(push_url, json={
                "token": sckey,
                "title": f"{email} GLaDOS签到结果",
                "content": sendContent.replace('\n', '<br/>'),
                "template": "html"
            }, timeout=10)
            print("PushPlus 推送响应:", res.text)
        except Exception as e:
            print("PushPlus 推送失败:", e)

    # 兼容 Bark 推送 (iOS)
    bark_key = os.environ.get("BARK_KEY", "")
    if bark_key:
        try:
            requests.get(f"https://api.day.app/{bark_key}/GLaDOS签到通知/{sendContent}", timeout=10)
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
                            "title": "⚠️ GLaDOS 续期预警通知" if has_warning else "🎉 GLaDOS 自动签到通知",
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

