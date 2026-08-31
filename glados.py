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
    url2= "https://glados.rocks/api/user/status"
    referer = 'https://glados.rocks/console/checkin'
    origin = "https://glados.rocks"
    useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
    payload={
        'token': 'glados.one'
    }
    for cookie in cookies:
        checkin = requests.post(url,headers={'cookie': cookie ,'referer': referer,'origin':origin,'user-agent':useragent,'content-type':'application/json;charset=UTF-8'},data=json.dumps(payload))
        state =  requests.get(url2,headers={'cookie': cookie ,'referer': referer,'origin':origin,'user-agent':useragent})
    #--------------------------------------------------------------------------------------------------------#  
        days_left = state.json()['data']['leftDays'].split('.')[0]
        email = state.json()['data']['email']
        if 'message' in checkin.text:
            mess = checkin.json()['message']
            print(f'{email}----结果--{mess}----剩余({days_left})天')  # 日志输出
            sendContent += f'{email}----{mess}----剩余({days_left})天\n'
        else:
            print(f'{email} cookie已失效')
            sendContent += f'{email} cookie已失效\n'

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
                            "title": "🎉 GLaDOS 自动签到通知",
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

